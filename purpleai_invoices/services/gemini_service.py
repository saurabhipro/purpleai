# -*- coding: utf-8 -*-
"""
gemini_service.py
────────────────
Thin wrapper that forwards Gemini AI calls to the centralized ai_core implementation.
"""

import logging
from odoo.addons.ai_core.services.gemini_service import GeminiService as _GeminiService

_logger = logging.getLogger(__name__)

# Singleton instance for backward compatibility
_service = _GeminiService()

def generate_with_gemini(contents, model=None, temperature=0.1, env=None, max_retries=3):
    return _service.generate(contents, model=model, temperature=temperature, max_retries=max_retries, env=env)

def upload_file_to_gemini(file_path, wait_active=True, max_wait_sec=90, env=None, use_cache=True, **kwargs):
    return _service.upload_file(file_path, wait_active=wait_active, max_wait_sec=max_wait_sec, env=env, use_cache=use_cache, **kwargs)

def get_gemini_api_key(env=None):
    return _service.get_api_key(env=env)

def get_configured_model(env=None):
    return _service.get_model(env=env)

def _invalidate_model_cache():
    _service.invalidate_model_cache()

def list_available_models(env=None):
    return _service.list_models(env=env)

# Preserve original public API names
generate = generate_with_gemini
upload_file = upload_file_to_gemini
list_models = list_available_models
