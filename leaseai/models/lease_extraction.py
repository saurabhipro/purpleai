import base64
import json
import logging
import tempfile

import requests
from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.addons.ai_core.services.ai_core_service import _get_ai_settings

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
    raw_response = fields.Text(string='Raw AI Response', readonly=True)
    error_log = fields.Text(string='Error Log', readonly=True)
    auto_extract_on_upload = fields.Boolean(string='Auto Extract on Upload', default=True)

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
            if active_rules:
                return "\n".join([f"{rule.rule_key}: {rule.instruction}" for rule in active_rules])
            if self.template_id.rules_text:
                return self.template_id.rules_text
        return ""

    @api.depends('extracted_json')
    def _compute_extracted_html(self):
        for rec in self:
            if not rec.extracted_json:
                rec.extracted_html = False
                continue
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

    def _extract_pdf_text(self, tmp_path):
        try:
            from PyPDF2 import PdfReader
            reader = PdfReader(tmp_path)
            chunks = [(p.extract_text() or '') for p in reader.pages[:20]]
            return "\n".join(chunks).strip()
        except Exception as e:
            _logger.warning("LeaseAI: PDF text extraction failed: %s", str(e))
            return ""

    def _call_ai(self, prompt):
        settings = _get_ai_settings(self.env)
        provider = (settings.get('provider') or 'openai').lower().strip()

        if provider == 'gemini':
            api_key = (settings.get('gemini_key') or '').strip()
            model = (settings.get('gemini_model') or 'gemini-2.5-flash').strip()
            if not api_key:
                raise UserError(_("Gemini API key is missing in AI Core settings."))
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": settings.get('temperature', 0.3)},
            }
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
                rec.state = 'done'
            except Exception as e:
                rec.state = 'error'
                rec.error_log = str(e)
                _logger.exception("Lease AI extraction failed")
                raise UserError(_("Extraction failed: %s") % str(e))

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
