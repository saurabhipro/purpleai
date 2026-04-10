# -*- coding: utf-8 -*-
"""AI Settings model for central configuration"""

from odoo import models, fields

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

    openai_key = fields.Char(string='AI Core OpenAI API Key', config_parameter='ai_core.openai_api_key')
    openai_model = fields.Char(string='AI Core OpenAI Model', default='gpt-4o', config_parameter='ai_core.openai_model')

    gemini_key = fields.Char(string='AI Core Gemini API Key', config_parameter='ai_core.gemini_api_key')
    gemini_model = fields.Char(string='AI Core Gemini Model', default='gemini-2.5-flash', config_parameter='ai_core.gemini_model')

    azure_key = fields.Char(string='AI Core Azure API Key', config_parameter='ai_core.azure_api_key')
    azure_endpoint = fields.Char(string='Azure Endpoint', config_parameter='ai_core.azure_endpoint')
    azure_deployment = fields.Char(string='Azure Deployment', config_parameter='ai_core.azure_deployment')
    azure_embedding_deployment = fields.Char(
        string='Azure Embedding Deployment',
        default='text-embedding-3-small',
        config_parameter='ai_core.azure_embedding_deployment',
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
