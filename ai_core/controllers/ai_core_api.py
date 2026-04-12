# -*- coding: utf-8 -*-
"""HTTP JSON API for external tools (e.g. Purple AI React UI).

Security:
- Set ``ai_core.react_dev_api_key`` (General Settings → AI Core) to a long random secret.
- Send header ``X-AI-Core-Dev-Key`` with that value from the React app, **or**
- Use the Vite dev proxy and an existing Odoo browser session (same browser profile).

If the dev key is empty, only authenticated Odoo sessions can call /settings and /chat.
"""
import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


def _sanitize_settings(settings):
    out = {}
    for key, val in settings.items():
        lk = key.lower()
        if any(x in lk for x in ('key', 'secret', 'password', 'token')):
            out[key] = '***' if val else ''
        else:
            out[key] = val
    return out


def _dispatch_chat(env, prompt, module='memoai'):
    """Run chat using provider implementations from specific modules."""
    from odoo.addons.ai_core.services.ai_core_service import _get_ai_settings
    settings = _get_ai_settings(env)
    
    if module == 'memoai':
        try:
            from odoo.addons.memoai.services import memo_ai_service as ms
            provider = (settings.get('provider') or 'openai').lower().strip()
            if provider == 'gemini':
                return ms.call_gemini(env, prompt, settings)
            if provider == 'azure':
                return ms.call_azure_openai(env, prompt, settings)
            return ms.call_openai(env, prompt, settings)
        except ImportError:
            raise RuntimeError("Module 'memoai' is not installed or accessible.")
            
    elif module == 'leaseai':
        try:
            from odoo.addons.leaseai.models.lease_extraction import LeaseExtraction
            # Implementation for lease chat/extraction if applicable
            # For now, let's assume it has a similar interface or return a placeholder
            return "Lease AI integration is active. (Extraction logic pending)"
        except ImportError:
            raise RuntimeError("Module 'leaseai' is not installed or accessible.")

    elif module == 'purpleai_invoices':
        try:
            # Placeholder for invoice specific logic
            return "Purple Invoices AI integration is active."
        except ImportError:
            raise RuntimeError("Module 'purpleai_invoices' is not installed or accessible.")

    else:
        # Default back to memoai or error
        raise RuntimeError(f"Unknown or unsupported module: {module}")


def _cors_headers():

    origin = request.httprequest.headers.get('Origin') or ''
    raw = request.env['ir.config_parameter'].sudo().get_param(
        'ai_core.react_cors_origins',
        'http://localhost:5173,http://127.0.0.1:5173',
    )
    allowed = {o.strip() for o in raw.split(',') if o.strip()}
    headers = []
    if origin and origin in allowed:
        headers.append(('Access-Control-Allow-Origin', origin))
        headers.append(('Access-Control-Allow-Credentials', 'true'))
    elif not origin:
        headers.append(('Access-Control-Allow-Origin', '*'))
    else:
        return []
    headers.extend(
        [
            ('Access-Control-Allow-Methods', 'GET, POST, OPTIONS'),
            ('Access-Control-Allow-Headers', 'Content-Type, X-AI-Core-Dev-Key'),
            ('Access-Control-Max-Age', '86400'),
        ]
    )
    return headers


def _json_response(payload, status=200):
    body = json.dumps(payload)
    h = [('Content-Type', 'application/json; charset=utf-8')]
    h.extend(_cors_headers())
    return request.make_response(body, headers=h, status=status)


def _options_response():
    return request.make_response('', headers=_cors_headers(), status=204)


def _parse_json_body():
    try:
        body = request.httprequest.get_json(force=False, silent=True)
        if isinstance(body, dict):
            return body
    except Exception:
        pass
    raw = request.httprequest.data
    if raw:
        try:
            return json.loads(raw.decode('utf-8'))
        except Exception:
            pass
    return {}


def _authorized_env():
    """Return (ok, env, error_message)."""
    ICP = request.env['ir.config_parameter'].sudo()
    expected = (ICP.get_param('ai_core.react_dev_api_key') or '').strip()
    header = (request.httprequest.headers.get('X-AI-Core-Dev-Key') or '').strip()

    if expected and header == expected:
        return True, request.env(su=True), ''

    if request.session.uid:
        return True, request.env, ''

    if not expected:
        return (
            False,
            None,
            'Configure "React UI dev API key" in Settings → General Settings → AI Core, '
            'or open Odoo in the same browser and log in (when using the dev proxy).',
        )
    return False, None, 'Invalid or missing X-AI-Core-Dev-Key header.'


class AICoreAPIController(http.Controller):
    @http.route('/ai_core/v1/ping', type='http', auth='none', methods=['GET', 'OPTIONS'], csrf=False)
    def ping(self, **_kwargs):
        if request.httprequest.method == 'OPTIONS':
            return _options_response()
        return _json_response({'ok': True, 'service': 'ai_core', 'version': 1})

    @http.route('/ai_core/v1/settings', type='http', auth='none', methods=['GET', 'OPTIONS'], csrf=False)
    def settings_summary(self, **_kwargs):
        if request.httprequest.method == 'OPTIONS':
            return _options_response()
        ok, env, err = _authorized_env()
        if not ok:
            return _json_response({'ok': False, 'error': err}, status=401)
        from odoo.addons.ai_core.services.ai_core_service import _get_ai_settings

        return _json_response({'ok': True, 'settings': _sanitize_settings(_get_ai_settings(env))})

    @http.route('/ai_core/v1/chat', type='http', auth='none', methods=['POST', 'OPTIONS'], csrf=False)
    def chat(self, **_kwargs):
        if request.httprequest.method == 'OPTIONS':
            return _options_response()
        ok, env, err = _authorized_env()
        if not ok:
            return _json_response({'ok': False, 'error': err}, status=401)

        body = _parse_json_body()
        prompt = (body.get('prompt') or '').strip()
        module = (body.get('module') or 'memoai').strip()
        
        if not prompt:
            return _json_response({'ok': False, 'error': 'prompt is required'}, status=400)

        try:
            result = _dispatch_chat(env, prompt, module=module)
            return _json_response({'ok': True, 'result': result})

        except Exception as exc:
            _logger.exception('ai_core/v1/chat failed')
            return _json_response({'ok': False, 'error': str(exc)}, status=500)
