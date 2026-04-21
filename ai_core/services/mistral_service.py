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

def _is_azure_ocr_endpoint(endpoint: str) -> bool:
    """Check if endpoint is Azure Mistral Document AI OCR endpoint."""
    return '/providers/mistral/azure/ocr' in endpoint

def _get_mistral_endpoint(env) -> str:
    """Get Mistral API endpoint URL from settings (custom or default).
    
    Handles multiple endpoint formats:
    - Standard chat: https://api.mistral.ai/v1/chat/completions
    - Azure OCR: https://gateway.com/providers/mistral/azure/ocr
    - Azure OCR chat: https://gateway.com/providers/mistral/azure/ocr/v1/chat/completions
    """
    custom_url = (BaseAIService._get_param(env, 'ai_core.mistral_endpoint_url', '') or '').strip()
    if custom_url:
        custom_url = custom_url.rstrip('/')
        
        # If it's Azure OCR endpoint, use as-is (don't auto-append /v1/chat/completions)
        if '/providers/mistral/azure/ocr' in custom_url:
            _logger.debug("MISTRAL: Using Azure OCR endpoint: %s", custom_url)
            return custom_url
        
        # If it already contains the full chat API path, use it as-is
        if '/v1/chat/completions' in custom_url:
            _logger.debug("MISTRAL: Using custom endpoint with full path: %s", custom_url)
            return custom_url
        
        # If it ends with /v1, append /chat/completions
        if custom_url.endswith('/v1'):
            endpoint = custom_url + '/chat/completions'
            _logger.debug("MISTRAL: Appending /chat/completions to endpoint")
            return endpoint
        
        # If it ends with /chat/completions, prepend /v1
        if custom_url.endswith('/chat/completions'):
            endpoint = custom_url.replace('/chat/completions', '/v1/chat/completions')
            _logger.debug("MISTRAL: Adding /v1 prefix to endpoint")
            return endpoint
        
        # Otherwise, append the full API path
        endpoint = custom_url + '/v1/chat/completions'
        _logger.debug("MISTRAL: Appending /v1/chat/completions to custom endpoint: %s → %s", custom_url, endpoint)
        return endpoint
    
    # Default to Mistral API if not configured in settings
    return "https://api.mistral.ai/v1/chat/completions"

def _get_ssl_verify(env) -> bool:
    """Get SSL verification setting for Mistral endpoint."""
    verify_setting = (BaseAIService._get_param(env, 'ai_core.mistral_verify_ssl', 'true') or 'true').strip().lower()
    return verify_setting != 'false'


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

        # Check if using Azure OCR endpoint
        api_endpoint = _get_mistral_endpoint(env)
        if _is_azure_ocr_endpoint(api_endpoint):
            # Route to Azure OCR handler if endpoint is Azure OCR
            _logger.info("MISTRAL: Detected Azure OCR endpoint, converting to document extraction format")
            import base64 as _b64

            # Try to extract a document data-URI from file_proxy items first
            doc_data_uri = None
            items = contents if isinstance(contents, list) else [contents]
            raw_messages = self._normalise_messages(items)
            for msg in raw_messages:
                parts = msg.get("content", "")
                if isinstance(parts, list):
                    for part in parts:
                        if isinstance(part, dict) and part.get("type") == "file_proxy":
                            url = part.get("url", "")
                            if url.startswith("data:"):
                                doc_data_uri = url
                                break
                    if doc_data_uri:
                        break

            if doc_data_uri:
                # Already a proper data-URI (e.g. data:image/png;base64,...)  →  use directly
                _logger.info("MISTRAL: Using file_proxy data URI for Azure OCR")
                return self.generate_document_extraction(
                    document_data_uri=doc_data_uri,
                    model=model,
                    env=env,
                    max_retries=max_retries,
                )
            else:
                # Plain-text content (e.g. test connection) – wrap as text/plain
                text_parts = []
                for msg in raw_messages:
                    c = msg.get("content", "")
                    if isinstance(c, str):
                        text_parts.append(c)
                    elif isinstance(c, list):
                        for p in c:
                            if isinstance(p, dict) and p.get("type") == "text":
                                text_parts.append(p.get("text", ""))
                            elif isinstance(p, str):
                                text_parts.append(p)
                text_content = "\n".join(text_parts)
                doc_b64 = _b64.b64encode(text_content.encode('utf-8')).decode('utf-8')
                _logger.info("MISTRAL: Using plain-text content for Azure OCR test (sent as application/pdf)")
                return self.generate_document_extraction(
                    document_data_uri=f"data:application/pdf;base64,{doc_b64}",
                    model=model,
                    env=env,
                    max_retries=max_retries,
                )

        api_key = self._get_param(env, "ai_core.mistral_api_key", "") or self._get_param(env, "tender_ai.mistral_api_key", "")
        if not api_key:
            raise RuntimeError(_("Mistral API Key is missing. Please configure it in Purple AI Settings."))

        resolved_model = (
            model
            or self._get_param(env, "ai_core.mistral_model", "")
            or self._get_param(env, "tender_ai.mistral_default_model", "")
            or "mistral-large-latest"  # Default fallback model
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
            "max_tokens": 8192,
        }

        # Enable JSON mode for appropriate models
        all_text = str(contents).lower()
        if "json" in all_text and ("large" in resolved_model or "small" in resolved_model or "pixtral" in resolved_model):
            payload["response_format"] = {"type": "json_object"}

        # Get SSL settings
        verify_ssl = _get_ssl_verify(env)
        
        # Use the endpoint retrieved earlier
        api_url = api_endpoint
        
        # Mask API key for logging (show first 4 and last 4 chars)
        key_display = f"{api_key[:4]}...{api_key[-4:]}" if len(api_key) > 8 else "***"
        
        last_err: Optional[Exception] = None
        for attempt in range(max_retries + 1):
            self._retry_sleep(attempt)
            try:
                t0 = time.time()
                
                # Log the request details (mask sensitive data)
                masked_payload = payload.copy()
                _logger.info(
                    "MISTRAL CHAT API REQUEST:\n"
                    "  URL: %s\n"
                    "  Method: POST\n"
                    "  Headers: Content-Type=application/json, Authorization=Bearer %s, Accept=application/json\n"
                    "  Payload: %s",
                    api_url, key_display, masked_payload
                )
                
                resp = requests.post(api_url, headers=headers, json=payload, timeout=120, verify=verify_ssl)
                duration_ms = int((time.time() - t0) * 1000)

                if resp.status_code == 429:
                    if attempt >= max_retries:
                        raise RuntimeError(f"Mistral rate-limited: {resp.text}")
                    sleep_time = min(5 * (attempt + 1), 60)
                    _logger.warning("MISTRAL API: rate-limited (429), attempt %d/%d. Waiting %ds...", attempt, max_retries, sleep_time)
                    last_err = RuntimeError(f"Mistral rate-limited: {resp.text}")
                    time.sleep(sleep_time)
                    continue

                if resp.status_code == 401:
                    # Authentication error - show debugging info
                    error_details = (
                        f"\n\n🔑 DEBUG INFO:\n"
                        f"• Endpoint: {api_url}\n"
                        f"• API Key: {key_display}\n"
                        f"• SSL Verify: {verify_ssl}\n"
                        f"• Model: {resolved_model}\n\n"
                        f"❌ Fix: Check that your API key is correct and matches the endpoint.\n"
                        f"• If using Azure gateway: Verify the custom endpoint URL\n"
                        f"• If using default Mistral: Verify your Mistral API key is active\n"
                        f"• Response: {resp.text}"
                    )
                    raise RuntimeError(_("Mistral AI Authentication Error (401): Invalid API key or endpoint%s") % error_details)
                
                if resp.status_code != 200:
                    error_details = (
                        f"\n\n🔍 DEBUG INFO:\n"
                        f"• Endpoint: {api_url}\n"
                        f"• API Key: {key_display}\n"
                        f"• SSL Verify: {verify_ssl}\n"
                        f"• Model: {resolved_model}"
                    )
                    _logger.error("MISTRAL API: error %s – %s", resp.status_code, resp.text)
                    raise RuntimeError(_("Mistral AI returned error %s: %s%s") % (resp.status_code, resp.text, error_details))

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
            except requests.exceptions.ConnectionError as conn_err:
                conn_err_msg = str(conn_err)
                _logger.error("MISTRAL API: Connection error: %s", conn_err_msg)
                if "NameResolutionError" in conn_err_msg or "Failed to resolve" in conn_err_msg:
                    error_msg = (
                        f"Cannot resolve hostname for Mistral endpoint: {api_url}\n"
                        f"This is a DNS/network issue. Possible causes:\n"
                        f"1. Check the endpoint URL is correct and accessible\n"
                        f"2. Verify network connectivity to the endpoint\n"
                        f"3. Check firewall/proxy settings\n"
                        f"4. For Azure: Verify the resource group and region are correct"
                    )
                    last_err = RuntimeError(error_msg)
                else:
                    last_err = RuntimeError(f"Connection failed: {conn_err_msg}")
            except requests.exceptions.Timeout:
                _logger.warning("MISTRAL API: request timed out (attempt %d)", attempt)
                last_err = RuntimeError("Mistral AI request timed out.")
            except RuntimeError:
                raise
            except Exception as exc:
                _logger.exception("MISTRAL API: unexpected error")
                last_err = exc
        raise RuntimeError(_("Mistral AI call failed after %d attempts: %s") % (max_retries + 1, last_err))

    def generate_document_extraction(
        self,
        document_data_uri: str = "",
        document_content: str = "",
        *,
        mime_type: str = "application/pdf",
        model: Optional[str] = None,
        extraction_schema: Optional[Dict[str, Any]] = None,
        max_retries: int = 3,
        env=None,
    ) -> Dict[str, Any]:
        """Extract data from documents using Azure Mistral Document AI OCR endpoint.
        
        Args:
            document_data_uri: Full data-URI (e.g. data:image/png;base64,...). Preferred.
            document_content: Raw base64 string (legacy). Uses *mime_type* to build data-URI.
            mime_type: MIME type when using document_content (default application/pdf)
            model: Model name (e.g., 'mistral-document-ai-2505')
            extraction_schema: JSON schema for extracted data
            env: Odoo environment
        """
        if not env:
            raise ValueError("Odoo Environment (env) is required for Mistral AI service.")

        api_key = self._get_param(env, "ai_core.mistral_api_key", "") or self._get_param(env, "tender_ai.mistral_api_key", "")
        if not api_key:
            raise RuntimeError(_("Mistral API Key is missing. Please configure it in Purple AI Settings."))

        resolved_model = (
            model
            or self._get_param(env, "ai_core.mistral_model", "")
            or "mistral-document-ai-2505"
        )

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        # Build extraction schema
        if not extraction_schema:
            extraction_schema = {
                "type": "json_schema",
                "json_schema": {
                    "schema": {
                        "properties": {
                            "extracted_text": {"title": "Extracted Text", "type": "string"},
                        },
                        "required": ["extracted_text"],
                        "title": "DocumentExtraction",
                        "type": "object",
                        "additionalProperties": False,
                    },
                    "name": "document_extraction",
                    "strict": True,
                },
            }

        # Build the document data-URI
        if document_data_uri:
            doc_url = document_data_uri
        elif document_content:
            doc_url = f"data:{mime_type};base64,{document_content}"
        else:
            raise ValueError("Either document_data_uri or document_content must be provided.")

        payload = {
            "model": resolved_model,
            "document": {
                "type": "document_url",
                "document_url": doc_url,
            },
            "document_annotation_format": extraction_schema,
            "include_image_base64": True,
        }

        # Get custom endpoint and SSL settings
        api_url = _get_mistral_endpoint(env)
        verify_ssl = _get_ssl_verify(env)
        
        # Check if using Azure proxy (may have stricter validation)
        is_azure_proxy = '/providers/mistral/azure' in api_url.lower()
        
        key_display = f"{api_key[:4]}...{api_key[-4:]}" if len(api_key) > 8 else "***"
        
        last_err: Optional[Exception] = None
        for attempt in range(max_retries + 1):
            self._retry_sleep(attempt)
            try:
                t0 = time.time()
                
                # Log the request details (mask sensitive data and large content)
                masked_payload = payload.copy()
                if 'document' in masked_payload and 'document_url' in masked_payload['document']:
                    masked_payload['document']['document_url'] = masked_payload['document']['document_url'][:50] + '...' if len(masked_payload['document']['document_url']) > 50 else masked_payload['document']['document_url']
                
                _logger.info(
                    "MISTRAL OCR API REQUEST:\n"
                    "  URL: %s\n"
                    "  Method: POST\n"
                    "  Headers: Content-Type=application/json, Authorization=Bearer %s\n"
                    "  Payload: %s",
                    api_url, key_display, masked_payload
                )
                
                resp = requests.post(api_url, headers=headers, json=payload, timeout=120, verify=verify_ssl)
                duration_ms = int((time.time() - t0) * 1000)

                if resp.status_code == 429:
                    if attempt >= max_retries:
                        raise RuntimeError(f"Mistral rate-limited: {resp.text}")
                    sleep_time = min(5 * (attempt + 1), 60)
                    _logger.warning("MISTRAL OCR: rate-limited (429), attempt %d/%d. Waiting %ds...", attempt, max_retries, sleep_time)
                    last_err = RuntimeError(f"Mistral rate-limited: {resp.text}")
                    time.sleep(sleep_time)
                    continue

                if resp.status_code != 200:
                    error_text = resp.text
                    _logger.error("MISTRAL OCR: error %s – %s", resp.status_code, error_text)
                    
                    # Provide specific guidance for Azure proxy data URI limitation
                    if is_azure_proxy and resp.status_code == 400 and 'invalid_request' in error_text.lower():
                        error_text += (
                            "\n\n⚠️ Azure Mistral OCR Proxy Limitation:\n"
                            "The Azure gateway may only accept HTTPS URLs for the 'document_url' field,\n"
                            "not base64 data URIs. Possible solutions:\n"
                            "1. Use the standard Mistral /v1/ocr endpoint instead: https://api.mistral.ai/v1/ocr\n"
                            "2. Host your PDFs on an HTTPS server and pass the URLs\n"
                            "3. Contact Azure support to enable data URI support on this gateway"
                        )
                    
                    raise RuntimeError(_("Mistral AI OCR returned error %s: %s") % (resp.status_code, error_text))

                data = resp.json()
                # Azure OCR response contains extracted data directly
                return self._build_response(
                    text=str(data),
                    model=resolved_model,
                    provider=self.PROVIDER,
                    duration_ms=duration_ms,
                )
            except requests.exceptions.ConnectionError as conn_err:
                conn_err_msg = str(conn_err)
                _logger.error("MISTRAL OCR: Connection error: %s", conn_err_msg)
                if "NameResolutionError" in conn_err_msg or "Failed to resolve" in conn_err_msg:
                    error_msg = (
                        f"Cannot resolve hostname for Mistral OCR endpoint: {api_url}\n"
                        f"This is a DNS/network issue. Possible causes:\n"
                        f"1. Check the endpoint URL is correct and accessible\n"
                        f"2. Verify network connectivity to the endpoint\n"
                        f"3. Check firewall/proxy settings\n"
                        f"4. For Azure: Verify the resource group and region are correct"
                    )
                    last_err = RuntimeError(error_msg)
                else:
                    last_err = RuntimeError(f"Connection failed: {conn_err_msg}")
            except requests.exceptions.Timeout:
                _logger.warning("MISTRAL OCR: request timed out (attempt %d)", attempt)
                last_err = RuntimeError("Mistral AI OCR request timed out.")
            except RuntimeError:
                raise
            except Exception as exc:
                _logger.exception("MISTRAL OCR: unexpected error")
                last_err = exc
        raise RuntimeError(_("Mistral AI OCR call failed after %d attempts: %s") % (max_retries + 1, last_err))

    def list_models(self, env=None) -> List[str]:
        """Fetch available models from the Mistral API.
        Requires a valid API key in Odoo system parameters.
        """
        if not env:
            return []
        api_key = self._get_param(env, "ai_core.mistral_api_key", "") or self._get_param(env, "tender_ai.mistral_api_key", "")
        if not api_key:
            return []
        try:
            # Get custom endpoint and SSL settings
            custom_url = (self._get_param(env, 'ai_core.mistral_endpoint_url', '') or '').strip()
            verify_ssl = _get_ssl_verify(env)
            
            # Construct models endpoint
            if custom_url:
                models_url = custom_url.rstrip('/') + '/v1/models'
            else:
                models_url = "https://api.mistral.ai/v1/models"
            
            resp = requests.get(
                models_url,
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=15,
                verify=verify_ssl,
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
