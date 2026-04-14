# -*- coding: utf-8 -*-
"""
base_ai_service.py
─────────────────
Abstract base class shared by every AI provider (Gemini, Azure, Mistral, …).

Responsibilities
----------------
* Defines the public contract: ``generate(contents, ...)``
* Provides helpers that every provider needs:
  - ``_normalise_messages()``  – turn any content shape into a [{"role","content"}] list
  - ``_build_response()``      – build the standard response dict returned to callers
  - ``_get_param()``           – read an Odoo system-parameter with a fallback
* Exposes a tiny retry helper so individual providers can use it if they want.

Callers should never import provider classes directly; instead they should use
``ai_service.generate()`` which dispatches to the right provider automatically.
"""

import abc
import time
import logging
from typing import Any, Dict, List, Optional

_logger = logging.getLogger(__name__)


class BaseAIService(abc.ABC):
    """Abstract base class for AI provider services.

    Sub-classes must implement:
        - ``generate(contents, model, temperature, max_retries, env)``

    They may optionally override:
        - ``list_models(env)``  – return a list of available model name strings
    """

    @abc.abstractmethod
    def generate(
        self,
        contents: Any,
        *,
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_retries: int = 3,
        env=None,
    ) -> Dict[str, Any]:
        """..."""
        pass

    def list_models(self, env=None) -> List[str]:
        """Return available model names. Override per-provider."""
        return []

    def upload_file(
        self,
        file_path: str,
        env=None,
        **kwargs,
    ) -> Any:
        """Prepare a file for processing.
        Returns a provider-specific file object or a data-proxy dict.
        """
        return None

    # ──────────────────────────────────────────────────────────────────────────
    # Shared helpers
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _normalise_messages(contents: Any) -> List[Dict[str, str]]:
        """Accept any of the forms callers pass and return a clean list of
        OpenAI-style message dicts: [{"role": "user", "content": "…"}].

        Accepted input forms
        --------------------
        - str                          → single user message
        - list[dict]  (already ok)     → returned as-is
        - list[non-dict]               → joined as a single user message
        - anything else                → str() conversion, single user message
        """
        if isinstance(contents, str):
            return [{"role": "user", "content": contents}]

        if isinstance(contents, list):
            if contents and isinstance(contents[0], dict) and "role" in contents[0]:
                return contents
            # Check if it's a mix of strings and file proxies
            has_proxy = any(isinstance(item, dict) and item.get("type") == "file_proxy" for item in contents)
            if has_proxy:
                # Keep it as a raw list for the provider to handle
                return [{"role": "user", "content": contents}]
            # Otherwise join everything as a user turn
            joined = "\n".join(str(p) for p in contents)
            return [{"role": "user", "content": joined}]

        return [{"role": "user", "content": str(contents)}]

    @staticmethod
    def _build_response(
        text: str,
        model: str,
        provider: str,
        duration_ms: int,
        usage: Optional[Dict[str, int]] = None,
    ) -> Dict[str, Any]:
        """Build the standard response dict that every caller expects."""
        return {
            "text": text or "",
            "usage": usage or {"promptTokens": 0, "outputTokens": 0, "totalTokens": 0},
            "model": model,
            "provider": provider,
            "durationMs": duration_ms,
        }

    @staticmethod
    def _get_param(env, key: str, fallback: str = "") -> str:
        """Read an Odoo system parameter, returning *fallback* on any error."""
        if not env:
            return fallback
        try:
            return env["ir.config_parameter"].sudo().get_param(key, fallback) or fallback
        except Exception:
            return fallback

    @staticmethod
    def _retry_sleep(attempt: int, base: float = 1.0, cap: float = 30.0) -> None:
        """Exponential back-off sleep between retries.
        attempt=0 → no sleep (first try),  attempt=1 → ~1s, attempt=2 → ~2s, …
        """
        if attempt <= 0:
            return
        delay = min(base * (2 ** (attempt - 1)), cap)
        _logger.debug("AI retry back-off: sleeping %.1fs before attempt %d", delay, attempt + 1)
        time.sleep(delay)

    @classmethod
    def _file_to_base64_data_url(cls, file_path: str) -> Dict[str, str]:
        """Helper: read local file and return a data-proxy dict for multi-modal calls."""
        import base64
        import mimetypes
        from pathlib import Path

        p = Path(file_path)
        if not p.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        mime_type, _ = mimetypes.guess_type(file_path)
        mime_type = mime_type or "application/octet-stream"

        with open(file_path, "rb") as f:
            raw_bytes = f.read()

        # If it's a PDF and we are preparing for a non-Gemini provider,
        # we often need to convert it to an image for Vision models to 'see' it.
        if mime_type == "application/pdf":
            try:
                img_data, mime_type = cls._render_pdf_to_image(raw_bytes)
                b64_data = img_data
            except Exception as e:
                _logger.warning("PDF-to-Image conversion failed, sending raw PDF: %s", str(e))
                b64_data = base64.b64encode(raw_bytes).decode("utf-8")
        else:
            b64_data = base64.b64encode(raw_bytes).decode("utf-8")

        return {
            "type": "file_proxy",
            "mime_type": mime_type,
            "data": b64_data,
            "url": f"data:{mime_type};base64,{b64_data}",
            "file_name": p.name,
        }

    @classmethod
    def _render_pdf_to_image(cls, pdf_bytes: bytes, page_num: int = 0, dpi_scale: float = 3.0) -> tuple[str, str]:
        """Convert a specific page of a PDF to a base64-encoded PNG image.
        
        Args:
            pdf_bytes: PDF file bytes
            page_num: Page index to render (0-based). Default 0 = first page.
            dpi_scale: Zoom factor for rendering. 3.0 = ~216 DPI for better Azure vision accuracy.
                       Increase for scanned documents or complex layouts.
        
        Returns:
            Tuple of (base64_png_string, 'image/png')
        """
        import base64
        try:
            import fitz
        except ImportError:
            raise ImportError("PyMuPDF (fitz) is required for PDF-to-Image conversion.")

        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        if len(doc) == 0:
            raise ValueError("PDF is empty")

        if page_num < 0 or page_num >= len(doc):
            page_num = 0  # Fall back to first page

        # Render at high resolution (216 DPI) for better Azure vision model accuracy
        page = doc[page_num]
        pix = page.get_pixmap(matrix=fitz.Matrix(dpi_scale, dpi_scale))
        img_bytes = pix.tobytes("png")
        doc.close()

        return base64.b64encode(img_bytes).decode("utf-8"), "image/png"
