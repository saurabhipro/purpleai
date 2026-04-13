from odoo import models, fields, api, _
from odoo.exceptions import UserError
import json

class ExtractionResult(models.Model):
    _name = 'purple_ai.extraction_result'
    _description = 'Processed Extraction Result'
    _order = 'create_date desc'

    client_id = fields.Many2one('purple_ai.client', string='Client', required=True, ondelete='cascade')
    company_id = fields.Many2one('res.company', string='Company', related='client_id.company_id', store=True, readonly=True)
    filename = fields.Char(string='File Name', required=True)
    
    state = fields.Selection([
        ('processing', 'Scanning...'),
        ('done', 'Success'),
        ('error', 'Error')
    ], string='Status', default='processing')
    
    extracted_data = fields.Text(string='Extracted JSON')
    data_html = fields.Html(string='Formatted View', compute='_compute_data_html')
    
    raw_response = fields.Text(string='Raw AI Response', readonly=True)
    error_log = fields.Text(string='Error Details', readonly=True)

    # Document preview fields
    pdf_file = fields.Binary(string='Document File', attachment=True)
    pdf_filename = fields.Char(string='Filename')
    total_pages = fields.Integer(string='Total Pages')
    
    is_pdf = fields.Boolean(compute='_compute_file_type', string='Is PDF')
    is_image = fields.Boolean(compute='_compute_file_type', string='Is Image')
    invoice_processor_id = fields.Many2one(
        'purple_ai.invoice_processor',
        string='Review Queue Record',
        compute='_compute_invoice_processor_id',
    )
    review_workflow_status = fields.Selection(
        selection=[
            ('draft_extracted', 'Draft Extracted'),
            ('hold_vrf_vendor_missing', 'Hold - Vendor Missing in VRF'),
            ('hold_last_provision', 'Hold - Move to Last Provisions'),
            ('hold_foreign_invoice', 'Hold - Foreign Invoice'),
            ('hold_advance_proforma', 'Hold - Move to Advance'),
            ('pending_vrf_field_mapping', 'Pending VRF Field Mapping'),
            ('gl_decision_in_progress', 'GL Decision In Progress'),
            ('waiting_fa_schedule_update', 'Waiting FA Schedule Update'),
            ('waiting_prepaid_review', 'Waiting Prepaid Review'),
            ('validation_passed', 'Validation Passed'),
            ('pending_manager_approval', 'Pending Manager Approval'),
            ('manager_approved', 'Manager Approved'),
            ('manager_rejected', 'Manager Rejected'),
            ('ready_for_tally', 'Ready for Tally'),
        ],
        string='Workflow Status',
        compute='_compute_review_statuses',
    )
    review_approval_state = fields.Selection(
        selection=[('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected')],
        string='Approval State',
        compute='_compute_review_statuses',
    )

    @api.depends('filename')
    def _compute_file_type(self):
        for rec in self:
            fn = (rec.filename or '').lower()
            rec.is_pdf = fn.endswith('.pdf')
            rec.is_image = any(fn.endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.webp', '.gif'])

    def _compute_invoice_processor_id(self):
        Proc = self.env['purple_ai.invoice_processor'].sudo()
        for rec in self:
            rec.invoice_processor_id = Proc.search([('extraction_result_id', '=', rec.id)], limit=1)

    def _compute_review_statuses(self):
        for rec in self:
            proc = rec.invoice_processor_id
            rec.review_workflow_status = proc.workflow_status if proc else False
            rec.review_approval_state = proc.approval_state if proc else False

    # Analytics Fields
    provider = fields.Char(string='AI Provider')
    model_used = fields.Char(string='AI Model')
    duration_ms = fields.Integer(string='Processing Time (ms)')
    prompt_tokens = fields.Integer(string='Prompt Tokens')
    output_tokens = fields.Integer(string='Output Tokens')
    total_tokens = fields.Integer(string='Total Tokens')
    cost = fields.Float(string='Estimated Cost ($)', digits=(12, 6))
    page_count = fields.Integer(string='Pages', default=0)

    @api.depends('extracted_data')
    def _compute_data_html(self):
        for rec in self:
            if not rec.extracted_data:
                rec.data_html = False
                continue
            try:
                data = json.loads(rec.extracted_data)
                html = '<table class="table table-sm table-hover border"><tbody>'
                for key, val_data in data.items():
                    # Handle both old simple string format and new dict format
                    if isinstance(val_data, dict):
                        val = val_data.get('value', '')
                        page = val_data.get('page_number')
                    else:
                        val = val_data
                        page = False

                    # Search/Verify Button
                    # Page Badge (Odoo 18 / Bootstrap 5 style)
                    page_badge = f'<span class="badge rounded-pill text-bg-info ms-2" style="font-size: 10px; vertical-align: middle;">Pg {page}</span>' if page else ''
                    
                    # Search/Verify Button - Using a more distinct style
                    search_term = str(val).replace("'", "\\'")
                    verify_btn = f'''<button class="btn btn-sm btn-outline-primary py-0 px-1 ms-2" 
                                     style="font-size: 11px; vertical-align: middle;"
                                     onclick="window.find && window.find('{search_term}')" 
                                     title="Find in document">
                                     <i class="fa fa-search"></i> Verify
                                     </button>'''
                    
                    html += f'''<tr>
                                <th class="bg-light text-muted" style="width: 35%; padding: 10px;">{key}</th>
                                <td style="padding: 10px;">
                                    <span style="font-size: 1.1em;">{val}</span>
                                    {page_badge}
                                    {verify_btn if val else ''}
                                </td>
                            </tr>'''
                html += '</tbody></table>'
                rec.data_html = html
            except:
                rec.data_html = f"<div class='alert alert-info py-2'>{rec.extracted_data}</div>"

    def action_process_invoice(self):
        self.ensure_one()
        proc = self.env['purple_ai.invoice_processor'].create_from_extraction(self.id)
        if not proc:
            raise UserError(_("Could not create or open the invoice queue row for this extraction."))
        proc.action_validate()
        return {
            'name': _('Invoice Detail'),
            'view_mode': 'form',
            'res_model': 'purple_ai.invoice_processor',
            'res_id': proc.id,
            'type': 'ir.actions.act_window',
            'context': self._context,
            'target': 'current'
        }

    def action_sync_invoice_queue_row(self):
        """Create or refresh the review queue row (for done extractions missing from the queue)."""
        done = self.filtered(lambda r: r.state == 'done')
        if not done:
            raise UserError(_("Only successful extractions (Status = Success) can be linked to the invoice queue."))
        Proc = self.env['purple_ai.invoice_processor']
        n = 0
        for rec in done:
            proc = Proc.create_from_extraction(rec.id)
            if proc:
                proc.action_validate()
                n += 1
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Invoice queue'),
                'message': _('Updated %s row(s) in Invoice Processing Queue.') % n,
                'type': 'success',
                'sticky': False,
            },
        }

    def _get_estimated_cost(self, provider, model, prompt_tokens, output_tokens):
        """Estimate cost based on current provider/model prices (as of 2024-2025)."""
        provider = (provider or '').lower()
        model = (model or '').lower()
        
        rates = {
            'gemini': {'input': 0.075 / 1000000, 'output': 0.30 / 1000000},  # default flash
            'openai': {'input': 2.50 / 1000000, 'output': 10.00 / 1000000},  # ~gpt-4o ballpark
            'azure': {'input': 2.50 / 1000000, 'output': 10.00 / 1000000},
            'mistral': {'input': 2.00 / 1000000, 'output': 6.00 / 1000000},
        }

        # Override specific models if known
        if 'pro' in model:
            rates['gemini'] = {'input': 1.25 / 1000000, 'output': 5.00 / 1000000}
        if 'mini' in model:
            rates['azure'] = {'input': 0.15 / 1000000, 'output': 0.60 / 1000000}
            rates['openai'] = {'input': 0.15 / 1000000, 'output': 0.60 / 1000000}

        config = rates.get(provider, rates['gemini'])
        cost = (prompt_tokens * config['input']) + (output_tokens * config['output'])
        return round(cost, 6)

    @api.model
    def get_dashboard_stats(self):
        """Unified API for the Owl Dashboard to fetch stats across all selected companies."""
        active_company_ids = self.env.companies.ids
        results = self.search([('company_id', 'in', active_company_ids)])

        from odoo.addons.ai_core.services.ai_core_service import _get_ai_settings

        ai = _get_ai_settings(self.env)
        active_provider = (ai.get('provider') or 'openai').lower()
        active_model = 'Unknown'
        if active_provider == 'gemini':
            active_model = (ai.get('gemini_model') or '').strip() or 'gemini-2.0-flash'
        elif active_provider == 'openai':
            active_model = (ai.get('openai_model') or '').strip() or 'gpt-4o'
        elif active_provider == 'azure':
            active_model = (ai.get('azure_deployment') or '').strip() or 'gpt-4o'
        elif active_provider == 'mistral':
            active_model = self.env['ir.config_parameter'].sudo().get_param(
                'tender_ai.mistral_model', 'mistral-large-latest'
            )

        inr_rate = 83.5
        latest_requests = []
        for reg in results.sorted('create_date', reverse=True)[:10]:
            latest_requests.append({
                'id': reg.id,
                'name': reg.filename or f"REQ-{reg.id}",
                'provider': (reg.provider or 'unknown').capitalize(),
                'model': reg.model_used or '—',
                'status': reg.state,
                'cost_inr': round(reg.cost * inr_rate, 2),
                'time': reg.create_date.strftime('%d %b, %H:%M'),
                'client_name': reg.client_id.name,
                'page_count': reg.page_count,
            })

        stats = {
            'active_info': {
                'provider': (active_provider or 'openai').upper(),
                'model': active_model,
                'company': ", ".join(self.env.companies.mapped('name')),
            },
            'total_clients': self.env['purple_ai.client'].search_count([('company_id', 'in', active_company_ids)]),
            'total_requests': len(results),
            'total_pages_processed': sum(results.mapped('page_count')),
            'invoice_buckets': {},
            'status_breakdown': {
                'success': len(results.filtered(lambda r: r.state == 'done')),
                'error': len(results.filtered(lambda r: r.state == 'error')),
            },
            'total_cost_usd': sum(results.mapped('cost')),
            'total_cost_inr': round(sum(results.mapped('cost')) * inr_rate, 2),
            'avg_time': round(sum(results.mapped('duration_ms')) / max(1, len(results)), 1),
            'providers': {},
            'latest': latest_requests
        }

        for provider in ['gemini', 'openai', 'azure', 'mistral']:
            prov_results = results.filtered(lambda r: (r.provider or '').lower() == provider)
            if not prov_results: continue
            
            stats['providers'][provider] = {
                'count': len(prov_results),
                'cost_inr': round(sum(prov_results.mapped('cost')) * inr_rate, 2),
                'avg_time': round(sum(prov_results.mapped('duration_ms')) / max(1, len(prov_results)), 1),
                'success_rate': round(len(prov_results.filtered(lambda r: r.state == 'done')) / len(prov_results) * 100, 1)
            }

        Proc = self.env['purple_ai.invoice_processor']
        proc_domain_company = [('company_id', 'in', active_company_ids)]
        stats['invoice_buckets'] = {
            'all': Proc.search_count(proc_domain_company),
            'pending': Proc.search_count(proc_domain_company + ['|', ('state', '=', 'failed'), ('workflow_status', 'in', [
                'pending_vrf_field_mapping', 'gl_decision_in_progress', 'waiting_fa_schedule_update',
                'waiting_prepaid_review', 'pending_manager_approval'
            ])]),
            'hold': Proc.search_count(proc_domain_company + [('workflow_status', 'in', [
                'hold_vrf_vendor_missing', 'hold_last_provision', 'hold_foreign_invoice', 'hold_advance_proforma'
            ])]),
            'validated': Proc.search_count(proc_domain_company + [('workflow_status', 'in', [
                'validation_passed', 'pending_manager_approval', 'manager_approved', 'ready_for_tally'
            ])]),
            'passed_tally': Proc.search_count(proc_domain_company + [('state', '=', 'posted')]),
            'rejected': Proc.search_count(proc_domain_company + ['|', ('workflow_status', '=', 'manager_rejected'), ('approval_state', '=', 'rejected')]),
        }
        
        return stats

    def action_retry_extraction(self):
        """Re-scan this record using the stored PDF binary. Overwrites the existing record."""
        self.ensure_one()
        import tempfile
        import os
        import base64
        import logging
        _logger = logging.getLogger(__name__)

        if not self.pdf_file:
            # If no stored PDF, try to find it in the client folder
            folder_path = self.client_id.folder_path
            if folder_path and self.filename:
                file_path = os.path.join(folder_path, self.filename)
                if os.path.exists(file_path):
                    self._rescan_from_disk(file_path)
                    return True
            raise UserError(_("No document source found to retry extraction. Please re-upload."))

        # Extract to temp file for processing service
        ext = os.path.splitext(self.filename)[1] or '.pdf'
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as temp:
            temp_path = temp.name
            temp.write(base64.b64decode(self.pdf_file))

        try:
            # Explicitly set state to processing so UI shows feedback
            self.write({'state': 'processing', 'error_log': False})
            self.env.cr.commit()

            from odoo.addons.invoiceai.services.document_processing_service import process_document
            process_document(self.env, self.client_id, temp_path, self.filename, existing_record=self)
        except Exception as e:
            _logger.error("action_retry_extraction failed: %s", str(e))
            self.write({'state': 'error', 'error_log': str(e)})
            raise UserError(_("Retry failed: %s") % str(e))
        finally:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass
        
        return True

    def _rescan_from_disk(self, file_path):
        """Re-extracts data from an on-disk file and UPDATES this record."""
        import logging
        _log = logging.getLogger(__name__)
        from odoo.addons.invoiceai.services.document_processing_service import process_document
        process_document(self.env, self.client_id, file_path, self.filename, existing_record=self)
