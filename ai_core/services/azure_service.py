# -*- coding: utf-8 -*-
"""
azure_service.py
────────────────
Microsoft Azure OpenAI (Azure Cloud Foundry) provider, implements BaseAIService.
"""

import time
import logging
import requests
from typing import Any, Dict, List, Optional

from .base_ai_service import BaseAIService

try:
    from odoo import _  # type: ignore
except ImportError:
    _ = lambda x: x          # noqa: E731  (standalone / test use)

_logger = logging.getLogger(__name__)

class AzureService(BaseAIService):
    """Microsoft Azure OpenAI (Azure Cloud Foundry) provider.

    Calls the Azure OpenAI REST API:
        POST {endpoint}/openai/deployments/{deployment}/chat/completions
        ?api-version={version}
    """

    PROVIDER = "azure"

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
            raise ValueError("Odoo Environment (env) is required for Azure AI service.")

        endpoint = self._get_param(env, "tender_ai.azure_endpoint", "").strip().rstrip("/")
        api_key  = self._get_param(env, "tender_ai.azure_api_key", "")
        deployment = model or self._get_param(env, "tender_ai.azure_deployment_name", "")
        api_version = self._get_param(env, "tender_ai.azure_api_version", "2024-12-01-preview")

        if not endpoint or not api_key or not deployment:
            raise RuntimeError(_("Azure configuration is incomplete (Endpoint, Key, or Deployment missing)."))

        if not endpoint.startswith("http"):
            endpoint = f"https://{endpoint}"

        url = f"{endpoint}/openai/deployments/{deployment}/chat/completions"
        headers = {
            "api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

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

        payload = {"messages": messages, "temperature": temperature, "max_tokens": 4096}
        all_text = str(contents).lower()
        if "json" in all_text and ("gpt-4" in deployment or "gpt-3.5" in deployment):
            payload["response_format"] = {"type": "json_object"}

        last_err: Optional[Exception] = None
        for attempt in range(max_retries + 1):
            self._retry_sleep(attempt)
            try:
                t0 = time.time()
                resp = requests.post(
                    url,
                    headers=headers,
                    json=payload,
                    params={"api-version": api_version},
                    timeout=60,
                )
                if resp.status_code == 400 and "temperature" in resp.text.lower() and "temperature" in payload:
                    _logger.info("AZURE API: Model rejected temperature setting. Retrying without it.")
                    del payload["temperature"]
                    resp = requests.post(url, headers=headers, json=payload, params={"api-version": api_version}, timeout=60)
                duration_ms = int((time.time() - t0) * 1000)
                if resp.status_code == 429:
                    if attempt >= max_retries:
                        raise RuntimeError(f"Azure rate-limited: {resp.text}")
                    _logger.warning("AZURE API: rate-limited (429), attempt %d/%d", attempt, max_retries)
                    last_err = RuntimeError(f"Azure rate-limited: {resp.text}")
                    time.sleep(5)
                    continue
                if resp.status_code != 200:
                    _logger.error("AZURE API: error %s – %s", resp.status_code, resp.text)
                    raise RuntimeError(_("Azure AI returned error %s: %s") % (resp.status_code, resp.text))
                data = resp.json()
                text = data["choices"][0]["message"]["content"]
                raw_usage = data.get("usage", {})
                usage = {"promptTokens": raw_usage.get("prompt_tokens", 0), "outputTokens": raw_usage.get("completion_tokens", 0), "totalTokens": raw_usage.get("total_tokens", 0)}
                return self._build_response(text=text, model=deployment, provider=self.PROVIDER, duration_ms=duration_ms, usage=usage)
            except requests.exceptions.Timeout:
                _logger.warning("AZURE API: request timed out (attempt %d)", attempt)
                last_err = RuntimeError("Azure AI request timed out.")
            except RuntimeError:
                raise
            except Exception as exc:
                _logger.exception("AZURE API: unexpected error")
                last_err = exc
        raise RuntimeError(_("Azure AI call failed after %d attempts: %s") % (max_retries + 1, last_err))

    def list_models(self, env=None) -> List[str]:
        """Azure doesn't expose a model-list endpoint; return empty list."""
        return []

    def upload_file(self, file_path: str, env=None, **kwargs) -> Dict[str, Any]:
        """Return a base64 Data URL proxy for Azure vision.
        Azure (GPT-4o) processes files by receiving them directly in the chat payload.
        """
        return self._file_to_base64_data_url(file_path)
