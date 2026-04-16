# -*- coding: utf-8 -*-
"""AI Core service utilities that delegate to Memo AI service for backward compatibility.
This module provides a thin wrapper so that other apps can import from ai_core.services
without duplicating logic.
"""

# Import the core functions from Memo AI service
# Lazy import to avoid circular dependency with memo_ai_service
def _load_memo_functions():
    from odoo.addons.memoai.services.memo_ai_service import (
        call_ai as _call_ai,
        get_embedding as _get_embedding,
        _get_ai_settings as _get_ai_settings_internal,
    )
    return _call_ai, _get_embedding, _get_ai_settings_internal

# Initialize placeholders (will be set on first call)
_call_ai = _get_embedding = _get_ai_settings_internal = None

def _ensure_loaded():
    """Load memo_ai_service functions lazily to break circular imports."""
    global _call_ai, _get_embedding, _get_ai_settings_internal
    if _call_ai is None:
        _call_ai, _get_embedding, _get_ai_settings_internal = _load_memo_functions()

def call_ai(env, prompt, enforce_html=True):
    """Delegate AI call to Memo AI service.
    This keeps a single source of truth for provider handling.

    ``enforce_html`` is passed through to Memo AI (False for JSON / structured output).
    """
    _ensure_loaded()
    return _call_ai(env, prompt, enforce_html=enforce_html)

def get_embedding(env, text):
    """Delegate embedding retrieval to Memo AI service."""
    _ensure_loaded()
    return _get_embedding(env, text)

def _get_ai_settings(env):
    """Retrieve AI settings using the ai_core configuration parameters.
    Mirrors Memo AI's settings but reads from ai_core config.
    """
    import logging
    _logger = logging.getLogger(__name__)
    
    # Settings are defined directly here; no need to call memo service.
    config = env['ir.config_parameter'].sudo()
    
    # Debug: Log all ai_core parameters (debug level only, not info)
    all_params = config.search([('key', 'like', 'ai_core.%')])
    _logger.debug("AI Core parameters in database: %s", 
                 {p.key: (p.value[:20] + '...' if p.value and len(p.value) > 20 else p.value) for p in all_params})
    
    azure_endpoint = config.get_param('ai_core.azure_endpoint', '')
    azure_embedding_endpoint = config.get_param('ai_core.azure_embedding_endpoint', '')
    
    # Fallback: Use embedding endpoint for chat if main endpoint not set
    if not azure_endpoint and azure_embedding_endpoint:
        azure_endpoint = azure_embedding_endpoint
        _logger.info("Using azure_embedding_endpoint as fallback for azure_endpoint: %s", azure_endpoint)
    
    settings = {
        'provider': config.get_param('ai_core.ai_provider', 'openai'),
        'openai_key': config.get_param('ai_core.openai_api_key', ''),
        'openai_model': config.get_param('ai_core.openai_model', 'gpt-4o'),
        'gemini_key': config.get_param('ai_core.gemini_api_key', ''),
        'gemini_model': config.get_param('ai_core.gemini_model', 'gemini-2.5-flash'),
        'azure_key': config.get_param('ai_core.azure_api_key', ''),
        'azure_endpoint': azure_endpoint,
        'azure_deployment': config.get_param('ai_core.azure_deployment', ''),
        'azure_embedding_deployment': config.get_param('ai_core.azure_embedding_deployment', 'text-embedding-3-small'),
        'azure_embedding_endpoint': azure_embedding_endpoint,
        'azure_embedding_key': config.get_param('ai_core.azure_embedding_api_key', ''),
        'azure_api_version': config.get_param('ai_core.azure_api_version', '2024-12-01-preview'),
        'use_local_embeddings': config.get_param('ai_core.use_local_embeddings', 'False') == 'True',
        'local_embedding_model': config.get_param('ai_core.local_embedding_model', 'sentence-transformers/all-MiniLM-L6-v2'),
        'temperature': float(config.get_param('ai_core.temperature', 0.3)),
        'max_tokens': int(config.get_param('ai_core.max_tokens', 4096)),
        'prompt_cost': float(config.get_param('ai_core.prompt_cost', 12.5)),
        'completion_cost': float(config.get_param('ai_core.completion_cost', 50.0)),
    }
    
    _logger.info("AI Core settings loaded: provider=%s, azure_endpoint=%s, azure_key_present=%s",
                 settings['provider'], settings['azure_endpoint'] or 'EMPTY', 'YES' if settings['azure_key'] else 'NO')
    
    return settings

# Export symbols for external use
__all__ = ['call_ai', 'get_embedding', '_get_ai_settings']
