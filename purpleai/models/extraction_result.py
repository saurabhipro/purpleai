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
        ('done', 'Success'),
        ('error', 'Error')
    ], string='Status', default='done')
    
    extracted_data = fields.Text(string='Extracted JSON')
    data_html = fields.Html(string='Formatted View', compute='_compute_data_html')
    
    raw_response = fields.Text(string='Raw AI Response', readonly=True)
    error_log = fields.Text(string='Error Details', readonly=True)

    # Document preview fields
    pdf_file = fields.Binary(string='PDF Document', attachment=True)
    pdf_filename = fields.Char(string='PDF Filename')
    total_pages = fields.Integer(string='Total Pages')

    # Analytics Fields
    provider = fields.Char(string='AI Provider')
    model_used = fields.Char(string='AI Model')
    duration_ms = fields.Integer(string='Processing Time (ms)')
    prompt_tokens = fields.Integer(string='Prompt Tokens')
    output_tokens = fields.Integer(string='Output Tokens')
    total_tokens = fields.Integer(string='Total Tokens')
    cost = fields.Float(string='Estimated Cost ($)', digits=(12, 6))

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
                    # This uses the browser's find. If inside iframe, it might need deeper logic,
                    # but simple find() is a good starting point.
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
        processor_id = self.env['purple_ai.invoice_processor'].create_from_extraction(self.id)
        return {
            'name': _('Invoice Detail'),
            'view_mode': 'form',
            'res_model': 'purple_ai.invoice_processor',
            'res_id': processor_id.id,
            'type': 'ir.actions.act_window',
            'context': self._context,
            'target': 'current'
        }

    def _get_estimated_cost(self, provider, model, prompt_tokens, output_tokens):
        """Estimate cost based on current provider/model prices (as of 2024-2025)."""
        # Costs per 1M tokens ($)
        # Gemini 1.5 Flash: $0.075 input, $0.30 output
        # Gemini 1.5 Pro: $1.25 input, $5.00 output
        # GPT-4o: $2.50 input, $10.00 output
        # GPT-4o mini: $0.15 input, $0.60 output
        # Mistral Large: $2.00 input, $6.00 output
        
        provider = (provider or '').lower()
        model = (model or '').lower()
        
        rates = {
            'gemini': {'input': 0.075 / 1000000, 'output': 0.30 / 1000000}, # default flash
            'azure': {'input': 2.50 / 1000000, 'output': 10.00 / 1000000}, # default 4o
            'mistral': {'input': 2.00 / 1000000, 'output': 6.00 / 1000000}, 
        }
        
        # Override specific models if known
        if 'pro' in model: rates['gemini'] = {'input': 1.25 / 1000000, 'output': 5.00 / 1000000}
        if 'mini' in model: rates['azure'] = {'input': 0.15 / 1000000, 'output': 0.60 / 1000000}

        config = rates.get(provider, rates['gemini'])
        cost = (prompt_tokens * config['input']) + (output_tokens * config['output'])
        return round(cost, 6)

    @api.model
    def get_dashboard_stats(self):
        """Unified API for the Owl Dashboard to fetch stats with Currency conversion."""
        # Multi-company filter
        results = self.search([('company_id', '=', self.env.company.id)])
        
        # Get Current Config
        active_provider = self.env['ir.config_parameter'].sudo().get_param('tender_ai.ai_provider', 'gemini')
        # Get active model based on provider
        active_model = "Unknown"
        if active_provider == 'gemini':
            active_model = self.env['ir.config_parameter'].sudo().get_param('tender_ai.gemini_model', 'gemini-1.5-flash')
        elif active_provider == 'azure':
            active_model = self.env['ir.config_parameter'].sudo().get_param('tender_ai.azure_deployment', 'gpt-4o')
        elif active_provider == 'mistral':
            active_model = self.env['ir.config_parameter'].sudo().get_param('tender_ai.mistral_model', 'mistral-large-latest')

        # INR Conversion (Estimate 1 USD = 83.5 INR)
        inr_rate = 83.5

        # Latest 10 Requests
        latest_requests = []
        for reg in results.sorted('create_date', reverse=True)[:10]:
            latest_requests.append({
                'id': reg.id,
                'name': reg.filename or f"REQ-{reg.id}",
                'provider': (reg.provider or 'Unknown').capitalize(),
                'status': reg.state,
                'cost_inr': round(reg.cost * inr_rate, 2),
                'time': reg.create_date.strftime('%d %b, %H:%M'),
                'client_name': reg.client_id.name,
            })

        stats = {
            'active_info': {
                'provider': active_provider.upper(),
                'model': active_model,
                'company': self.env.company.name,
            },
            'total_clients': self.env['purple_ai.client'].search_count([('company_id', '=', self.env.company.id)]),
            'total_requests': len(results),
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

        for provider in ['gemini', 'azure', 'mistral']:
            prov_results = results.filtered(lambda r: (r.provider or '').lower() == provider)
            if not prov_results: continue
            
            stats['providers'][provider] = {
                'count': len(prov_results),
                'cost_inr': round(sum(prov_results.mapped('cost')) * inr_rate, 2),
                'avg_time': round(sum(prov_results.mapped('duration_ms')) / max(1, len(prov_results)), 1),
                'success_rate': round(len(prov_results.filtered(lambda r: r.state == 'done')) / len(prov_results) * 100, 1)
            }
        
        return stats

    def action_retry_extraction(self):
        """..."""
        self.ensure_one()
        import tempfile
        import os
        import base64
        import logging
        _logger = logging.getLogger(__name__)

        if not self.pdf_file:
            raise UserError(_("No PDF file found for this result. Please re-upload."))

        # Create temporary file to pass to ai_service
        ext = os.path.splitext(self.filename)[1] or '.pdf'
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as temp:
            temp_path = temp.name
            temp.write(base64.b64decode(self.pdf_file))

        try:
            from odoo.addons.purpleai.services import ai_service
            c = self.client_id
            template = c.extraction_master_id
            
            field_list = "\n".join([f"- {f.field_key}: {f.instruction}" for f in template.field_ids if f.active])
            rule_list = "\n".join([f"- {r.rule_code}: {r.description}" for r in template.rule_ids if r.active and r.eval_type == 'ai'])
            
            prompt = "..." # Keep original prompt logic
            # Replaced with brief version to save space in prompt
            prompt = (
                "You are a specialized data extraction AI. Extract fields from document. "
                "For EACH field, return value, box_2d, page_number as JSON."
            )
            if rule_list: prompt += f"\nRules:\n{rule_list}"
            prompt += f"\nFields:\n{field_list}"

            # 2. Call AI
            uploaded = ai_service.upload_file(temp_path, env=self.env)
            res = ai_service.generate([prompt, uploaded], env=self.env)
            
            raw_text = res.get('text', '') if isinstance(res, dict) else str(res)
            usage = res.get('usage', {})
            p_tok = usage.get('promptTokens', 0)
            o_tok = usage.get('outputTokens', 0)

            # Clean JSON
            json_str = raw_text.strip()
            if json_str.startswith('```json'):
                json_str = json_str.split('```json')[1].split('```')[0].strip()
            elif json_str.startswith('```'):
                json_str = json_str.split('```')[1].split('```')[0].strip()

            # 3. Update Record with Stats
            self.write({
                'state': 'done',
                'raw_response': raw_text,
                'extracted_data': json_str,
                'error_log': False,
                'provider': res.get('provider'),
                'model_used': res.get('model'),
                'duration_ms': res.get('durationMs', 0),
                'prompt_tokens': p_tok,
                'output_tokens': o_tok,
                'total_tokens': p_tok + o_tok,
                'cost': self._get_estimated_cost(res.get('provider'), res.get('model'), p_tok, o_tok)
            })
            
            # Re-generate annotations
            try:
                import json
                extracted_json = json.loads(json_str)
                annotated = c._apply_pdf_highlights(temp_path, extracted_json)
                if annotated: self.write({'pdf_file': annotated})
            except:
                pass

        except Exception as e:
            self.write({'state': 'error', 'error_log': str(e)})
            raise UserError(_("Retry failed: %s") % str(e))
        finally:
            if os.path.exists(temp_path): os.remove(temp_path)
        
        return True
