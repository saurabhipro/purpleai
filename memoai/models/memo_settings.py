# -*- coding: utf-8 -*-
# Memo AI settings have been deprecated. All AI configuration now lives in ai_core.settings.
# This file keeps compatibility fields so older/stale views do not crash.

from odoo import models, fields

class MemoAIResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'
    # Deprecated compatibility fields (not used by current UI).
    memo_ai_provider = fields.Selection(
        [('openai', 'OpenAI'), ('gemini', 'Google Gemini'), ('azure', 'Azure OpenAI')],
        string='Memo AI Provider (Deprecated)',
        config_parameter='memo_ai.provider',
        default='openai',
    )
    memo_ai_openai_api_key = fields.Char(string='Memo OpenAI API Key (Deprecated)', config_parameter='memo_ai.openai_api_key')
    memo_ai_openai_model = fields.Char(string='Memo OpenAI Model (Deprecated)', config_parameter='memo_ai.openai_model', default='gpt-4o')
    memo_ai_gemini_api_key = fields.Char(string='Memo Gemini API Key (Deprecated)', config_parameter='memo_ai.gemini_api_key')
    memo_ai_gemini_model = fields.Char(string='Memo Gemini Model (Deprecated)', config_parameter='memo_ai.gemini_model', default='gemini-2.5-flash')
    memo_ai_azure_api_key = fields.Char(string='Memo Azure API Key (Deprecated)', config_parameter='memo_ai.azure_api_key')
    memo_ai_azure_endpoint = fields.Char(string='Memo Azure Endpoint (Deprecated)', config_parameter='memo_ai.azure_endpoint')
    memo_ai_azure_deployment = fields.Char(string='Memo Azure Deployment (Deprecated)', config_parameter='memo_ai.azure_deployment')
    memo_ai_azure_embedding_deployment = fields.Char(
        string='Memo Azure Embedding Deployment (Deprecated)',
        config_parameter='memo_ai.azure_embedding_deployment',
        default='text-embedding-3-small',
    )
    memo_ai_azure_api_version = fields.Char(
        string='Memo Azure API Version (Deprecated)',
        config_parameter='memo_ai.azure_api_version',
        default='2024-12-01-preview',
    )
    memo_ai_use_local_embeddings = fields.Boolean(
        string='Memo Use Local Embeddings (Deprecated)',
        config_parameter='memo_ai.use_local_embeddings',
    )
    memo_ai_local_embedding_model = fields.Char(
        string='Memo Local Embedding Model (Deprecated)',
        config_parameter='memo_ai.local_embedding_model',
        default='sentence-transformers/all-MiniLM-L6-v2',
    )
    memo_ai_temperature = fields.Float(string='Memo Temperature (Deprecated)', config_parameter='memo_ai.temperature', default=0.3)
    memo_ai_max_tokens = fields.Integer(string='Memo Max Tokens (Deprecated)', config_parameter='memo_ai.max_tokens', default=4096)
    memo_ai_prompt_cost = fields.Float(string='Memo Prompt Cost (Deprecated)', config_parameter='memo_ai.prompt_cost', default=12.5)
    memo_ai_completion_cost = fields.Float(string='Memo Completion Cost (Deprecated)', config_parameter='memo_ai.completion_cost', default=50.0)
