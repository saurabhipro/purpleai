# -*- coding: utf-8 -*-
"""
mistral_service.py
────────────────
Thin wrapper that forwards Mistral AI calls to the centralized ai_core implementation.
"""

import logging
from odoo.addons.ai_core.services.mistral_service import MistralService as _MistralService

_logger = logging.getLogger(__name__)

# Singleton instance for backward compatibility
_service = _MistralService()

def generate_with_mistral(contents, model=None, temperature=0.1, env=None, max_retries=3):
    return _service.generate(contents, model=model, temperature=temperature,
                             max_retries=max_retries, env=env)

def upload_file_to_mistral(file_path, env=None, **kwargs):
    return _service.upload_file(file_path, env=env, **kwargs)

def list_available_models(env=None):
    return _service.list_models(env=env)

# Preserve original public API names
generate = generate_with_mistral
upload_file = upload_file_to_mistral
list_models = list_available_models
