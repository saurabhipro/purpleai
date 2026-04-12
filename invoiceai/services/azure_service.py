# -*- coding: utf-8 -*-
"""
azure_service.py
────────────────
Thin wrapper that forwards Azure AI calls to the centralized ai_core implementation.
"""

import logging
from odoo.addons.ai_core.services.azure_service import AzureService as _AzureService

_logger = logging.getLogger(__name__)

# Create a singleton instance for backward compatibility
_service = _AzureService()

def generate_with_azure(contents, model=None, temperature=0.1, env=None, max_retries=3):
    return _service.generate(contents, model=model, temperature=temperature, max_retries=max_retries, env=env)

def upload_file_to_azure(file_path, env=None, **kwargs):
    return _service.upload_file(file_path, env=env, **kwargs)

def list_available_models(env=None):
    return _service.list_models(env=env)

# Preserve original public API names if any other modules import them directly
generate = generate_with_azure
upload_file = upload_file_to_azure
list_models = list_available_models
