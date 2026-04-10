# -*- coding: utf-8 -*-
import os
import logging
import re
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class ClientMaster(models.Model):
    _name = 'purple_ai.client'
    _description = 'Client Folder Mapping'
    _order = 'name'

    name = fields.Char(string='Client Name', required=True)
    folder_path = fields.Char(string='Watch Folder Path', help="Automatically generated path on the server")
    extraction_master_id = fields.Many2one('purple_ai.extraction_master', string='Extraction Template', required=True)
    company_id = fields.Many2one('res.company', string='Linked Company', readonly=True)
    active = fields.Boolean(default=True)
    
    # Progress Tracking
    scan_status = fields.Selection([
        ('idle', 'Idle'),
        ('scanning', 'Scanning'),
    ], default='idle', string='Scan Status')
    scan_count = fields.Integer(string='Processed Index', default=0)
    scan_total = fields.Integer(string='Total Files', default=0)
    scan_current_file = fields.Char(string='Processing File')
    scan_progress = fields.Float(string='Progress Percentage', compute='_compute_scan_progress')
    
    last_scan = fields.Datetime(string='Last Scanned At', readonly=True)
    processed_count = fields.Integer(string='Processed Files', compute='_compute_counts')
    extraction_result_ids = fields.One2many('purple_ai.extraction_result', 'client_id', string='Extraction Results')

    # Computed HTML listing of files in the watch folder
    folder_files_html = fields.Html(string='Folder Contents', compute='_compute_folder_files', sanitize=False)

    def _compute_counts(self):
        for rec in self:
            rec.processed_count = self.env['purple_ai.extraction_result'].search_count([('client_id', '=', rec.id)])

    def _compute_folder_files(self):
        """List all PDF/image files inside the client's watch folder."""
        import datetime
        SUPPORTED_EXT = {'.pdf', '.jpg', '.jpeg', '.png', '.webp', '.tiff'}
        for rec in self:
            path = (rec.folder_path or '').strip()
            if not path or not os.path.isdir(path):
                rec.folder_files_html = (
                    '<div class="alert alert-warning py-2">'
                    '<i class="fa fa-folder-open me-2"></i>'
                    'Watch folder not found or not configured.</div>'
                )
                continue

            try:
                entries = []
                for fname in sorted(os.listdir(path)):
                    ext = os.path.splitext(fname)[1].lower()
                    if ext not in SUPPORTED_EXT:
                        continue
                    fpath = os.path.join(path, fname)
                    stat = os.stat(fpath)
                    size_kb = round(stat.st_size / 1024, 1)
                    mtime = datetime.datetime.fromtimestamp(stat.st_mtime).strftime('%d %b %Y %H:%M')
                    entries.append((fname, size_kb, mtime, ext))

                if not entries:
                    rec.folder_files_html = (
                        '<div class="alert alert-info py-2">'
                        '<i class="fa fa-inbox me-2"></i>'
                        'No PDF or image files found in the watch folder.</div>'
                    )
                    continue

                icon_map = {'.pdf': 'fa-file-pdf-o text-danger', '.jpg': 'fa-file-image-o text-info',
                            '.jpeg': 'fa-file-image-o text-info', '.png': 'fa-file-image-o text-info',
                            '.webp': 'fa-file-image-o text-info', '.tiff': 'fa-file-image-o text-info'}

                rows = ''.join(
                    f'<tr>'
                    f'<td><i class="fa {icon_map.get(ext, "fa-file-o")} me-2"></i>{fname}</td>'
                    f'<td class="text-muted text-end">{size_kb} KB</td>'
                    f'<td class="text-muted text-end">{mtime}</td>'
                    f'</tr>'
                    for fname, size_kb, mtime, ext in entries
                )
                rec.folder_files_html = f'''
                    <div class="mb-2 text-muted" style="font-size:0.85rem;">
                        <i class="fa fa-folder-open me-1"></i>
                        <strong>{len(entries)}</strong> file(s) &nbsp;·&nbsp;
                        <code style="font-size:0.8rem;">{path}</code>
                    </div>
                    <table class="table table-sm table-hover table-bordered mb-0" style="font-size:0.9rem;">
                        <thead class="table-light">
                            <tr>
                                <th><i class="fa fa-file me-1"></i> File Name</th>
                                <th class="text-end">Size</th>
                                <th class="text-end">Last Modified</th>
                            </tr>
                        </thead>
                        <tbody>{rows}</tbody>
                    </table>'''
            except Exception as e:
                rec.folder_files_html = f'<div class="alert alert-danger py-2">Error reading folder: {e}</div>'

    @api.depends('scan_count', 'scan_total')
    def _compute_scan_progress(self):
        for rec in self:
            if rec.scan_total > 0:
                rec.scan_progress = min(100.0, (rec.scan_count / rec.scan_total) * 100.0)
            else:
                rec.scan_progress = 0.0

    @api.model_create_multi
    def create(self, vals_list):
        new_company_ids = []
        for vals in vals_list:
            if 'folder_path' not in vals or not vals['folder_path']:
                vals['folder_path'] = self._generate_auto_path(vals)

            if 'company_id' not in vals:
                new_company = self.env['res.company'].sudo().create({
                    'name': vals.get('name', 'New Client Company'),
                    'currency_id': (self.env.ref('base.INR').id if self.env.ref('base.INR', raise_if_not_found=False) else self.env.company.currency_id.id)
                })
                vals['company_id'] = new_company.id
                new_company_ids.append(new_company.id)
                self.env.user.sudo().write({'company_ids': [(4, new_company.id)]})

        if new_company_ids:
            current_allowed = list(self.env.context.get('allowed_company_ids', self.env.user.company_ids.ids))
            patched_allowed = list(set(current_allowed + new_company_ids))
            self = self.with_context(allowed_company_ids=patched_allowed)

        res = super(ClientMaster, self).create(vals_list)
        for rec in res:
            rec._ensure_folder_exists()
        return res

    def write(self, vals):
        root_path = self.env['ir.config_parameter'].sudo().get_param('purple_ai.root_path')
        if 'name' in vals or 'extraction_master_id' in vals:
            for rec in self:
                if root_path and (not rec.folder_path or rec.folder_path.startswith(root_path)):
                    vals['folder_path'] = self._generate_auto_path({
                        'name': vals.get('name', rec.name),
                        'extraction_master_id': vals.get('extraction_master_id', rec.extraction_master_id.id)
                    })
        res = super().write(vals)
        self._ensure_folder_exists()
        return res

    def _generate_auto_path(self, vals):
        """Generates a sanitized path: {root_path}/{template}/{client}"""
        root_path = self.env['ir.config_parameter'].sudo().get_param('purple_ai.root_path')
        if not root_path:
             raise UserError(_("Please define the 'Root Folder Path' in Purple AI settings first."))
             
        def slugify(text):
            if not text: return "unknown"
            return re.sub(r'[^a-z0-9]+', '_', str(text).lower()).strip('_')
        client_name = slugify(vals.get('name', 'default'))
        template_id = vals.get('extraction_master_id')
        template_name = "invoices"
        if template_id:
            template = self.env['purple_ai.extraction_master'].browse(template_id)
            if template.exists(): template_name = slugify(template.name)
        return os.path.join(root_path, template_name, client_name)

    def _ensure_folder_exists(self):
        """Creates the directory structure on the server with 777 permissions."""
        root_path = self.env['ir.config_parameter'].sudo().get_param('purple_ai.root_path')
        if not root_path:
            return
            
        for rec in self:
            if rec.folder_path:
                path = rec.folder_path.strip()
                try:
                    if not os.path.exists(path):
                        os.makedirs(path, mode=0o777, exist_ok=True)
                    os.chmod(path, 0o777)
                    parent = os.path.dirname(path)
                    if parent != root_path and parent.startswith(root_path):
                        os.chmod(parent, 0o777)
                except Exception as e:
                    _logger.error("Failed to create/chmod folder %s: %s", path, str(e))

    @api.constrains('folder_path')
    def _check_folder_path(self):
        for rec in self:
            if not rec.folder_path: continue
            path = rec.folder_path.strip()
            if not os.path.exists(path): rec._ensure_folder_exists()
            if not os.path.exists(path):
                raise UserError(_("The folder path '%s' is not accessible.") % path)
            if not os.path.isdir(path):
                raise UserError(_("The path '%s' is not a directory.") % path)

    def action_view_results(self):
        self.ensure_one()
        return {
            'name': _('Extraction Results'),
            'type': 'ir.actions.act_window',
            'res_model': 'purple_ai.extraction_result',
            'view_mode': 'list,form',
            'domain': [('client_id', '=', self.id)],
            'context': {'default_client_id': self.id},
        }
