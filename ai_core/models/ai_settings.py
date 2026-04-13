# -*- coding: utf-8 -*-
"""AI Settings model for central configuration"""

from odoo import models, fields, _
from odoo.exceptions import UserError

class AISettings(models.TransientModel):
    _inherit = 'res.config.settings'
    _description = 'AI Core Settings'

    # Compatibility fields so shared settings views always render safely.
    purple_ai_root_path = fields.Char(config_parameter='purple_ai.root_path')
    tender_ai_input_cost = fields.Float(config_parameter='tender_ai.input_cost', default=12.5)
    tender_ai_output_cost = fields.Float(config_parameter='tender_ai.output_cost', default=50.0)
    tally_url = fields.Char(config_parameter='tender_ai.tally_url', default='http://localhost')
    tally_port = fields.Char(config_parameter='tender_ai.tally_port', default='9000')
    tally_company = fields.Char(config_parameter='tender_ai.tally_company')

    # Compatibility fields for Purple Invoices settings view rendering.
    # These prevent "field is undefined" UI errors when view/model load order changes.
    purple_ai_root_path = fields.Char(
        string='Root Folder Path (Compat)',
        config_parameter='purple_ai.root_path',
        default='/home/odoo18',
    )
    tender_ai_input_cost = fields.Float(
        string='Input Cost (Compat)',
        config_parameter='tender_ai.input_cost',
        default=12.5,
    )
    tender_ai_output_cost = fields.Float(
        string='Output Cost (Compat)',
        config_parameter='tender_ai.output_cost',
        default=50.0,
    )
    tally_url = fields.Char(
        string='Tally Host URL (Compat)',
        config_parameter='tender_ai.tally_url',
        default='http://localhost',
    )
    tally_port = fields.Char(
        string='Tally Port (Compat)',
        config_parameter='tender_ai.tally_port',
        default='9000',
    )
    tally_company = fields.Char(
        string='Tally Company Name (Compat)',
        config_parameter='tender_ai.tally_company',
    )

    provider = fields.Selection([
        ('openai', 'OpenAI'),
        ('gemini', 'Google Gemini'),
        ('azure', 'Azure OpenAI'),
    ], string='AI Core Provider', default='openai', config_parameter='ai_core.ai_provider')

    openai_key = fields.Char(
        string='AI Core OpenAI API Key',
        config_parameter='ai_core.openai_api_key',
        help='Create an API key in the OpenAI dashboard: https://platform.openai.com/api-keys',
    )
    openai_model = fields.Char(string='AI Core OpenAI Model', default='gpt-4o', config_parameter='ai_core.openai_model')

    gemini_key = fields.Char(
        string='AI Core Gemini API Key',
        config_parameter='ai_core.gemini_api_key',
        help='Create an API key in Google AI Studio: https://aistudio.google.com/app/apikey',
    )
    gemini_model = fields.Char(string='AI Core Gemini Model', default='gemini-2.5-flash', config_parameter='ai_core.gemini_model')

    azure_key = fields.Char(
        string='AI Core Azure API Key',
        config_parameter='ai_core.azure_api_key',
        help='From your Azure OpenAI resource (Keys and Endpoint) or Azure OpenAI Studio: https://oai.azure.com/',
    )
    azure_endpoint = fields.Char(string='Azure Endpoint', config_parameter='ai_core.azure_endpoint')
    azure_deployment = fields.Char(string='Azure Deployment', config_parameter='ai_core.azure_deployment')
    azure_embedding_deployment = fields.Char(
        string='Azure Embedding Deployment',
        default='text-embedding-3-small',
        config_parameter='ai_core.azure_embedding_deployment',
    )
    azure_embedding_endpoint = fields.Char(
        string='Azure Embedding Endpoint',
        config_parameter='ai_core.azure_embedding_endpoint',
        help='Optional dedicated endpoint for embedding deployment. Leave empty to use Azure Endpoint.',
    )
    azure_embedding_key = fields.Char(
        string='Azure Embedding API Key',
        config_parameter='ai_core.azure_embedding_api_key',
        help='Optional dedicated API key for embeddings. Leave empty to use Azure API Key.',
    )
    azure_api_version = fields.Char(
        string='Azure API Version',
        default='2024-12-01-preview',
        config_parameter='ai_core.azure_api_version',
    )

    use_local_embeddings = fields.Boolean(string='Use Local Embeddings', config_parameter='ai_core.use_local_embeddings')
    local_embedding_model = fields.Char(
        string='Local Embedding Model',
        default='sentence-transformers/all-MiniLM-L6-v2',
        config_parameter='ai_core.local_embedding_model',
    )

    temperature = fields.Float(string='Temperature', default=0.3, config_parameter='ai_core.temperature')
    max_tokens = fields.Integer(string='Max Tokens', default=4096, config_parameter='ai_core.max_tokens')
    prompt_cost = fields.Float(string='Prompt Cost (per 1M tokens)', default=12.5, config_parameter='ai_core.prompt_cost')
    completion_cost = fields.Float(
        string='Completion Cost (per 1M tokens)',
        default=50.0,
        config_parameter='ai_core.completion_cost',
    )

    react_dev_api_key = fields.Char(
        string='React UI Dev API Key',
        config_parameter='ai_core.react_dev_api_key',
        help='Shared secret for the Purple AI React dev UI (header X-AI-Core-Dev-Key). '
        'Leave empty only if you rely on an Odoo browser session via reverse proxy.',
    )
    react_cors_origins = fields.Char(
        string='React UI CORS Origins',
        default='http://localhost:5173,http://127.0.0.1:5173',
        config_parameter='ai_core.react_cors_origins',
        help='Comma-separated origins allowed for direct browser calls to /ai_core/v1/*. '
        'Not needed when the React app uses the Vite proxy (recommended).',
    )

    def action_test_ai_connection(self):
        """Test configured provider credentials and show sample response."""
        self.ensure_one()

        settings = {
            'provider': self.provider or 'openai',
            'openai_key': self.openai_key or '',
            'openai_model': self.openai_model or 'gpt-4o',
            'gemini_key': self.gemini_key or '',
            'gemini_model': self.gemini_model or 'gemini-2.5-flash',
            'azure_key': self.azure_key or '',
            'azure_endpoint': self.azure_endpoint or '',
            'azure_deployment': self.azure_deployment or '',
            'azure_api_version': self.azure_api_version or '2024-12-01-preview',
            'temperature': float(self.temperature or 0.3),
            'max_tokens': int(self.max_tokens or 4096),
            'prompt_cost': float(self.prompt_cost or 12.5),
            'completion_cost': float(self.completion_cost or 50.0),
        }
        provider = (settings.get('provider') or '').lower().strip()

        prompt = (
            "Connection test from Odoo AI Core settings. "
            "Reply in one short line: CONNECTED OK."
        )

        try:
            from odoo.addons.memoai.services.memo_ai_service import (
                call_openai, call_gemini, call_azure_openai,
            )
            if provider == 'gemini':
                result = call_gemini(self.env, prompt, settings=settings, enforce_html=False)
            elif provider == 'azure':
                result = call_azure_openai(self.env, prompt, settings=settings, enforce_html=False)
            else:
                result = call_openai(self.env, prompt, settings=settings, enforce_html=False)

            response_text = (result.get('text') or '').strip()
            if len(response_text) > 220:
                response_text = response_text[:220] + "..."

            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('AI Core Connection Successful'),
                    'message': _(
                        "Provider: %(provider)s | Tokens: %(tokens)s | Response: %(response)s",
                        provider=provider.upper(),
                        tokens=result.get('total_tokens', 0),
                        response=response_text or 'No text returned',
                    ),
                    'type': 'success',
                    'sticky': True,
                },
            }
        except Exception as e:
            raise UserError(_("AI connection test failed: %s") % str(e)) from e
