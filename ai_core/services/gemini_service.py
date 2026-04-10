# -*- coding: utf-8 -*-
"""
gemini_service.py
────────────────
Google Gemini (google-genai SDK) provider, implements BaseAIService.
"""

import os
import time
import re
import threading
import logging
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base_ai_service import BaseAIService

try:
    from google import genai
    from google.genai import errors as genai_errors
except ImportError:
    genai = None
    genai_errors = None

_logger = logging.getLogger(__name__)

# ── Default model fallback ────────────────────────────────────────────────────
_DEFAULT_MODEL_FALLBACK = "gemini-2.0-flash"

# ── Model cache ────────────────────────────────────────────────────────────────
_model_cache: Optional[str] = None
_model_cache_lock = threading.Lock()

# ── Thread-local client (one per thread = thread-safe) ────────────────────────
_thread_local = threading.local()

# ── Concurrency cap (avoids 429 when running parallel PDFs/companies) ────────
_GEMINI_SEM = threading.BoundedSemaphore(
    int(os.getenv("AI_MAX_CONCURRENCY") or os.getenv("GEMINI_MAX_CONCURRENCY") or "8")
)

# ── File‑upload cache: hash → (file_obj, name, upload_time) ────────────────────
_file_cache: Dict[str, Any] = {}
_file_cache_lock = threading.Lock()
_FILE_CACHE_TTL = 3600       # cache files for 1 hour
_last_cleanup_time = 0
_CLEANUP_INTERVAL = 300      # run cleanup every 5 minutes

# ── API key cache ──────────────────────────────────────────────────────────────
_api_key_cache: Optional[str] = None
_api_key_cache_lock = threading.Lock()


class GeminiService(BaseAIService):
    """Google Gemini provider.

    Uses the google‑genai SDK (``pip install google‑genai``). Supports file‑upload
    caching, concurrency throttling, and SDK compatibility shims for different
    SDK versions.
    """

    PROVIDER = "gemini"

    def generate(
        self,
        contents: Any,
        *,
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_retries: int = 3,
        env=None,
    ) -> Dict[str, Any]:
        if genai is None:
            raise RuntimeError(
                "google‑genai package is not installed. Install it with: pip install google‑genai"
            )

        resolved_model = model or self.get_model(env)
        client = self._get_client(env=env)

        # Normalise model name (always prefix models/)
        full_model = (
            resolved_model if resolved_model.startswith("models/")
            else f"models/{resolved_model}"
        )

        _logger.debug(
            "GEMINI API: generate_content() – model=%s  temperature=%.2f",
            full_model, temperature,
        )

        last_err: Optional[Exception] = None
        for attempt in range(max_retries + 1):
            self._retry_sleep(attempt)
            if attempt > 0:
                _logger.warning("GEMINI API: retry %d/%d", attempt, max_retries)

            try:
                t0 = time.time()
                with _GEMINI_SEM:
                    response = _generate_content_compat(
                        client, model=full_model,
                        contents=contents, temperature=temperature,
                    )
                duration_ms = int((time.time() - t0) * 1000)

                text = _extract_text(response)
                usage = _extract_usage(response)

                _logger.debug(
                    "GEMINI API: ✓ done – %.2fs  tokens=%s",
                    duration_ms / 1000, usage,
                )
                return self._build_response(
                    text=text,
                    model=resolved_model,
                    provider=self.PROVIDER,
                    duration_ms=duration_ms,
                    usage=usage,
                )

            except Exception as exc:
                msg = str(exc)
                if genai_errors and isinstance(exc, genai_errors.ClientError):
                    if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                        if attempt >= max_retries:
                            raise RuntimeError(f"Gemini rate‑limited: {msg}")
                        _logger.warning("GEMINI API: rate‑limited, sleeping 5s before retry")
                        time.sleep(5)
                        last_err = exc
                        continue
                    if "404" in msg or "NOT_FOUND" in msg:
                        raise RuntimeError(
                            f"Model not found or not allowed: '{full_model}'. "
                            "Try clicking 'Fetch Available Models' in Purple AI settings."
                        )
                    raise
                last_err = exc

        raise RuntimeError(
            f"Gemini generate failed after {max_retries + 1} attempts: {last_err}"
        )

    def list_models(self, env=None) -> List[str]:
        try:
            client = self._get_client(env=env)
            return [m.name for m in client.models.list()]
        except Exception as exc:
            _logger.error("GEMINI API: list_models failed: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Gemini‑specific: file uploads
    # ------------------------------------------------------------------
    def upload_file(
        self,
        file_path: str,
        env=None,
        wait_active: bool = True,
        max_wait_sec: int = 90,
        use_cache: bool = True,
        **kwargs,
    ) -> Any:
        _cleanup_file_cache(lazy=True)

        file_hash: Optional[str] = None
        if use_cache:
            try:
                file_hash = _get_file_hash(file_path)
                with _file_cache_lock:
                    if file_hash in _file_cache:
                        cached_file, _, upload_time = _file_cache[file_hash]
                        if time.time() - upload_time < _FILE_CACHE_TTL:
                            _logger.debug(
                                "GEMINI API: cache hit for %s (uploaded %.1fs ago)",
                                file_path, time.time() - upload_time,
                            )
                            return cached_file
            except Exception as exc:
                _logger.debug("GEMINI API: hash error (cache skipped): %s", exc)

        client = self._get_client(env=env)
        p = Path(file_path)
        if not p.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        _logger.debug(
            "GEMINI API: uploading %s (%.2f MB)",
            file_path, p.stat().st_size / 1_048_576,
        )
        upload_start = time.time()
        with _GEMINI_SEM:
            f = client.files.upload(file=p)
        _logger.debug(
            "GEMINI API: upload done in %.2fs", time.time() - upload_start
        )

        name = getattr(f, "name", None)

        if not wait_active:
            if use_cache and name and file_hash:
                with _file_cache_lock:
                    _file_cache[file_hash] = (f, name, time.time())
            return f

        if not name:
            return f

        # Wait for ACTIVE
        start = time.time()
        while time.time() - start < max_wait_sec:
            try:
                with _GEMINI_SEM:
                    f2 = client.files.get(name=name)
                state = str(getattr(f2, "state", "")).upper()
                if "ACTIVE" in state:
                    if use_cache and file_hash:
                        with _file_cache_lock:
                            _file_cache[file_hash] = (f2, name, time.time())
                    return f2
                if "FAILED" in state:
                    _logger.error("GEMINI API: file processing FAILED for %s", name)
                    break
                elapsed = time.time() - start
                if int(elapsed) % 10 == 0:
                    _logger.debug(
                        "GEMINI API: waiting for ACTIVE (state=%s, elapsed=%.1fs)",
                        state, elapsed,
                    )
            except Exception as exc:
                _logger.debug("GEMINI API: file state check error: %s", exc)
            time.sleep(1)

        if use_cache and name and file_hash:
            with _file_cache_lock:
                _file_cache[file_hash] = (f, name, time.time())
        return f

    # ------------------------------------------------------------------
    # API key & model resolution
    # ------------------------------------------------------------------
    def get_api_key(self, env=None) -> str:
        global _api_key_cache
        with _api_key_cache_lock:
            if _api_key_cache:
                return _api_key_cache

        # 1. odoo.conf
        try:
            from odoo import tools  # type: ignore
            cfg = getattr(tools, "config", None)
            if cfg:
                for key in ("AI_API_KEY", "ai_api_key", "GEMINI_API_KEY", "gemini_api_key"):
                    try:
                        value = cfg.get(key) if hasattr(cfg, "get") else None
                    except Exception:
                        value = None
                    if value:
                        _logger.debug("AI API KEY: found in odoo.conf")
                        with _api_key_cache_lock:
                            _api_key_cache = value
                        return value
        except Exception as exc:
            _logger.debug("AI API KEY: could not read odoo.conf: %s", exc)

        # 2. System parameter
        if env:
            try:
                for param in ("tender_ai.ai_api_key", "tender_ai.gemini_api_key"):
                    value = env["ir.config_parameter"].sudo().get_param(param, "")
                    if value:
                        _logger.debug("AI API KEY: found in system parameter (%s)", param)
                        with _api_key_cache_lock:
                            _api_key_cache = value
                        return value
            except Exception:
                pass

        # 3. Environment variable
        value = os.getenv("AI_API_KEY") or os.getenv("GEMINI_API_KEY")
        if value:
            _logger.debug("AI API KEY: found in environment variable")
            with _api_key_cache_lock:
                _api_key_cache = value
            return value

        raise RuntimeError(
            "Missing AI API key. Set it via:\n"
            "1. odoo.conf → add 'ai_api_key=your_key' in [options] then restart Odoo\n"
            "2. Environment variable: export AI_API_KEY=your_key\n"
            "3. Odoo System Parameter: tender_ai.ai_api_key"
        )

    def get_model(self, env=None) -> str:
        global _model_cache
        with _model_cache_lock:
            if _model_cache:
                return _model_cache

        if env:
            try:
                model = env["ir.config_parameter"].sudo().get_param(
                    "tender_ai.default_model", ""
                )
                if model:
                    with _model_cache_lock:
                        _model_cache = model
                    return model
            except Exception:
                pass

        model = (
            os.getenv("AI_MODEL")
            or os.getenv("AI_TENDER_MODEL")
            or os.getenv("AI_COMPANY_MODEL")
            or os.getenv("GEMINI_COMPANY_MODEL")
            or os.getenv("GEMINI_TENDER_MODEL")
        )
        if model:
            with _model_cache_lock:
                _model_cache = model
            return model

        return _DEFAULT_MODEL_FALLBACK

    def invalidate_model_cache(self) -> None:
        global _model_cache
        with _model_cache_lock:
            _model_cache = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _get_client(self, env=None):
        if genai is None:
            raise RuntimeError(
                "google‑genai package is not installed. Install it with: pip install google‑genai"
            )
        client = getattr(_thread_local, "client", None)
        if client is not None:
            return client
        api_key = self.get_api_key(env=env)
        _thread_local.client = genai.Client(api_key=api_key)
        return _thread_local.client

# ── Module‑level private helpers (unchanged logic, kept here for locality) ──

def _get_file_hash(file_path: str) -> str:
    sha = hashlib.sha256()
    with open(file_path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            sha.update(chunk)
    return sha.hexdigest()

def _cleanup_file_cache(lazy: bool = True) -> None:
    global _last_cleanup_time
    now = time.time()
    if lazy and (now - _last_cleanup_time) < _CLEANUP_INTERVAL:
        return
    with _file_cache_lock:
        expired = [k for k, (_, _, t) in _file_cache.items() if now - t >= _FILE_CACHE_TTL]
        for k in expired:
            del _file_cache[k]
        if expired:
            _logger.debug("GEMINI API: evicted %d expired file cache entries", len(expired))
        _last_cleanup_time = now

def _extract_text(response: Any) -> str:
    txt = getattr(response, "text", None)
    if txt:
        return txt
    try:
        out = []
        for c in (getattr(response, "candidates", None) or []):
            for part in (getattr(getattr(c, "content", None), "parts", None) or []):
                t = getattr(part, "text", None)
                if t:
                    out.append(t)
        return "\n".join(out).strip()
    except Exception:
        return ""

def _extract_usage(response: Any) -> Dict[str, int]:
    if response is None:
        return {}
    usage = getattr(response, "usage_metadata", None) or getattr(response, "usageMetadata", None)
    if usage is not None:
        def _int(v):
            try:
                return int(v)
            except Exception:
                return 0
        pt = (
            getattr(usage, "prompt_token_count", None)
            or getattr(usage, "promptTokenCount", None)
            or getattr(usage, "input_token_count", None)
            or 0
        )
        ot = (
            getattr(usage, "candidates_token_count", None)
            or getattr(usage, "candidatesTokenCount", None)
            or getattr(usage, "output_token_count", None)
            or 0
        )
        tt = getattr(usage, "total_token_count", None) or getattr(usage, "totalTokenCount", None)
        pt_i, ot_i = _int(pt), _int(ot)
        tt_i = _int(tt) if tt is not None else pt_i + ot_i
        if pt_i or ot_i or tt_i:
            return {"promptTokens": pt_i, "outputTokens": ot_i, "totalTokens": tt_i}
    try:
        d = response.__dict__ if hasattr(response, "__dict__") else {}
        for key in ("usage", "usageMetadata", "usage_metadata"):
            if key in d and isinstance(d[key], dict):
                u = d[key]
                pt = u.get("promptTokens") or u.get("prompt_token_count") or 0
                ot = u.get("outputTokens") or u.get("candidates_token_count") or 0
                tt = u.get("totalTokens") or u.get("total_token_count") or (int(pt) + int(ot))
                return {
                    "promptTokens": int(pt) if str(pt).isdigit() else 0,
                    "outputTokens": int(ot) if str(ot).isdigit() else 0,
                    "totalTokens": int(tt) if str(tt).isdigit() else 0,
                }
    except Exception:
        pass
    return {}

def _sleep_from_retry_message(msg: str, default_sec: int = 5) -> int:
    if not msg:
        return default_sec
    m = re.search(r"retry in\\s+([\\d.]+)s", msg, re.IGNORECASE)
    if m:
        try:
            return max(1, int(float(m.group(1))))
        except Exception:
            pass
    m = re.search(r"retryDelay['\\\"]?\\s*:\\s*['\\\"]?(\\d+)s", msg, re.IGNORECASE)
    if m:
        try:
            return max(1, int(m.group(1)))
        except Exception:
            pass
    return default_sec

def _generate_content_compat(client, model: str, contents: Any, temperature: float) -> Any:
    try:
        return client.models.generate_content(
            model=model, contents=contents,
            generation_config={"temperature": temperature},
        )
    except TypeError:
        pass
    try:
        return client.models.generate_content(
            model=model, contents=contents,
            config={"temperature": temperature},
        )
    except TypeError:
        pass
    return client.models.generate_content(model=model, contents=contents)

# Singleton & backward‑compatible module‑level functions
_service = GeminiService()

def generate_with_gemini(
    contents: Any,
    model: str = None,
    max_retries: int = 3,
    temperature: float = 0.1,
    env=None,
) -> Dict[str, Any]:
    return _service.generate(
        contents,
        model=model,
        temperature=temperature,
        max_retries=max_retries,
        env=env,
    )

def upload_file_to_gemini(
    file_path: str,
    wait_active: bool = True,
    max_wait_sec: int = 90,
    env=None,
    use_cache: bool = True,
) -> Any:
    return _service.upload_file(
        file_path,
        wait_active=wait_active,
        max_wait_sec=max_wait_sec,
        env=env,
        use_cache=use_cache,
    )

def get_gemini_api_key(env=None) -> str:
    return _service.get_api_key(env=env)

def get_configured_model(env=None) -> str:
    return _service.get_model(env=env)

def _invalidate_model_cache() -> None:
    _service.invalidate_model_cache()

def list_available_models(env=None) -> List[str]:
    return _service.list_models(env=env)
