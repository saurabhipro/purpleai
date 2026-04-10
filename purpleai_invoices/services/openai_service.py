# -*- coding: utf-8 -*-
"""
openai_service.py
────────────────
Thin wrapper that forwards OpenAI AI calls to the centralized ai_core implementation.
"""

import logging
from odoo.addons.ai_core.services.openai_service import OpenAIService as _OpenAIService

_logger = logging.getLogger(__name__)

# Singleton instance for backward compatibility
_service = _OpenAIService()

def generate_with_openai(contents, model=None, temperature=0.1, env=None, max_retries=3):
    return _service.generate(contents, model=model, temperature=temperature, max_retries=max_retries, env=env)

def upload_file_to_openai(file_path, env=None, **kwargs):
    return _service.upload_file(file_path, env=env, **kwargs)

def list_available_models(env=None):
    return _service.list_models(env=env)

# Preserve original public API names
generate = generate_with_openai
upload_file = upload_file_to_openai
list_models = list_available_models
