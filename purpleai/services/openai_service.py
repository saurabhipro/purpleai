# -*- coding: utf-8 -*-
"""
openai_service.py
─────────────────
OpenAI GPT provider, implements BaseAIService.

Reads configuration from Odoo system parameters:
    tender_ai.openai_api_key
    tender_ai.openai_default_model

Supported models:
    gpt-4o, gpt-4o-mini, gpt-4-turbo, gpt-4, gpt-3.5-turbo, etc.

API reference: https://platform.openai.com/docs/api-reference/chat
"""

import time
import logging
import requests
from typing import Any, Dict, List, Optional

from .base_ai_service import BaseAIService

try:
    from odoo import _  # type: ignore
except ImportError:
    _ = lambda x: x  # noqa: E731  (standalone / test use)

_logger = logging.getLogger(__name__)

OPENAI_API_BASE = "https://api.openai.com/v1"


class OpenAIService(BaseAIService):
    """
    OpenAI GPT provider.

    Calls the OpenAI Chat Completions API:
        POST https://api.openai.com/v1/chat/completions
    """

    PROVIDER = "openai"

    # ------------------------------------------------------------------
    # BaseAIService contract
    # ------------------------------------------------------------------

    def generate(
        self,
        contents: Any,
        *,
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_retries: int = 3,
        env=None,
    ) -> Dict[str, Any]:
        """
        Call the OpenAI chat/completions endpoint.

        ``model`` overrides the model from settings when provided.
        """
        if not env:
            raise ValueError("Odoo Environment (env) is required for OpenAI service.")

        api_key = self._get_param(env, "tender_ai.openai_api_key", "")
        chosen_model = model or self._get_param(
            env, "tender_ai.openai_default_model", "gpt-4o-mini"
        )

        if not api_key:
            raise RuntimeError(
                _("OpenAI configuration is incomplete (API Key is missing).")
            )

        url = f"{OPENAI_API_BASE}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        raw_messages = self._normalise_messages(contents)
        messages = []

        for msg in raw_messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            # Already a list (multi-modal content)? Use it as-is.
            if isinstance(content, list):
                messages.append({"role": role, "content": content})
                continue

            # Handle file proxies (images / documents)
            if isinstance(contents, list) and role == "user":
                parts = []
                for item in contents:
                    if isinstance(item, dict) and item.get("type") == "file_proxy":
                        mime = item.get("mime_type", "")
                        if "image" in mime:
                            parts.append({
                                "type": "image_url",
                                "image_url": {"url": item.get("url")},
                            })
                        else:
                            # For PDFs/documents — send as image_url if it's a data-URL
                            parts.append({
                                "type": "image_url",
                                "image_url": {"url": item.get("url")},
                            })
                    elif isinstance(item, str):
                        parts.append({"type": "text", "text": item})

                if parts:
                    messages.append({"role": role, "content": parts})
                    continue

            messages.append({"role": role, "content": content})

        payload = {
            "model": chosen_model,
            "messages": messages,
            "temperature": temperature,
        }

        last_err: Optional[Exception] = None
        for attempt in range(max_retries + 1):
            self._retry_sleep(attempt)
            try:
                t0 = time.time()
                resp = requests.post(url, headers=headers, json=payload, timeout=60)
                duration_ms = int((time.time() - t0) * 1000)

                if resp.status_code == 429:
                    # Distinguish billing quota exhausted (non-retryable)
                    # from real rate-limiting (retryable)
                    try:
                        err_code = resp.json().get("error", {}).get("code", "")
                    except Exception:
                        err_code = ""

                    if err_code == "insufficient_quota":
                        raise RuntimeError(
                            _(
                                "OpenAI quota exhausted: Your account has no remaining credits. "
                                "Please add billing credits at "
                                "https://platform.openai.com/settings/organization/billing"
                            )
                        )

                    # Real rate-limit — retry with back-off
                    if attempt >= max_retries:
                        raise RuntimeError(f"OpenAI rate-limited: {resp.text}")
                    _logger.warning(
                        "OPENAI API: rate-limited (429), attempt %d/%d", attempt, max_retries
                    )
                    last_err = RuntimeError(f"OpenAI rate-limited: {resp.text}")
                    time.sleep(5)
                    continue


                if resp.status_code != 200:
                    _logger.error("OPENAI API: error %s – %s", resp.status_code, resp.text)
                    raise RuntimeError(
                        _("OpenAI returned error %s: %s") % (resp.status_code, resp.text)
                    )

                data = resp.json()
                text = data["choices"][0]["message"]["content"]
                raw_usage = data.get("usage", {})
                usage = {
                    "promptTokens": raw_usage.get("prompt_tokens", 0),
                    "outputTokens": raw_usage.get("completion_tokens", 0),
                    "totalTokens": raw_usage.get("total_tokens", 0),
                }
                return self._build_response(
                    text=text,
                    model=chosen_model,
                    provider=self.PROVIDER,
                    duration_ms=duration_ms,
                    usage=usage,
                )

            except requests.exceptions.Timeout:
                _logger.warning("OPENAI API: request timed out (attempt %d)", attempt)
                last_err = RuntimeError("OpenAI request timed out.")
            except RuntimeError:
                raise
            except Exception as exc:
                _logger.exception("OPENAI API: unexpected error")
                last_err = exc

        raise RuntimeError(
            _("OpenAI call failed after %d attempts: %s") % (max_retries + 1, last_err)
        )

    def list_models(self, env=None) -> List[str]:
        """Fetch available GPT models from the OpenAI API."""
        if not env:
            return _DEFAULT_MODELS

        api_key = self._get_param(env, "tender_ai.openai_api_key", "")
        if not api_key:
            return _DEFAULT_MODELS

        try:
            resp = requests.get(
                f"{OPENAI_API_BASE}/models",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10,
            )
            if resp.status_code == 200:
                models = resp.json().get("data", [])
                gpt_models = sorted(
                    [m["id"] for m in models if m["id"].startswith("gpt-")],
                    reverse=True,
                )
                return gpt_models or _DEFAULT_MODELS
        except Exception as exc:
            _logger.warning("OPENAI: could not fetch model list: %s", exc)

        return _DEFAULT_MODELS

    def upload_file(self, file_path: str, env=None, **kwargs) -> Dict[str, Any]:
        """
        Return a base64 Data URL proxy for GPT-4 Vision / GPT-4o.
        OpenAI vision models accept files inline via base64 data URLs.
        """
        return self._file_to_base64_data_url(file_path)


# ── Default model list (used as fallback) ─────────────────────────────────────

_DEFAULT_MODELS = [
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-4-turbo",
    "gpt-4",
    "gpt-3.5-turbo",
]


# ════════════════════════════════════════════════════════════════════════════
# Singleton & backward-compatible module-level function
# ════════════════════════════════════════════════════════════════════════════

_service = OpenAIService()


def generate_with_openai(
    contents: Any,
    model: str = None,
    temperature: float = 0.1,
    env=None,
    max_retries: int = 3,
) -> Dict[str, Any]:
    """
    Backward-compatible wrapper around OpenAIService.generate().

    Example::

        from odoo.addons.purpleai.services.openai_service import generate_with_openai

        result = generate_with_openai(
            contents="Summarise this contract.",
            model="gpt-4o",
            env=self.env,
        )
        text = result["text"]
    """
    return _service.generate(
        contents,
        model=model,
        temperature=temperature,
        max_retries=max_retries,
        env=env,
    )
