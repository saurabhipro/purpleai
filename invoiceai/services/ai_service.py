# -*- coding: utf-8 -*-
"""Thin wrapper over AI Core.

Invoice **document extraction** must send the actual PDF/images to the provider.
The legacy ``call_ai`` path only posts plain text; using it with file paths in the
prompt breaks vision and produces hallucinated ``value`` / ``box_2d``. When
AI Core provider is **gemini**, we use ``GeminiService`` with real file uploads
(google-genai SDK), matching the pre-centralization behaviour.
"""

import logging
import os

from odoo.addons.ai_core.services.ai_core_service import (
    call_ai as _call_ai,
    get_embedding as _get_embedding,
    _get_ai_settings as _get_ai_settings,
)

_logger = logging.getLogger(__name__)


def _model_for_provider(settings, provider):
    """Human-readable model id stored on extraction rows + dashboard."""
    p = (provider or '').lower().strip()
    if p == 'gemini':
        return (settings.get('gemini_model') or '').strip() or None
    if p == 'openai':
        return (settings.get('openai_model') or '').strip() or None
    if p == 'azure':
        return (settings.get('azure_deployment') or '').strip() or None
    return None


def _normalize_call_ai_response(raw, settings, provider_key):
    """Memo/Core ``call_ai`` returns snake_case tokens and no provider/model.
    Match the dict shape from ``GeminiService._build_response`` for one downstream path."""
    if not isinstance(raw, dict):
        raw = {'text': str(raw)}
    pt = int(raw.get('prompt_tokens') or 0)
    ct = int(raw.get('completion_tokens') or 0)
    return {
        'text': raw.get('text') or '',
        'usage': {
            'promptTokens': pt,
            'outputTokens': ct,
            'totalTokens': int(raw.get('total_tokens') or (pt + ct)),
        },
        'provider': provider_key,
        'model': _model_for_provider(settings, provider_key) or '',
        'durationMs': int(raw.get('duration_ms') or 0),
    }


def _content_part_to_text(part):
    """Normalize one item from ``contents`` (dict message, plain str, or other)."""
    if isinstance(part, dict):
        return str(part.get('content', part))
    return str(part)


def _is_existing_file_path(part):
    if not isinstance(part, str):
        return False
    p = part.strip()
    return bool(p) and os.path.isfile(p)


def generate(
    contents,
    *,
    model=None,
    temperature=0.1,
    max_retries=3,
    provider=None,
    env=None,
    enforce_html=True,
):
    """Run a generation request.

    For **gemini**, ``contents`` may be a list mixing instruction strings and
    local file paths; paths are uploaded and sent as multimodal parts.

    For **openai** / **azure**, content is flattened to text and sent via Memo/Core
    (use null ``box_2d`` in extraction prompts when coordinates are unreliable).
    """
    settings = _get_ai_settings(env)
    resolved = (provider or settings.get('provider') or 'openai').lower().strip()

    if resolved == 'gemini':
        from odoo.addons.ai_core.services.gemini_service import GeminiService

        svc = GeminiService()
        parts = contents if isinstance(contents, list) else [contents]
        text_segments = []
        file_paths = []
        for part in parts:
            if _is_existing_file_path(part):
                file_paths.append(part.strip())
            else:
                text_segments.append(_content_part_to_text(part) if isinstance(part, dict) else str(part))
        prompt = '\n\n'.join(s for s in text_segments if s)
        uploaded = []
        for fp in file_paths:
            uploaded.append(svc.upload_file(fp, env=env))
        multimodal = [prompt] + uploaded if prompt else uploaded
        if not multimodal:
            raise ValueError('Gemini generate: empty contents (no text and no files).')
        gemini_model = model or (settings.get('gemini_model') or '').strip() or None
        temp = float(settings.get('temperature', temperature))
        return svc.generate(
            multimodal,
            model=gemini_model,
            temperature=temp,
            max_retries=max_retries,
            env=env,
        )

    if isinstance(contents, list):
        prompt = '\n'.join(_content_part_to_text(msg) for msg in contents)
    else:
        prompt = str(contents)
    raw = _call_ai(env, prompt, enforce_html=enforce_html)
    return _normalize_call_ai_response(raw, settings, resolved)


def upload_file(file_path: str, provider: str = None, env=None, **kwargs):
    """Return the path; ``generate`` uploads when provider is Gemini."""
    return file_path


def list_models(provider: str = None, env=None):
    _logger.debug('list_models called – not implemented in ai_core wrapper')
    return []


def get_service(provider: str = None, env=None):
    return None


def available_providers():
    return ['openai', 'gemini', 'azure']


def register_provider(name: str, cls):
    _logger.warning('register_provider called on wrapper – operation ignored')
