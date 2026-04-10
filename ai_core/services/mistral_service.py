# -*- coding: utf-8 -*-
"""
mistral_service.py
────────────────
Mistral AI provider, implements BaseAIService. Centralized version for ai_core.
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

_MISTRAL_API_URL = "https://api.mistral.ai/v1/chat/completions"
_DEFAULT_MODEL = "mistral-large-latest"


class MistralService(BaseAIService):
    """Mistral AI provider.

    Calls the Mistral chat‑completions endpoint with Bearer token auth.
    """

    PROVIDER = "mistral"

    def generate(
        self,
        contents: Any,
        *,
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_retries: int = 3,
        env=None,
    ) -> Dict[str, Any]:
        if not env:
            raise ValueError("Odoo Environment (env) is required for Mistral AI service.")

        api_key = self._get_param(env, "tender_ai.mistral_api_key", "")
        if not api_key:
            raise RuntimeError(_("Mistral API Key is missing. Please configure it in Purple AI Settings."))

        resolved_model = (
            model
            or self._get_param(env, "tender_ai.mistral_default_model", "")
            or _DEFAULT_MODEL
        )

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        # Normalise messages (supports multi‑modal lists)
        raw_messages = self._normalise_messages(contents)
        messages = []
        for msg in raw_messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if isinstance(content, list):
                parts = []
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "file_proxy":
                        parts.append({"type": "image_url", "image_url": {"url": item.get("url")}})
                    elif isinstance(item, (str, int, float)):
                        parts.append({"type": "text", "text": str(item)})
                if parts:
                    messages.append({"role": role, "content": parts})
                else:
                    messages.append({"role": role, "content": str(content)})
                continue
            messages.append({"role": role, "content": content})

        payload = {
            "model": resolved_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 4096,
        }

        # Enable JSON mode for appropriate models
        all_text = str(contents).lower()
        if "json" in all_text and ("large" in resolved_model or "small" in resolved_model or "pixtral" in resolved_model):
            payload["response_format"] = {"type": "json_object"}

        last_err: Optional[Exception] = None
        for attempt in range(max_retries + 1):
            self._retry_sleep(attempt)
            try:
                t0 = time.time()
                resp = requests.post(_MISTRAL_API_URL, headers=headers, json=payload, timeout=60)
                duration_ms = int((time.time() - t0) * 1000)

                if resp.status_code == 429:
                    if attempt >= max_retries:
                        raise RuntimeError(f"Mistral rate-limited: {resp.text}")
                    sleep_time = min(5 * (attempt + 1), 60)
                    _logger.warning("MISTRAL API: rate-limited (429), attempt %d/%d. Waiting %ds...", attempt, max_retries, sleep_time)
                    last_err = RuntimeError(f"Mistral rate-limited: {resp.text}")
                    time.sleep(sleep_time)
                    continue

                if resp.status_code != 200:
                    _logger.error("MISTRAL API: error %s – %s", resp.status_code, resp.text)
                    raise RuntimeError(_("Mistral AI returned error %s: %s") % (resp.status_code, resp.text))

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
                    model=resolved_model,
                    provider=self.PROVIDER,
                    duration_ms=duration_ms,
                    usage=usage,
                )
            except requests.exceptions.Timeout:
                _logger.warning("MISTRAL API: request timed out (attempt %d)", attempt)
                last_err = RuntimeError("Mistral AI request timed out.")
            except RuntimeError:
                raise
            except Exception as exc:
                _logger.exception("MISTRAL API: unexpected error")
                last_err = exc
        raise RuntimeError(_("Mistral AI call failed after %d attempts: %s") % (max_retries + 1, last_err))

    def list_models(self, env=None) -> List[str]:
        """Fetch available models from the Mistral API.
        Requires a valid API key in Odoo system parameters.
        """
        if not env:
            return []
        api_key = self._get_param(env, "tender_ai.mistral_api_key", "")
        if not api_key:
            return []
        try:
            resp = requests.get(
                "https://api.mistral.ai/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=15,
            )
            if resp.status_code == 200:
                return [m.get("id", "") for m in resp.json().get("data", []) if m.get("id")]
        except Exception as exc:
            _logger.error("MISTRAL API: list_models failed: %s", exc)
        return []

    def upload_file(self, file_path: str, env=None, **kwargs) -> Dict[str, Any]:
        """Return a base64 Data URL proxy for Mistral (Pixtral) vision.
        Mistral processes files as image_url in the message payload.
        """
        return self._file_to_base64_data_url(file_path)

# Singleton & backward‑compatible wrapper
_service = MistralService()

def generate_with_mistral(contents: Any, model: str = None, temperature: float = 0.1, env=None, max_retries: int = 3) -> Dict[str, Any]:
    """Backward‑compatible wrapper around MistralService.generate()."""
    return _service.generate(contents, model=model, temperature=temperature, max_retries=max_retries, env=env)

def list_available_models(env=None) -> List[str]:
    return _service.list_models(env=env)

def upload_file_to_mistral(file_path: str, env=None, **kwargs) -> Dict[str, Any]:
    return _service.upload_file(file_path, env=env, **kwargs)
