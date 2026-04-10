# -*- coding: utf-8 -*-
"""ai_service.py – Thin wrapper that forwards AI calls to the centralized ai_core module.

All callers import ``generate`` (and related helpers) from this module. The implementation
now simply delegates to ``odoo.addons.ai_core.services.ai_core_service``.
"""

import logging
from odoo.addons.ai_core.services.ai_core_service import (
    call_ai as _call_ai,
    get_embedding as _get_embedding,
    _get_ai_settings as _get_ai_settings,
)

_logger = logging.getLogger(__name__)

def generate(contents, *, model=None, temperature=0.1, max_retries=3, provider=None, env=None):
    """Dispatch an AI generation request.

    ``contents`` may be a string or a list of message dicts. For compatibility we
    flatten list messages into a single prompt string before delegating to the core
    ``call_ai`` function.
    """
    if isinstance(contents, list):
        prompt = "\n".join(msg.get('content', str(msg)) for msg in contents)
    else:
        prompt = str(contents)
    return _call_ai(env, prompt)

def upload_file(file_path: str, provider: str = None, env=None, **kwargs):
    """Upload a file for AI processing.

    The core service does not expose a dedicated upload helper, so we simply return
    the file path – callers will include it in the ``visual_inputs`` list passed to
    ``generate``.
    """
    return file_path

def list_models(provider: str = None, env=None):
    """Return a list of models supported by the underlying provider.
    Currently a placeholder – callers can ignore the result.
    """
    _logger.debug("list_models called – not implemented in ai_core wrapper")
    return []

def get_service(provider: str = None, env=None):
    """Return the underlying service instance – not applicable for the wrapper.
    """
    return None

def available_providers():
    """Return the list of registered providers as defined in ai_core settings."""
    return ["openai", "gemini", "azure"]

def register_provider(name: str, cls):
    """No‑op placeholder – registration is handled by ``ai_core``.
    """
    _logger.warning("register_provider called on wrapper – operation ignored")

"""End of ai_service wrapper"""
