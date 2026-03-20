# -*- coding: utf-8 -*-
import os
import logging
import json
from odoo import models, fields, api, _
from odoo.exceptions import UserError
try:
    import fitz
except ImportError:
    fitz = None
import base64
import io
from odoo.addons.purpleai.services import ai_service

_logger = logging.getLogger(__name__)

class ClientMaster(models.Model):
    _name = 'purple_ai.client'
    _description = 'Client Folder Mapping'
    _order = 'name'

    name = fields.Char(string='Client Name', required=True)
    folder_path = fields.Char(string='Watch Folder Path', help="Automatically generated path on the server")
    extraction_master_id = fields.Many2one('purple_ai.extraction_master', string='Extraction Template', required=True)
    company_id = fields.Many2one('res.company', string='Linked Company', readonly=True, help="Automatically created for this client")
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

    def _compute_counts(self):
        for rec in self:
            rec.processed_count = self.env['purple_ai.extraction_result'].search_count([('client_id', '=', rec.id)])

    @api.depends('scan_count', 'scan_total')
    def _compute_scan_progress(self):
        for rec in self:
            if rec.scan_total > 0:
                rec.scan_progress = min(100.0, (rec.scan_count / rec.scan_total) * 100.0)
            else:
                rec.scan_progress = 0.0

    @api.model_create_multi
    def create(self, vals_list):
        # Collect new company IDs so we can patch the request context
        new_company_ids = []

        for vals in vals_list:
            # 1. Generate Path
            if 'folder_path' not in vals or not vals['folder_path']:
                vals['folder_path'] = self._generate_auto_path(vals)

            # 2. Create Company for this Client
            if 'company_id' not in vals:
                new_company = self.env['res.company'].sudo().create({
                    'name': vals.get('name', 'New Client Company'),
                    'currency_id': (
                        self.env.ref('base.INR').id
                        if self.env.ref('base.INR', raise_if_not_found=False)
                        else self.env.company.currency_id.id
                    )
                })
                vals['company_id'] = new_company.id
                new_company_ids.append(new_company.id)

                # Add to current user's allowed companies so they can switch immediately
                self.env.user.sudo().write({'company_ids': [(4, new_company.id)]})

        # Patch the request context so the multi-company security rule allows the
        # newly created company in the post-save visibility check.
        if new_company_ids:
            current_allowed = list(
                self.env.context.get('allowed_company_ids', self.env.user.company_ids.ids)
            )
            patched_allowed = list(set(current_allowed + new_company_ids))
            self = self.with_context(allowed_company_ids=patched_allowed)

        res = super(ClientMaster, self).create(vals_list)
        for rec in res:
            rec._ensure_folder_exists()
        return res

    def write(self, vals):
        # If name or template changes, and it was using an auto-generated path, update it
        if 'name' in vals or 'extraction_master_id' in vals:
            for rec in self:
                # Only auto-update if the current path is in /home/odoo18/
                if not rec.folder_path or rec.folder_path.startswith('/home/odoo18/'):
                    new_vals = {**vals}
                    vals['folder_path'] = self._generate_auto_path({
                        'name': vals.get('name', rec.name),
                        'extraction_master_id': vals.get('extraction_master_id', rec.extraction_master_id.id)
                    })
        res = super().write(vals)
        # Always attempt to ensure folder exists on save
        self._ensure_folder_exists()
        return res

    def _generate_auto_path(self, vals):
        """Generates a sanitized path: /home/odoo18/{template}/{client}"""
        import re
        def slugify(text):
            if not text: return "unknown"
            return re.sub(r'[^a-z0-9]+', '_', str(text).lower()).strip('_')

        client_name = slugify(vals.get('name', 'default'))
        
        template_id = vals.get('extraction_master_id')
        template_name = "invoices" # Default parent
        if template_id:
            template = self.env['purple_ai.extraction_master'].browse(template_id)
            if template.exists():
                template_name = slugify(template.name)

        return os.path.join('/home/odoo18', template_name, client_name)

    def _ensure_folder_exists(self):
        """Creates the directory structure on the server with 777 permissions."""
        for rec in self:
            if rec.folder_path:
                path = rec.folder_path.strip()
                try:
                    if not os.path.exists(path):
                        # Create with 777 permissions
                        os.makedirs(path, mode=0o777, exist_ok=True)
                        _logger.info("Successfully created watch folder: %s", path)
                    
                    # Explicitly set permissions to 777 (world-writable)
                    # This allows 'odoo' user to drop files into 'odoo18' owned folders
                    os.chmod(path, 0o777)
                    
                    # Also ensure parents up to /home/odoo18/ have enough permissions
                    parent = os.path.dirname(path)
                    if parent != '/home/odoo18' and parent.startswith('/home/odoo18/'):
                        os.chmod(parent, 0o777)
                        
                except Exception as e:
                    _logger.error("Failed to create/chmod folder %s: %s", path, str(e))

    @api.constrains('folder_path')
    def _check_folder_path(self):
        for rec in self:
            if not rec.folder_path:
                continue
            path = rec.folder_path.strip()
            # If it doesn't exist, we try to create it first
            if not os.path.exists(path):
                rec._ensure_folder_exists()
            
            if not os.path.exists(path):
                msg = _("The folder path '%s' is not accessible. \n\n"
                        "Likely a permission error. The Odoo server user (odoo18) "
                        "cannot write to this location.") % path
                raise UserError(msg)
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

    def cron_scan_client_folders(self):
        """Cron entry point to scan all active client folders."""
        clients = self.search([('active', '=', True)])
        _logger.info("Cron: Scanning %d clients", len(clients))
        for client in clients:
            try:
                client.action_scan_folder()
            except Exception as e:
                _logger.error("Cron: Failed to scan client %s: %s", client.name, str(e))
                self.env.cr.rollback()

    def _update_scan_progress(self, vals):
        """Write scan progress fields in an isolated cursor to avoid serialization conflicts."""
        allowed = {'scan_status', 'scan_total', 'scan_count', 'scan_current_file', 'last_scan'}
        vals = {k: v for k, v in vals.items() if k in allowed}
        if not vals:
            return
        try:
            with self.pool.cursor() as cr:
                set_clause = ', '.join('"{}" = %s'.format(k) for k in vals)
                cr.execute(
                    'UPDATE purple_ai_client SET {} WHERE id = %s'.format(set_clause),
                    list(vals.values()) + [self.id]
                )
        except Exception as e:
            _logger.warning("Could not update scan progress for client %s: %s", self.id, str(e))

    def action_scan_folder(self):
        """Scans the client folder for new PDF files and processes them."""
        self.ensure_one()
        folder_path = (self.folder_path or '').strip()
        if not folder_path or not os.path.exists(folder_path):
            _logger.warning("Folder path %s not found for client %s", folder_path, self.name)
            return

        files = [f for f in os.listdir(folder_path) if f.lower().endswith('.pdf')]

        # Filter files that are NOT yet processed
        Result = self.env['purple_ai.extraction_result']
        files_to_process = []
        for filename in files:
            existing = Result.search([('client_id', '=', self.id), ('filename', '=', filename)], limit=1)
            if not existing:
                files_to_process.append(filename)

        if not files_to_process:
            _logger.info("Nothing to scan for client %s", self.name)
            return

        _logger.info("Scanning client %s folder [%s]: found %d new PDFs", self.name, folder_path, len(files_to_process))

        # Use isolated cursor for progress — avoids concurrent-update serialization errors
        self._update_scan_progress({
            'scan_status': 'scanning',
            'scan_total': len(files_to_process),
            'scan_count': 0,
            'scan_current_file': 'Starting...',
        })
        self._send_scan_notification()

        for i, filename in enumerate(files_to_process):
            self._update_scan_progress({
                'scan_count': i + 1,
                'scan_current_file': filename,
            })
            self._send_scan_notification()

            file_path = os.path.join(self.folder_path, filename)
            try:
                self._process_one_file(file_path, filename)
            except Exception as e:
                _logger.error("Failed to process file %s for client %s: %s", filename, self.name, str(e))

        self._update_scan_progress({
            'scan_status': 'idle',
            'scan_count': len(files_to_process),
            'scan_current_file': 'Scanning Completed',
            'last_scan': fields.Datetime.now(),
        })
        self.env['purple_ai.client'].invalidate_model(['scan_status', 'scan_count', 'scan_current_file', 'last_scan'])
        self._send_scan_notification()

    def _send_scan_notification(self):
        """Sends a bus notification to update the UI."""
        self.ensure_one()
        # Odoo 18 style bus notification
        msg = {
            'type': 'purple_ai_scan_progress',
            'client_id': self.id,
            'progress': self.scan_progress,
            'current_file': self.scan_current_file,
            'status': self.scan_status
        }
        self.env['bus.bus']._sendone(self.env.user.partner_id, 'purple_ai_notification', msg)

    def _process_one_file(self, file_path, filename):
        """Uploads file to Gemini and extracts data based on the template."""
        # 1. Prepare Prompt
        fields_to_extract = self.extraction_master_id.field_ids.filtered(lambda f: f.active)
        if not fields_to_extract:
            _logger.warning("No active fields in template %s for client %s", self.extraction_master_id.name, self.name)
            return

        field_prompts = [f"- {f.field_key}: {f.instruction}" for f in fields_to_extract]
        field_list = "\n".join(field_prompts)

        rules_to_eval = self.extraction_master_id.rule_ids.filtered(lambda r: r.active and r.eval_type == 'ai')
        rule_prompts = [f"- {r.rule_code}: {r.description}" for r in rules_to_eval]
        rule_list = "\n".join(rule_prompts) if rule_prompts else ""
        
        system_prompt = (
            "You are a specialized data extraction AI. "
            "Extract the following fields from the provided document. "
            "For EACH field, return a JSON object containing:\n"
            "1. 'value': The extracted text string.\n"
            "2. 'box_2d': [ymin, xmin, ymax, xmax] coordinates in normalized 0-1000 scale.\n"
            "3. 'page_number': The page index (starting from 1) where the data was found.\n\n"
        )

        if rule_list:
            system_prompt += (
                "Additionally, evaluate these VALIDATION RULES. \n"
                "Add a top-level key 'validations' to your JSON response. \n"
                "For EACH validation rule, return:\n"
                "- 'status': true if the rule passes, false if it fails.\n"
                "- 'msg': A brief explanation of why it failed (or 'Passed').\n"
                "- 'box_2d' and 'page_number': If the failure relates to a specific part of the document.\n\n"
                f"RULES TO EVALUATE:\n{rule_list}\n\n"
            )

        system_prompt += (
            "Return ONLY a JSON map where keys match the requested field keys.\n\n"
            f"FIELDS TO EXTRACT:\n{field_list}"
        )

        # 2. Resolve Provider & Model
        active_provider = ai_service._resolve_provider(self.env)
        active_model = "Unknown"
        if active_provider == 'gemini':
            active_model = self.env['ir.config_parameter'].sudo().get_param('tender_ai.gemini_model', 'gemini-1.5-flash')
        elif active_provider == 'azure':
            active_model = self.env['ir.config_parameter'].sudo().get_param('tender_ai.azure_deployment', 'gpt-4o')
        elif active_provider == 'mistral':
            active_model = self.env['ir.config_parameter'].sudo().get_param('tender_ai.mistral_model', 'mistral-large-latest')

        # 3. Upload and Generate
        try:
            uploaded = ai_service.upload_file(file_path, env=self.env)
            res = ai_service.generate([system_prompt, uploaded], env=self.env, max_retries=0)
            
            raw_text = res.get('text', '') if isinstance(res, dict) else str(res)
            usage = res.get('usage', {})
            p_tok = usage.get('promptTokens', 0)
            o_tok = usage.get('outputTokens', 0)
            
            # Clean JSON response
            json_str = raw_text.strip()
            if json_str.startswith('```json'):
                json_str = json_str.split('```json')[1].split('```')[0].strip()
            elif json_str.startswith('```'):
                json_str = json_str.split('```')[1].split('```')[0].strip()

            # --- Highlighting Logic ---
            import base64
            annotatated_pdf_content = False
            try:
                extracted_json = json.loads(json_str)
                annotatated_pdf_content = self._apply_pdf_highlights(file_path, extracted_json)
            except Exception as e:
                _logger.warning("Highlighting failed: %s", str(e))

            if not annotatated_pdf_content:
                with open(file_path, 'rb') as f:
                    annotatated_pdf_content = base64.b64encode(f.read())

            # Create Record with Stats
            Result = self.env['purple_ai.extraction_result']
            cost = Result._get_estimated_cost(res.get('provider'), res.get('model'), p_tok, o_tok)

            result = Result.create({
                'client_id': self.id,
                'filename': filename,
                'raw_response': raw_text,
                'extracted_data': json_str,
                'pdf_file': annotatated_pdf_content, 
                'pdf_filename': f"annotated_{filename}",
                'state': 'done',
                'provider': res.get('provider'),
                'model_used': res.get('model'),
                'duration_ms': res.get('durationMs', 0),
                'prompt_tokens': p_tok,
                'output_tokens': o_tok,
                'total_tokens': p_tok + o_tok,
                'cost': cost
            })
            
            # Auto-create the invoice processor record and run validations
            proc = self.env['purple_ai.invoice_processor'].create_from_extraction(result.id)
            failures = proc.action_validate() or []
            
            # If any validations failed, re-annotate the PDF in RED
            if failures:
                red_pdf = self._apply_pdf_highlights(file_path, json.loads(json_str), failures)
                if red_pdf:
                    result.write({'pdf_file': red_pdf})
            
            _logger.info("Successfully processed and auto-queued for accounting: %s", filename)

        except Exception as e:
            _logger.error("AI Error for %s: %s", filename, str(e))
            
            # Read file content for storage even on error
            import base64
            pdf_content = False
            try:
                with open(file_path, 'rb') as f:
                    pdf_content = base64.b64encode(f.read())
            except:
                pass

            self.env['purple_ai.extraction_result'].create({
                'client_id': self.id,
                'filename': filename,
                'pdf_file': pdf_content,
                'pdf_filename': filename,
                'state': 'error',
                'provider': active_provider,
                'model_used': active_model,
                'error_log': str(e)
            })

    def _apply_pdf_highlights(self, file_path, extracted_json, failures=None):
        """Uses fitz to draw highlights. Yellow for data, Red for failures."""
        if not fitz:
            _logger.warning("fitz (PyMuPDF) is not installed. Highlighting skipped.")
            return False
        
        failures = failures or []
        failed_fields = {f['field']: f['msg'] for f in failures}

        try:
            doc = fitz.open(file_path)
            for key, data in extracted_json.items():
                if not isinstance(data, dict):
                    continue
                
                box = data.get('box_2d')
                p_num = data.get('page_number')
                
                if box and len(box) == 4 and p_num:
                    page_idx = int(p_num) - 1
                    if 0 <= page_idx < len(doc):
                        page = doc[page_idx]
                        w, h = page.rect.width, page.rect.height
                        
                        # Gemini scale is 0-1000 [ymin, xmin, ymax, xmax]
                        ymin, xmin, ymax, xmax = box
                        fitz_rect = fitz.Rect(
                            xmin * w / 1000, 
                            ymin * h / 1000, 
                            xmax * w / 1000, 
                            ymax * h / 1000
                        )
                        
                        # Failure Check
                        is_failed = key in failed_fields
                        color = (1, 0, 0) if is_failed else (1, 1, 0) # Red if failed, Yellow otherwise
                        
                        # Add highlight
                        annot = page.add_highlight_annot(fitz_rect)
                        annot.set_colors(stroke=color)
                        if is_failed:
                            annot.set_info(content=failed_fields[key])
                        annot.update()

            # Save to buffer
            out = io.BytesIO()
            doc.save(out)
            doc.close()
            return base64.b64encode(out.getvalue())
        except Exception as e:
            _logger.error("Highlight rendering error: %s", str(e))
            return False
