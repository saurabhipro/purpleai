import base64
import json
import logging
import tempfile
import os
import time

import requests
from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.addons.ai_core.services.ai_core_service import _get_ai_settings
from odoo.addons.invoiceai.services import ai_service
from odoo.addons.ai_core.services import ocr_service, box_refinement_service

_logger = logging.getLogger(__name__)


class LeaseExtractionTemplate(models.Model):
    _name = 'lease_ai.template'
    _description = 'Lease Extraction Template'
    _order = 'name'

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    description = fields.Char()
    rule_ids = fields.One2many('lease_ai.template.rule', 'template_id', string='Rules')
    rules_text = fields.Text(
        string='Extraction Rules (Compiled)',
        compute='_compute_rules_text',
        store=True,
    )

    @api.depends('rule_ids', 'rule_ids.sequence', 'rule_ids.rule_key', 'rule_ids.instruction', 'rule_ids.active')
    def _compute_rules_text(self):
        for rec in self:
            lines = []
            for rule in rec.rule_ids.sorted(key=lambda r: (r.sequence, r.id)):
                if rule.active:
                    lines.append(f"{rule.rule_key}: {rule.instruction}")
            rec.rules_text = "\n".join(lines)


class LeaseExtractionTemplateRule(models.Model):
    _name = 'lease_ai.template.rule'
    _description = 'Lease Extraction Template Rule'
    _order = 'sequence, id'

    sequence = fields.Integer(default=10)
    template_id = fields.Many2one('lease_ai.template', required=True, ondelete='cascade')
    rule_key = fields.Char(string='Rule ID', required=True)
    instruction = fields.Text(required=True)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('template_rule_key_uniq', 'unique(template_id, rule_key)', 'Rule ID must be unique per template.'),
    ]


class LeaseExtraction(models.Model):
    def _call_ai(self, prompt):
        """Call AI using the same AI Core configuration as invoiceai.
        
        Delegates to ai_service.generate() which handles all providers:
        Azure, OpenAI, Gemini, etc.
        """
        try:
            res = ai_service.generate(
                prompt,
                env=self.env,
                temperature=0.3,
                max_retries=1,
                enforce_html=False,
            )
            # Extract text from response (handles both string and dict responses)
            if isinstance(res, dict):
                return res.get('text', '')
            return str(res)
        except Exception as e:
            _logger.error("LeaseAI _call_ai failed: %s", str(e), exc_info=True)
            raise UserError(_("AI call failed: %s") % str(e))

    def _estimate_cost(self, prompt_text, response_text, provider='gpt-4o'):
        """Estimate cost based on tokens and model pricing.
        
        Pricing (as of 2024):
        - GPT-4o: $5/1M input, $15/1M output
        - GPT-4 Turbo: $10/1M input, $30/1M output
        - Azure GPT-4o: ~$6/1M input, $18/1M output
        - Gemini 1.5 Pro: $7.5/1M input, $30/1M output
        """
        # Simple token estimation: ~4 chars = 1 token
        input_tokens = len(prompt_text) // 4
        output_tokens = len(response_text) // 4
        
        # Default to GPT-4o pricing
        pricing = {
            'gpt-4o': {'input': 5.0 / 1e6, 'output': 15.0 / 1e6},
            'gpt-4-turbo': {'input': 10.0 / 1e6, 'output': 30.0 / 1e6},
            'azure': {'input': 6.0 / 1e6, 'output': 18.0 / 1e6},
            'gemini': {'input': 7.5 / 1e6, 'output': 30.0 / 1e6},
        }
        
        model_key = provider.lower()
        if 'azure' in model_key:
            model_key = 'azure'
        elif 'gemini' in model_key:
            model_key = 'gemini'
        elif 'turbo' in model_key:
            model_key = 'gpt-4-turbo'
        else:
            model_key = 'gpt-4o'
        
        rates = pricing.get(model_key, pricing['gpt-4o'])
        cost = (input_tokens * rates['input']) + (output_tokens * rates['output'])
        
        return input_tokens + output_tokens, cost

    def _extract_pdf_text(self, tmp_path):
        try:
            from PyPDF2 import PdfReader
            reader = PdfReader(tmp_path)
            chunks = [(p.extract_text() or '') for p in reader.pages[:20]]
            return "\n".join(chunks).strip()
        except Exception as e:
            _logger.warning("LeaseAI: PDF text extraction failed: %s", str(e))
            return ""
        
    @api.depends('extracted_json')
    def _compute_extracted_html(self):
            for rec in self:
                if rec.extracted_json:
                    try:
                        data = json.loads(rec.extracted_json)
                        rows = []
                        for k, v in data.items():
                            rows.append(
                                f"<tr><th class='bg-light' style='width:35%'>{k}</th><td>{v if v is not None else ''}</td></tr>"
                            )
                        rec.extracted_html = "<table class='table table-sm table-bordered'><tbody>%s</tbody></table>" % ''.join(rows)
                    except Exception:
                        rec.extracted_html = "<pre>%s</pre>" % (rec.extracted_json or '')
                else:
                    rec.extracted_html = ""

    @api.depends('extracted_json')
    def _compute_extracted_data(self):
        """Compute extracted_data field for ai_evidence_viewer widget.
        
        The ai_evidence_viewer expects JSON with structure:
        {
            "field_name": { "value": "...", "page_number": 1, "box_2d": [y0, x0, y1, x1] },
            ...
        }
        
        If extracted_json doesn't have box_2d, we parse it anyway since the viewer
        can search for text on the PDF and draw boxes.
        """
        for rec in self:
            if rec.extracted_json:
                try:
                    data = json.loads(rec.extracted_json)
                    # If data is flat (simple key-value), wrap each value with metadata
                    normalized = {}
                    for key, val in data.items():
                        if isinstance(val, dict) and 'value' in val:
                            # Already has structured format
                            normalized[key] = val
                        else:
                            # Wrap simple value with metadata
                            normalized[key] = {
                                'value': val,
                                'page_number': 1,
                                'box_2d': None,  # Will be searched for on PDF
                            }
                    rec.extracted_data = json.dumps(normalized)
                except Exception as e:
                    _logger.debug("Failed to compute extracted_data: %s", e)
                    rec.extracted_data = rec.extracted_json or ''
            else:
                rec.extracted_data = ''

    @api.depends('document_filename')
    def _compute_is_pdf(self):
        """Check if document is a PDF."""
        for rec in self:
            filename = (rec.document_filename or '').lower()
            rec.is_pdf = filename.endswith('.pdf')

    @api.depends('document_filename')
    def _compute_is_image(self):
        """Check if document is an image."""
        IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp', '.gif', '.webp'}
        for rec in self:
            filename = (rec.document_filename or '').lower()
            ext = '.' + filename.rsplit('.', 1)[-1] if '.' in filename else ''
            rec.is_image = ext in IMAGE_EXTS
    @api.depends('estimated_cost')
    def _compute_cost_inr(self):
        """Convert USD cost to INR using exchange rate from system parameters."""
        exchange_rate = float(self.env['ir.config_parameter'].sudo().get_param('ai_core.usd_to_inr_rate', '85.0') or '85.0')
        for rec in self:
            rec.estimated_cost_inr = rec.estimated_cost * exchange_rate if rec.estimated_cost else 0.0
    @api.depends('extracted_json')
    def _compute_page_count(self):
        """Extract page count from extracted_json if available."""
        for rec in self:
            rec.page_count = 0
            if rec.extracted_json:
                try:
                    data = json.loads(rec.extracted_json)
                    # Try common field names for page count
                    for key in ['num_pages', 'page_count', 'pages', 'total_pages']:
                        if key in data:
                            try:
                                rec.page_count = int(data[key])
                                break
                            except (ValueError, TypeError):
                                pass
                except Exception:
                    pass

    @api.depends('extracted_json')
    def _compute_lease_start_date(self):
        """Extract lease start date from extracted_json."""
        for rec in self:
            rec.lease_start_date = None
            if rec.extracted_json:
                try:
                    data = json.loads(rec.extracted_json)
                    # Try common field names for start date
                    for key in ['lease_start_date', 'lease_start', 'start_date', 'commencement_date']:
                        if key in data and data[key]:
                            try:
                                date_str = str(data[key]).strip()
                                # Try parsing as date
                                if len(date_str) >= 10:
                                    date_obj = fields.Date.to_date(date_str)
                                    rec.lease_start_date = date_obj
                                    break
                            except (ValueError, TypeError):
                                pass
                except Exception:
                    pass

    @api.depends('extracted_json')
    def _compute_lease_end_date(self):
        """Extract lease end date from extracted_json."""
        for rec in self:
            rec.lease_end_date = None
            if rec.extracted_json:
                try:
                    data = json.loads(rec.extracted_json)
                    # Try common field names for end date
                    for key in ['lease_end_date', 'lease_end', 'end_date', 'expiration_date', 'termination_date']:
                        if key in data and data[key]:
                            try:
                                date_str = str(data[key]).strip()
                                # Try parsing as date
                                if len(date_str) >= 10:
                                    date_obj = fields.Date.to_date(date_str)
                                    rec.lease_end_date = date_obj
                                    break
                            except (ValueError, TypeError):
                                pass
                except Exception:
                    pass

    @api.depends('extracted_json')
    def _compute_tenant_name(self):
        """Extract tenant name from extracted_json."""
        for rec in self:
            rec.tenant_name = ''
            if rec.extracted_json:
                try:
                    data = json.loads(rec.extracted_json)
                    # Try common field names for tenant
                    for key in ['tenant_name', 'tenant', 'lessee', 'occupant']:
                        if key in data and data[key]:
                            rec.tenant_name = str(data[key])[:64]
                            break
                except Exception:
                    pass

    @api.depends('extracted_json')
    def _compute_property_address(self):
        """Extract property address from extracted_json."""
        for rec in self:
            rec.property_address = ''
            if rec.extracted_json:
                try:
                    data = json.loads(rec.extracted_json)
                    # Try common field names for address
                    for key in ['property_address', 'address', 'premises', 'location']:
                        if key in data and data[key]:
                            rec.property_address = str(data[key])[:128]
                            break
                except Exception:
                    pass

    @api.depends('extracted_json')
    def _compute_rent_amount(self):
        """Extract rent amount from extracted_json."""
        for rec in self:
            rec.rent_amount = ''
            if rec.extracted_json:
                try:
                    data = json.loads(rec.extracted_json)
                    # Try common field names for rent
                    for key in ['rent_amount', 'rental_amount', 'rent', 'monthly_rent']:
                        if key in data and data[key]:
                            rec.rent_amount = str(data[key])[:32]
                            break
                except Exception:
                    pass


    _name = 'lease_ai.extraction'
    _description = 'Lease AI Extraction'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(required=True, default='New Lease Extraction', tracking=True)
    state = fields.Selection(
        [('draft', 'Draft'), ('processing', 'Processing'), ('done', 'Done'), ('error', 'Error')],
        default='draft',
        tracking=True,
    )
    document_file = fields.Binary(string='Lease Document', required=True, attachment=True)
    document_filename = fields.Char(string='Filename')
    template_id = fields.Many2one(
        'lease_ai.template',
        string='Extraction Template',
        default=lambda self: self._default_template_id(),
        tracking=True,
    )
    custom_prompt = fields.Text(
        string='Custom Prompt',
        help='Override template rules for this record only.',
    )
    extracted_json = fields.Text(string='Extracted JSON')
    extracted_html = fields.Html(string='Formatted Output', compute='_compute_extracted_html')
    extracted_data = fields.Text(string='Extracted Data (for evidence viewer)', compute='_compute_extracted_data')
    raw_response = fields.Text(string='Raw AI Response', readonly=True)
    error_log = fields.Text(string='Error Log', readonly=True)
    auto_extract_on_upload = fields.Boolean(string='Auto Extract on Upload', default=True)
    
    # Extraction metrics
    execution_time = fields.Float(string='Execution Time (sec)', readonly=True, help='Time taken for extraction in seconds')
    tokens_used = fields.Integer(string='Tokens Used', readonly=True, help='Total tokens consumed from AI provider')
    estimated_cost = fields.Float(string='Estimated Cost (USD)', readonly=True, digits=(12, 6), help='Estimated cost in USD')
    estimated_cost_inr = fields.Float(string='Estimated Cost (₹)', compute='_compute_cost_inr', store=True, digits=(12, 2), help='Estimated cost in INR')
    ai_provider = fields.Char(string='AI Provider', readonly=True, help='Provider used (azure, openai, gemini, etc.)')
    ai_model = fields.Char(string='AI Model', readonly=True, help='Specific model used')
    
    # Extracted lease fields (computed from extracted_json)
    page_count = fields.Integer(string='Pages', compute='_compute_page_count', help='Total pages in document')
    lease_start_date = fields.Date(string='Lease Start', compute='_compute_lease_start_date', help='Extracted lease start date')
    lease_end_date = fields.Date(string='Lease End', compute='_compute_lease_end_date', help='Extracted lease end date')
    tenant_name = fields.Char(string='Tenant', compute='_compute_tenant_name', help='Extracted tenant name')
    property_address = fields.Char(string='Property', compute='_compute_property_address', help='Extracted property address')
    rent_amount = fields.Char(string='Rent', compute='_compute_rent_amount', help='Extracted rent amount')
    
    # PDF viewer fields (aliases for document_file, for UI compatibility)
    pdf_file = fields.Binary(related='document_file', string='PDF File')
    pdf_filename = fields.Char(related='document_filename', string='PDF Filename')
    
    # PDF viewer state fields
    is_pdf = fields.Boolean(compute='_compute_is_pdf', string='Is PDF')
    is_image = fields.Boolean(compute='_compute_is_image', string='Is Image')

    @api.model
    def _default_template_id(self):
        template = self.env.ref('leaseai.lease_template_sample_v1', raise_if_not_found=False)
        if template:
            return template.id
        fallback = self.env['lease_ai.template'].search([('active', '=', True)], limit=1)
        return fallback.id if fallback else False

    @api.onchange('template_id')
    def _onchange_template_id(self):
        for rec in self:
            if rec.template_id and not rec.custom_prompt:
                rec.custom_prompt = rec.template_id.rules_text

    def _get_effective_prompt(self):
        self.ensure_one()
        if self.custom_prompt:
            return self.custom_prompt
        if self.template_id:
            active_rules = self.template_id.rule_ids.filtered('active').sorted(key=lambda r: (r.sequence, r.id))
            def action_extract(self):
                for rec in self:
                    rec.state = 'processing'
                    rec.error_log = False
                    rec.raw_response = False
                    rec.extracted_json = False

                    if not rec.document_file:
                        raise UserError(_("Please upload a lease document first."))
                    effective_prompt = rec._get_effective_prompt()
                    if not effective_prompt:
                        raise UserError(_("Please select a template or provide custom prompt rules."))

                    suffix = '.pdf'
                    if rec.document_filename and '.' in rec.document_filename:
                        suffix = '.' + rec.document_filename.rsplit('.', 1)[-1].lower()

                    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tf:
                        tf.write(base64.b64decode(rec.document_file))
                        tmp_path = tf.name

                    try:
                        doc_text = self._extract_pdf_text(tmp_path) if suffix == '.pdf' else ''
                        full_prompt = (
                            "You are a lease extraction assistant.\n"
                            "Return ONLY valid JSON without markdown fences.\n\n"
                            f"CUSTOM EXTRACTION INSTRUCTIONS:\n{effective_prompt}\n\n"
                            f"DOCUMENT TEXT:\n{doc_text[:120000]}"
                        )
                        try:
                            ai_text = rec._call_ai(full_prompt).strip()
                        except Exception as ai_exc:
                            rec.state = 'error'
                            rec.error_log = f"AI call failed: {str(ai_exc)}"
                            _logger.error("Lease AI extraction failed during AI call", exc_info=True)
                            continue
                        rec.raw_response = ai_text

                        # Normalize JSON response
                        cleaned = ai_text
                        if not cleaned:
                            rec.state = 'error'
                            rec.error_log = "AI provider returned an empty response. Check network, credentials, or quota."
                            _logger.error("Lease AI extraction failed: empty AI response.")
                            continue
                        if '```' in cleaned:
                            cleaned = cleaned.replace('```json', '').replace('```', '').strip()
                        start = cleaned.find('{')
                        end = cleaned.rfind('}')
                        if start != -1 and end > start:
                            cleaned = cleaned[start:end + 1]
                        try:
                            parsed = json.loads(cleaned)
                        except Exception as json_exc:
                            rec.state = 'error'
                            rec.error_log = f"JSON decode failed: {str(json_exc)}\nRaw AI response: {ai_text}"
                            _logger.error("Lease AI extraction failed: invalid JSON", exc_info=True)
                            continue
                        rec.extracted_json = json.dumps(parsed, indent=2, ensure_ascii=False)
                        rec.state = 'done'
                    except Exception as e:
                        rec.state = 'error'
                        rec.error_log = str(e)
                        _logger.error("Lease AI extraction failed", exc_info=True)
            res = requests.post(url, json=payload, headers={'Content-Type': 'application/json'}, timeout=120)
            if res.status_code != 200:
                raise UserError(_("Gemini error %s: %s") % (res.status_code, res.text))
            body = res.json()
            return body.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', '')

        if provider == 'azure':
            endpoint = (settings.get('azure_endpoint') or '').strip().rstrip('/')
            key = (settings.get('azure_key') or '').strip()
            deployment = (settings.get('azure_deployment') or '').strip()
            api_ver = (settings.get('azure_api_version') or '2024-12-01-preview').strip()
            if not endpoint or not key or not deployment:
                raise UserError(_("Azure credentials/deployment are missing in AI Core settings."))
            url = f"{endpoint}/openai/deployments/{deployment}/chat/completions?api-version={api_ver}"
            payload = {
                "messages": [{"role": "user", "content": prompt}],
                "temperature": settings.get('temperature', 0.3),
                "max_completion_tokens": settings.get('max_tokens', 4096),
            }
            res = requests.post(url, json=payload, headers={'api-key': key, 'Content-Type': 'application/json'}, timeout=120)
            if res.status_code != 200:
                raise UserError(_("Azure error %s: %s") % (res.status_code, res.text))
            return res.json().get('choices', [{}])[0].get('message', {}).get('content', '')

        # default openai
        api_key = (settings.get('openai_key') or '').strip()
        model = (settings.get('openai_model') or 'gpt-4o').strip()
        if not api_key:
            raise UserError(_("OpenAI API key is missing in AI Core settings."))
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": settings.get('temperature', 0.3),
            "max_completion_tokens": settings.get('max_tokens', 4096),
        }
        res = requests.post(
            'https://api.openai.com/v1/chat/completions',
            json=payload,
            headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
            timeout=120,
        )
        if res.status_code != 200:
            raise UserError(_("OpenAI error %s: %s") % (res.status_code, res.text))
        return res.json().get('choices', [{}])[0].get('message', {}).get('content', '')

    def action_extract(self):
        for rec in self:
            # Start execution timer
            start_time = time.time()
            
            rec.state = 'processing'
            rec.error_log = False
            rec.raw_response = False
            rec.extracted_json = False
            rec.execution_time = 0
            rec.tokens_used = 0
            rec.estimated_cost = 0.0
            rec.ai_provider = ''
            rec.ai_model = ''

            if not rec.document_file:
                raise UserError(_("Please upload a lease document first."))
            effective_prompt = rec._get_effective_prompt()
            if not effective_prompt:
                raise UserError(_("Please select a template or provide custom prompt rules."))

            suffix = '.pdf'
            if rec.document_filename and '.' in rec.document_filename:
                suffix = '.' + rec.document_filename.rsplit('.', 1)[-1].lower()

            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tf:
                tf.write(base64.b64decode(rec.document_file))
                tmp_path = tf.name

            # --- OCR fallback for image-based PDFs ---
            file_to_send = tmp_path
            temp_ocr_file = None
            if suffix == '.pdf':
                try:
                    is_searchable, text_count = ocr_service.check_pdf_searchability(tmp_path)
                    if not is_searchable:
                        _logger.info("LeaseAI: PDF '%s' is image-heavy (text_count=%d) -> applying OCR", rec.document_filename, text_count)
                        ocr_doc = ocr_service.apply_ocr_to_pdf(tmp_path, env=self.env)
                        if ocr_doc is not None:
                            temp_ocr_file = f"/tmp/ocr_{int(time.time())}_{rec.document_filename}"
                            ocr_doc.save(temp_ocr_file)
                            ocr_doc.close()
                            file_to_send = temp_ocr_file
                            _logger.info("LeaseAI: OCR'd PDF saved to temp: %s", temp_ocr_file)
                        else:
                            _logger.warning("LeaseAI: OCR failed, falling back to original PDF")
                    else:
                        _logger.info("LeaseAI: PDF '%s' is already searchable (text_count=%d)", rec.document_filename, text_count)
                except Exception as e:
                    _logger.warning("LeaseAI: Searchability check failed: %s, sending original PDF", e)

            try:
                doc_text = self._extract_pdf_text(file_to_send) if suffix == '.pdf' else ''
                full_prompt = (
                    "You are a lease extraction assistant.\n"
                    "Return ONLY valid JSON without markdown fences.\n\n"
                    f"CUSTOM EXTRACTION INSTRUCTIONS:\n{effective_prompt}\n\n"
                    f"DOCUMENT TEXT:\n{doc_text[:120000]}"
                )
                ai_text = rec._call_ai(full_prompt).strip()
                rec.raw_response = ai_text

                # Normalize JSON response
                cleaned = ai_text
                if '```' in cleaned:
                    cleaned = cleaned.replace('```json', '').replace('```', '').strip()
                start = cleaned.find('{')
                end = cleaned.rfind('}')
                if start != -1 and end > start:
                    cleaned = cleaned[start:end + 1]
                parsed = json.loads(cleaned)
                rec.extracted_json = json.dumps(parsed, indent=2, ensure_ascii=False)
                
                # Calculate execution metrics
                execution_time = time.time() - start_time
                tokens_used, estimated_cost = rec._estimate_cost(full_prompt, ai_text, 'gpt-4o')
                
                # Get AI provider info from settings
                settings = _get_ai_settings(self.env)
                provider = settings.get('provider', 'openai').lower()
                model = settings.get('openai_model', 'gpt-4o').strip() if provider == 'openai' else provider
                
                # Store metrics
                rec.execution_time = execution_time
                rec.tokens_used = tokens_used
                rec.estimated_cost = estimated_cost
                rec.ai_provider = provider
                rec.ai_model = model
                
                _logger.info("LeaseAI extraction completed: time=%.2fs, tokens=%d, cost=$%.4f, provider=%s", 
                            execution_time, tokens_used, estimated_cost, provider)
                
                rec.state = 'done'
            except Exception as e:
                # Calculate partial execution time even on error
                execution_time = time.time() - start_time
                rec.execution_time = execution_time
                rec.state = 'error'
                rec.error_log = str(e)
                _logger.exception("Lease AI extraction failed after %.2fs", execution_time)
                raise UserError(_("Extraction failed: %s") % str(e))
            finally:
                # Clean up temp OCR file if created
                if temp_ocr_file and os.path.exists(temp_ocr_file):
                    try:
                        os.remove(temp_ocr_file)
                        _logger.debug("LeaseAI: Cleaned up temp OCR file: %s", temp_ocr_file)
                    except Exception as e:
                        _logger.warning("LeaseAI: Could not remove temp OCR file %s: %s", temp_ocr_file, e)

        return True

    @api.model_create_multi
    def create(self, vals_list):
        default_template_id = self._default_template_id()
        for vals in vals_list:
            if not vals.get('template_id') and default_template_id:
                vals['template_id'] = default_template_id
            if not vals.get('custom_prompt') and vals.get('template_id'):
                template = self.env['lease_ai.template'].browse(vals['template_id'])
                if template.exists() and template.rules_text:
                    vals['custom_prompt'] = template.rules_text
        records = super().create(vals_list)
        for rec, vals in zip(records, vals_list):
            if vals.get('document_file') and rec.auto_extract_on_upload:
                rec.action_extract()
        return records

    def write(self, vals):
        res = super().write(vals)
        if vals.get('document_file'):
            for rec in self:
                if rec.auto_extract_on_upload and rec.state in ('draft', 'error', 'done'):
                    rec.action_extract()
        return res
