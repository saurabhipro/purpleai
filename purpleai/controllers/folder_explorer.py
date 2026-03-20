# -*- coding: utf-8 -*-
import os
import mimetypes
import logging
from odoo import http, _
from odoo.http import request

_logger = logging.getLogger(__name__)

class FolderExplorerController(http.Controller):

    def _get_root_path(self, active_company_ids=None):
        """Returns the base configured root path from system settings."""
        root = request.env['ir.config_parameter'].sudo().get_param('purple_ai.root_path')
        if not root:
             return "/tmp" # Safe fallback if not set yet
        return root

    def _get_active_client(self, active_company_ids=None):
        """Return the single client for the current active companies."""
        primary_company = request.env.company
        Client = request.env['purple_ai.client'].sudo()
        Company = request.env['res.company'].sudo()

        # Prioritize companies passed from the UI
        if active_company_ids:
            active_companies = Company.browse(active_company_ids).exists()
        else:
            active_companies = request.env.companies
        
        # 1. Non-primary companies (the ones that were explicitly "checked" in UI)
        for company in active_companies:
            if company.id == primary_company.id:
                continue
            client = Client.search([('company_id', '=', company.id), ('active', '=', True)], limit=1)
            if client:
                return client

        # 2. Match by exact primary company
        client = Client.search([('company_id', '=', primary_company.id), ('active', '=', True)], limit=1)
        if client:
            return client

        # 3. Last resort: Name match (EXCLUDING 'YourCompany' and 'My Company')
        for company in active_companies:
            if company.name.lower() in ['yourcompany', 'my company', 'main company']:
                continue
            client = Client.search([('name', '=ilike', company.name), ('active', '=', True)], limit=1)
            if client:
                return client

        return None

    def _validate_path(self, path, active_company_ids=None):
        """Ensures the path is within the root path to prevent directory traversal."""
        root = os.path.abspath(self._get_root_path(active_company_ids=active_company_ids))
        requested = os.path.abspath(os.path.join(root, path.lstrip('/')))
        if not requested.startswith(root):
            return None
        return requested

    @http.route('/purple_ai/list_folder', type='json', auth='user', methods=['POST'], csrf=False)
    def list_folder(self, folder_path='', active_company_ids=None):
        # 1. Resolve Global Base
        root = self._get_root_path()
        
        # 2. Intelligent Auto-Jump: if path is empty, find the preferred company folder
        if not folder_path:
             client = self._get_active_client(active_company_ids=active_company_ids)
             if client and client.folder_path and client.folder_path.startswith(root):
                  # Extract the relative portion to jump to (e.g. invoice_extraction/hpcl)
                  folder_path = client.folder_path[len(root):].lstrip('/')

        full_path = self._validate_path(folder_path, active_company_ids=active_company_ids)
        if not full_path or not os.path.exists(full_path):
             return {'status': 'error', 'message': _('Invalid path or folder not found: %s') % folder_path}
        
        if not os.path.isdir(full_path):
             return {'status': 'error', 'message': _('Path is not a directory.')}

        contents = []
        try:
            for item in os.listdir(full_path):
                item_path = os.path.join(full_path, item)
                is_dir = os.path.isdir(item_path)
                stats = os.stat(item_path)
                
                contents.append({
                    'name': item,
                    'is_dir': is_dir,
                    'size': stats.st_size if not is_dir else 0,
                    'mtime': stats.st_mtime,
                    'path': os.path.join(folder_path, item).replace('\\', '/')
                })
            
            # Sort: Directories first, then alphabetical
            contents.sort(key=lambda x: (not x['is_dir'], x['name'].lower()))
            
            active_client = self._get_active_client(active_company_ids=active_company_ids)
            root_name = active_client.name if active_client else (request.env.company.name or 'Home')
            return {
                'status': 'success',
                'contents': contents,
                'current_path': folder_path,
                'root_name': root_name,
            }
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    @http.route('/purple_ai/download_file', type='http', auth='user')
    def download_file(self, file_path):
        full_path = self._validate_path(file_path)
        if not full_path or not os.path.exists(full_path) or os.path.isdir(full_path):
            return request.not_found()

        filename = os.path.basename(full_path)
        mime = mimetypes.guess_type(full_path)[0] or 'application/octet-stream'
        
        with open(full_path, 'rb') as f:
            content = f.read()
            
        return request.make_response(content, [
            ('Content-Type', mime),
            ('Content-Disposition', http.content_disposition(filename))
        ])

    @http.route('/purple_ai/upload_file', type='http', auth='user', methods=['POST'], csrf=False)
    def upload_file(self, folder_path, ufile):
        full_folder_path = self._validate_path(folder_path)
        if not full_folder_path or not os.path.exists(full_folder_path):
            return request.make_response("Invalid folder path", status=400)

        filename = ufile.filename
        file_path = os.path.join(full_folder_path, filename)
        
        # Save file to server
        with open(file_path, 'wb') as f:
            f.write(ufile.read())
            
        return request.make_response("Success", status=200)

    @http.route('/purple_ai/delete_file', type='json', auth='user', methods=['POST'], csrf=False)
    def delete_file(self, file_path=None, file_paths=None):
        paths = file_paths if file_paths is not None else ([file_path] if file_path else [])
        if not paths:
            return {'status': 'error', 'message': _('No paths provided.')}

        errors = []
        success_count = 0
        for p in paths:
            full_path = self._validate_path(p)
            if not full_path or not os.path.exists(full_path):
                errors.append(_("Path not found: %s") % p)
                continue

            try:
                if os.path.isdir(full_path):
                    if len(os.listdir(full_path)) > 0:
                         errors.append(_("Folder not empty: %s") % p)
                         continue
                    os.rmdir(full_path)
                else:
                    os.remove(full_path)
                success_count += 1
            except Exception as e:
                errors.append(f"{p}: {str(e)}")

        if errors and success_count == 0:
            return {'status': 'error', 'message': "\n".join(errors)}
        
        return {
            'status': 'success', 
            'message': _('Deleted %d items.') % success_count if not errors else _('Deleted %d items with %d errors.') % (success_count, len(errors)),
            'errors': errors
        }
