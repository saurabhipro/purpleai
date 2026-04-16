from odoo import models, fields, api, _
from odoo.exceptions import UserError
import json
import logging

_logger = logging.getLogger(__name__)


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
    ocr_method = fields.Selection([
        ('tesseract', 'Tesseract OCR'),
        ('paddle', 'Paddle OCR'),
        ('mistral', 'Mistral OCR'),
        ('none', 'No OCR Applied'),
    ], string='OCR Method', help='OCR engine used for text extraction')
    duration_ms = fields.Integer(string='AI Call Time (ms)', help='Time taken by AI API call only')
    total_processing_time_ms = fields.Integer(string='Total Processing Time (ms)', help='End-to-end processing time including OCR, AI call, and post-processing')
    processing_time_seconds = fields.Float(string='Processing Time (s)', compute='_compute_processing_time_seconds', store=True)
    prompt_tokens = fields.Integer(string='Prompt Tokens')
    output_tokens = fields.Integer(string='Output Tokens')
    total_tokens = fields.Integer(string='Total Tokens')
    cost = fields.Float(string='Estimated Cost ($)', digits=(12, 6))
    cost_inr = fields.Float(string='Estimated Cost (₹)', compute='_compute_cost_inr', store=True, digits=(12, 2))
    page_count = fields.Integer(string='Pages', default=0)
    pdf_dpi = fields.Integer(string='Source PDF DPI', help='Calculated DPI/resolution of the source PDF document')
    pdf_quality = fields.Selection([
        ('high', 'High Quality'),
        ('good', 'Good'),
        ('medium', 'Medium'),
        ('low', 'Low Quality'),
        ('unknown', 'Unknown'),
    ], string='PDF Quality', compute='_compute_pdf_quality', store=True, help='Quality classification based on source PDF DPI')
    quality_enhancements = fields.Char(string='Quality Enhancements', help='Dynamic OCR enhancements applied based on PDF quality')
    
    # Extraction completeness
    fields_extracted_percent = fields.Float(
        string='% Fields Extracted',
        compute='_compute_extraction_stats',
        store=True,
        help='Percentage of fields successfully extracted with values'
    )
    total_fields_count = fields.Integer(
        string='Total Fields',
        compute='_compute_extraction_stats',
        store=True
    )
    extracted_fields_count = fields.Integer(
        string='Extracted Fields',
        compute='_compute_extraction_stats',
        store=True
    )

    @api.depends('total_processing_time_ms')
    def _compute_processing_time_seconds(self):
        """Convert milliseconds to seconds for better readability."""
        for rec in self:
            rec.processing_time_seconds = (rec.total_processing_time_ms / 1000.0) if rec.total_processing_time_ms else 0.0

    @api.depends('cost')
    def _compute_cost_inr(self):
        """Convert USD cost to INR using exchange rate."""
        # USD to INR exchange rate (configurable via system parameter)
        exchange_rate = float(self.env['ir.config_parameter'].sudo().get_param('ai_core.usd_to_inr_rate', '85.0'))
        for rec in self:
            rec.cost_inr = rec.cost * exchange_rate if rec.cost else 0.0
    
    @api.depends('pdf_dpi')
    def _compute_pdf_quality(self):
        """Classify PDF quality based on DPI."""
        for rec in self:
            if not rec.pdf_dpi or rec.pdf_dpi == 0:
                rec.pdf_quality = 'unknown'
            elif rec.pdf_dpi >= 250:
                rec.pdf_quality = 'high'
            elif rec.pdf_dpi >= 200:
                rec.pdf_quality = 'good'
            elif rec.pdf_dpi >= 150:
                rec.pdf_quality = 'medium'
            else:
                rec.pdf_quality = 'low'

    @api.depends('extracted_data', 'pdf_quality')
    def _compute_extraction_stats(self):
        """Calculate extraction completeness based on fields with values.
        
        Rules for counting as extracted (HIT):
        - Boolean values (true/false, yes/no) count as valid extractions
        - Any non-empty value counts as extracted
        - Only placeholder values ("--", "N/A", etc.) count as MISS
        """
        for rec in self:
            if not rec.extracted_data:
                rec.fields_extracted_percent = 0.0
                rec.total_fields_count = 0
                rec.extracted_fields_count = 0
                rec._update_confidence_scores()
                continue
            
            try:
                data = json.loads(rec.extracted_data)
                total = len(data)
                extracted = 0
                
                # Placeholder values that indicate "not found" (count as MISS)
                placeholder_values = {
                    '--', '—', '–',  # Different dash types
                    'n/a', 'na', 'not applicable',
                    'not found', 'not available',
                    'none', 'null', 'nil',
                    '', ' ',  # Empty or whitespace
                }
                
                for key, val_data in data.items():
                    # Handle both old simple string format and new dict format
                    if isinstance(val_data, dict):
                        val = val_data.get('value', '')
                    else:
                        val = val_data
                    
                    # Convert to string for comparison
                    val_str = str(val).strip().lower()
                    
                    # Boolean values (true/false, yes/no) count as valid extractions
                    if isinstance(val, bool):
                        extracted += 1
                        continue
                    
                    # Check if it's a boolean string representation
                    if val_str in ('true', 'false', 'yes', 'no', '0', '1'):
                        extracted += 1
                        continue
                    
                    # Count as MISS only if it's a known placeholder
                    if val_str in placeholder_values:
                        continue  # This is a miss, don't increment extracted counter
                    
                    # If we have any other non-empty value, count it as extracted
                    if val_str:
                        extracted += 1
                
                rec.total_fields_count = total
                rec.extracted_fields_count = extracted
                rec.fields_extracted_percent = (extracted / total * 100) if total > 0 else 0.0
                
                # Debug logging for low extraction cases
                if rec.fields_extracted_percent < 50.0 and total > 0:
                    _logger.info("Low extraction rate for %s: %.1f%% (%d/%d fields), sample_data: %s",
                                rec.filename, rec.fields_extracted_percent, extracted, total, str(data)[:300])
                
            except Exception as e:
                _logger.error("Error computing extraction stats for %s: %s", rec.filename, str(e))
                rec.fields_extracted_percent = 0.0
                rec.total_fields_count = 0
                rec.extracted_fields_count = 0

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
        """
        Estimate cost based on configurable provider/model prices (per 1M tokens).
        
        Cost formula: (prompt_tokens / 1000000 * input_rate) + (output_tokens / 1000000 * output_rate)
        
        Examples:
        - Gemini (cheapest): 3000 input + 1000 output = (3000 × $0.075/1M) + (1000 × $0.30/1M) = $0.000525 USD (₹0.045)
        - Azure (40-60% cheaper than OpenAI): 3000 input + 1000 output = (3000 × $0.50/1M) + (1000 × $1.50/1M) = $0.002 USD (₹0.17)
        - OpenAI (most expensive): 3000 input + 1000 output = (3000 × $2.50/1M) + (1000 × $10.00/1M) = $0.015 USD (₹1.28)
        """
        provider = (provider or '').lower().strip()
        model = (model or '').lower().strip()
        
        # Get configurable rates from system parameters
        icp = self.env['ir.config_parameter'].sudo()
        
        if provider == 'gemini':
            input_rate = float(icp.get_param('ai_core.gemini_input_cost', '0.075') or '0.075')
            output_rate = float(icp.get_param('ai_core.gemini_output_cost', '0.30') or '0.30')
            
            # Override for Pro models (more expensive)
            if 'pro' in model:
                input_rate = max(input_rate, 1.25)  # at least 1.25 for Pro
                output_rate = max(output_rate, 5.00)
        
        elif provider == 'openai':
            # Check if mini model (cheaper) or standard (more expensive)
            if 'mini' in model:
                input_rate = 0.15 / 1000000
                output_rate = 0.60 / 1000000
            else:
                input_rate = float(icp.get_param('ai_core.openai_input_cost', '2.50') or '2.50')
                output_rate = float(icp.get_param('ai_core.openai_output_cost', '10.00') or '10.00')
        
        elif provider == 'azure':
            if 'mini' in model:
                input_rate = 0.15 / 1000000
                output_rate = 0.60 / 1000000
            else:
                input_rate = float(icp.get_param('ai_core.azure_input_cost', '0.50') or '0.50')
                output_rate = float(icp.get_param('ai_core.azure_output_cost', '1.50') or '1.50')
        
        elif provider == 'mistral':
            input_rate = 2.00 / 1000000
            output_rate = 6.00 / 1000000
        
        else:
            # Default to Gemini rates
            input_rate = float(icp.get_param('ai_core.gemini_input_cost', '0.075') or '0.075')
            output_rate = float(icp.get_param('ai_core.gemini_output_cost', '0.30') or '0.30')
        
        # Ensure rates are already per-token (divide by 1M if they're large numbers)
        # If user enters "0.075", it's $ per 1M tokens, so divide by 1M
        # If rates are already tiny like 0.000000075, don't divide again
        if input_rate > 0.001:  # Likely per-million-tokens
            input_rate = input_rate / 1000000
        if output_rate > 0.001:
            output_rate = output_rate / 1000000
        
        # Calculate total cost in USD
        cost = (prompt_tokens * input_rate) + (output_tokens * output_rate)
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
            'pending': Proc.search_count(proc_domain_company + ['|', '|',
                ('state', '=', 'failed'),
                ('approval_state', '=', 'rejected'),
                ('workflow_status', 'in', [
                    'hold_vrf_vendor_missing', 'hold_last_provision', 'hold_foreign_invoice', 'hold_advance_proforma',
                    'pending_vrf_field_mapping', 'gl_decision_in_progress', 'waiting_fa_schedule_update',
                    'waiting_prepaid_review'
                ])
            ]),
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
                # Also check processed subfolder where processed files are moved to
                proc_path = os.path.join(folder_path, 'processed', self.filename)
                if os.path.exists(proc_path):
                    _log.info("action_retry_extraction: found file in processed folder, rescanning %s", proc_path)
                    self._rescan_from_disk(proc_path)
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

            # Enqueue processing via queue_job if available; otherwise run inline.
            try:
                if hasattr(self.client_id, 'with_delay'):
                    # Pass existing record id so the job updates this record
                    self.client_id.with_delay()._process_file(temp_path, self.filename, self.id)
                else:
                    from odoo.addons.invoiceai.services.document_processing_service import process_document
                    process_document(self.env, self.client_id, temp_path, self.filename, existing_record=self)
            except Exception:
                # If enqueue fails, fall back to synchronous processing
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
