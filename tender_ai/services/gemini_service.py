# -*- coding: utf-8 -*-

import os
import time
import re
import threading
import logging
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from google import genai
    from google.genai import errors as genai_errors
except ImportError:
    genai = None
    genai_errors = None

_logger = logging.getLogger(__name__)


# Thread-local storage so each thread gets its own client (thread-safe for parallel calls)
_thread_local = threading.local()

# Global concurrency cap to avoid 429 when you run parallel PDFs/companies
# Set env: AI_MAX_CONCURRENCY=8 (recommended 6-12). Legacy env var is still supported.
_GEMINI_SEM = threading.BoundedSemaphore(int(os.getenv("AI_MAX_CONCURRENCY") or os.getenv("GEMINI_MAX_CONCURRENCY") or "8"))

# File upload cache: maps file_path -> (file_object, file_name, upload_time)
# This avoids re-uploading the same file multiple times within a short period
# Note: The SDK will still make GET requests to fetch file metadata
# before each generate_content() call - this is expected SDK behavior
_file_cache = {}
_file_cache_lock = threading.Lock()
_FILE_CACHE_TTL = 3600  # Cache files for 1 hour
_last_cleanup_time = 0
_CLEANUP_INTERVAL = 300  # Run cleanup every 5 minutes instead of on every call


def _cleanup_file_cache(lazy=True):
    """
    Remove expired entries from file cache to prevent memory leaks.
    
    Args:
        lazy: If True, only cleanup if enough time has passed since last cleanup.
              If False, cleanup immediately.
    """
    global _last_cleanup_time
    current_time = time.time()
    
    # Lazy cleanup: only run if enough time has passed
    if lazy and (current_time - _last_cleanup_time) < _CLEANUP_INTERVAL:
        return
    
    with _file_cache_lock:
        expired_paths = [
            path for path, (_, _, upload_time) in _file_cache.items()
            if current_time - upload_time >= _FILE_CACHE_TTL
        ]
        for path in expired_paths:
            del _file_cache[path]
        if expired_paths:
            _logger.debug("AI API: Cleaned up %d expired file cache entries", len(expired_paths))
        _last_cleanup_time = current_time


# Cache API key to avoid repeated lookups
_api_key_cache = None
_api_key_cache_lock = threading.Lock()


def get_gemini_api_key(env=None):
    """
    Get AI API key from (in priority order):
    1. Odoo config file (odoo.conf): ai_api_key (preferred), then legacy keys
    2. Odoo system parameter: tender_ai.ai_api_key (preferred), then legacy parameter
    3. Environment variable: AI_API_KEY (preferred), then legacy environment variable
    4. Raise error if not found
    
    Args:
        env: Optional Odoo environment (api.Environment). If provided, will check system parameters.
    
    Returns:
        str: API key
    """
    global _api_key_cache
    
    # Return cached key if available
    with _api_key_cache_lock:
        if _api_key_cache:
            return _api_key_cache
    
    # Try Odoo config file (odoo.conf)
    try:
        from odoo import tools
        cfg = getattr(tools, 'config', None)
        if cfg:
            # Odoo stores config options in a dict-like object; keys are typically lowercased.
            candidates = [
                # Preferred neutral keys
                "AI_API_KEY",
                "ai_api_key",
                "ai_api_key".upper(),
                # Legacy keys (still supported for backwards compatibility)
                "GEMINI_API_KEY",
                "gemini_api_key",
                "GEMINI_API_KEY".lower(),
            ]
            for key in candidates:
                try:
                    api_key = cfg.get(key) if hasattr(cfg, "get") else None
                except Exception:
                    api_key = None
                if api_key:
                    _logger.debug("AI API KEY: Found in odoo.conf")
                    with _api_key_cache_lock:
                        _api_key_cache = api_key
                    return api_key
    except (ImportError, Exception) as e:
        _logger.debug("AI API KEY: Could not read from odoo.conf: %s", str(e))
    
    # If env is provided, try system parameter
    if env:
        try:
            api_key = env['ir.config_parameter'].sudo().get_param('tender_ai.ai_api_key', '')
            if not api_key:
                # Legacy parameter
                api_key = env['ir.config_parameter'].sudo().get_param('tender_ai.gemini_api_key', '')
            if api_key:
                _logger.debug("AI API KEY: Found in system parameter")
                with _api_key_cache_lock:
                    _api_key_cache = api_key
                return api_key
        except Exception:
            pass

    # Finally, try environment variable (optional fallback)
    api_key = os.getenv("AI_API_KEY") or os.getenv("GEMINI_API_KEY")
    if api_key:
        _logger.debug("AI API KEY: Found in environment variable")
        with _api_key_cache_lock:
            _api_key_cache = api_key
        return api_key
    
    # Final error with helpful message
    error_msg = (
        "Missing AI API key. Set it via:\n"
        "1. Odoo config file (odoo.conf): Add 'ai_api_key=your_key' in [options] section\n"
        "   Then RESTART Odoo server for changes to take effect\n"
        "2. Environment variable: export AI_API_KEY=your_key (before starting Odoo)\n"
        "3. Odoo System Parameter: Settings > Technical > Parameters > System Parameters\n"
        "   Create/Edit parameter 'tender_ai.ai_api_key' with your API key\n\n"
        "Note: If you added it to odoo.conf, make sure:\n"
        "  - It's in the [options] section\n"
        "  - There are no spaces around the = sign\n"
        "  - You have RESTARTED the Odoo server"
    )
    _logger.error("AI API KEY: %s", error_msg)
    raise RuntimeError(error_msg)


def _get_client(env=None):
    """
    Thread-safe AI client getter.
    Each thread gets its own client instance.
    
    Args:
        env: Optional Odoo environment (api.Environment). Used to get API key from system parameters.
    """
    if genai is None:
        raise RuntimeError("google-genai package is not installed. Install it with: pip install google-genai")
    
    client = getattr(_thread_local, "client", None)
    if client is not None:
        return client

    api_key = get_gemini_api_key(env=env)
    _thread_local.client = genai.Client(api_key=api_key)
    return _thread_local.client


def upload_file_to_gemini(
    file_path: str,
    wait_active: bool = True,
    max_wait_sec: int = 90,
    env=None,
    use_cache: bool = True,
):
    """
    Upload local file (PDF) to the AI Files API and return the File object.
    If wait_active=True, waits until state becomes ACTIVE (or timeout).
    
    NOTE: The SDK will make GET requests to fetch file metadata
    before each generate_content() call. This is expected SDK behavior and
    cannot be avoided. The repeated GET requests you see in logs are the SDK
    validating file state before API calls.
    
    Args:
        file_path: Path to the file to upload
        wait_active: Whether to wait for file to become ACTIVE
        max_wait_sec: Maximum seconds to wait
        env: Optional Odoo environment (api.Environment). Used to get API key from system parameters.
        use_cache: Whether to use cached file if available (default: True)
    """
    # Lazy cleanup: only run if enough time has passed
    _cleanup_file_cache(lazy=True)
    
    # Check cache first
    if use_cache:
        with _file_cache_lock:
            if file_path in _file_cache:
                cached_file, cached_name, upload_time = _file_cache[file_path]
                # Check if cache is still valid (within TTL)
                if time.time() - upload_time < _FILE_CACHE_TTL:
                    _logger.debug("GEMINI API: Using cached file for %s (uploaded %.1f seconds ago)", 
                                file_path, time.time() - upload_time)
                    if wait_active:
                        # Only verify file is ACTIVE if we need to wait
                        # For cached files, assume they're still active (they expire from cache after TTL)
                        # This avoids unnecessary API calls
                        return cached_file
                    else:
                        return cached_file
    
    client = _get_client(env=env)

    p = Path(file_path)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    file_size_mb = p.stat().st_size / (1024 * 1024)
    _logger.debug("AI API: Uploading file to Files API: %s (%.2f MB)", 
                  file_path, file_size_mb)

    # Gate uploads too (helps when many threads upload together)
    upload_start = time.time()
    with _GEMINI_SEM:
        f = client.files.upload(file=p)
    upload_duration = time.time() - upload_start
    _logger.debug("GEMINI API: File uploaded successfully (Duration: %.2f seconds)", upload_duration)

    name = getattr(f, "name", None)
    
    if not wait_active:
        # Cache the file even if not waiting for ACTIVE
        if use_cache and name:
            with _file_cache_lock:
                _file_cache[file_path] = (f, name, time.time())
        return f

    if not name:
        return f

    start = time.time()
    while time.time() - start < max_wait_sec:
        try:
            with _GEMINI_SEM:
                f2 = client.files.get(name=name)
            state = str(getattr(f2, "state", "")).upper()
            if state == "ACTIVE":
                # Cache the active file
                if use_cache:
                    with _file_cache_lock:
                        _file_cache[file_path] = (f2, name, time.time())
                return f2
        except Exception:
            pass
        time.sleep(1)

    # Cache even if not ACTIVE (might become ACTIVE later)
    if use_cache and name:
        with _file_cache_lock:
            _file_cache[file_path] = (f, name, time.time())
    
    return f


def _extract_text(response: Any) -> str:
    """
    Some responses have non-text parts; this tries to safely return only text.
    """
    txt = getattr(response, "text", None)
    if txt:
        return txt

    try:
        candidates = getattr(response, "candidates", None) or []
        out = []
        for c in candidates:
            content = getattr(c, "content", None)
            parts = getattr(content, "parts", None) or []
            for part in parts:
                t = getattr(part, "text", None)
                if t:
                    out.append(t)
        return "\n".join(out).strip()
    except Exception:
        return ""


def _extract_usage(response: Any) -> Dict[str, Any]:
    """
    Best-effort extraction of token usage from different google-genai SDK response shapes.

    Returns normalized fields when possible:
      {
        "promptTokens": int,
        "outputTokens": int,
        "totalTokens": int
      }

    If not found, returns {}.
    """
    if response is None:
        return {}

    # Newer style often: response.usage_metadata or response.usageMetadata
    usage = getattr(response, "usage_metadata", None) or getattr(response, "usageMetadata", None)
    if usage is not None:
        # Try common attribute names
        pt = getattr(usage, "prompt_token_count", None) or getattr(usage, "promptTokenCount", None) or getattr(usage, "input_token_count", None) or getattr(usage, "inputTokenCount", None)
        ot = getattr(usage, "candidates_token_count", None) or getattr(usage, "candidatesTokenCount", None) or getattr(usage, "output_token_count", None) or getattr(usage, "outputTokenCount", None)
        tt = getattr(usage, "total_token_count", None) or getattr(usage, "totalTokenCount", None)

        def _to_int(v):
            try:
                return int(v)
            except Exception:
                return 0

        pt_i = _to_int(pt)
        ot_i = _to_int(ot)
        tt_i = _to_int(tt) if tt is not None else (pt_i + ot_i)

        out = {
            "promptTokens": pt_i,
            "outputTokens": ot_i,
            "totalTokens": tt_i,
        }
        # only return if anything exists
        if out["promptTokens"] or out["outputTokens"] or out["totalTokens"]:
            return out

    # Some SDK versions might attach usage into response as dict-like
    # or nested fields. We safely try a couple more patterns.
    try:
        d = response.__dict__ if hasattr(response, "__dict__") else {}
        for key in ("usage", "usageMetadata", "usage_metadata"):
            if key in d and isinstance(d[key], dict):
                u = d[key]
                pt = u.get("promptTokens") or u.get("prompt_token_count") or u.get("inputTokens") or u.get("input_token_count") or 0
                ot = u.get("outputTokens") or u.get("candidates_token_count") or u.get("candidateTokens") or u.get("output_token_count") or 0
                tt = u.get("totalTokens") or u.get("total_token_count") or (int(pt) + int(ot))
                return {
                    "promptTokens": int(pt) if str(pt).isdigit() else 0,
                    "outputTokens": int(ot) if str(ot).isdigit() else 0,
                    "totalTokens": int(tt) if str(tt).isdigit() else (0 if tt is None else int(tt)),
                }
    except Exception:
        pass

    return {}


def _sleep_from_retry_message(msg: str, default_sec: int = 10) -> int:
    """
    Parses retry delay seconds from quota/rate-limit error messages.
    """
    if not msg:
        return default_sec

    m = re.search(r"retry in\s+([\d.]+)s", msg, re.IGNORECASE)
    if m:
        try:
            return max(1, int(float(m.group(1))))
        except Exception:
            pass

    m = re.search(r"retryDelay['\"]?\s*:\s*['\"]?(\d+)s", msg, re.IGNORECASE)
    if m:
        try:
            return max(1, int(m.group(1)))
        except Exception:
            pass

    return default_sec


def _generate_content_compat(client, model: str, contents: Any, temperature: float):
    """
    Compat layer for google-genai SDK differences:
    - some versions accept generation_config=
    - some accept config=
    - some accept neither
    """
    # 1) Try generation_config (newer style)
    try:
        return client.models.generate_content(
            model=model,
            contents=contents,
            generation_config={"temperature": temperature},
        )
    except TypeError:
        pass

    # 2) Try config (some versions use config)
    try:
        return client.models.generate_content(
            model=model,
            contents=contents,
            config={"temperature": temperature},
        )
    except TypeError:
        pass

    # 3) Fallback: no config at all
    return client.models.generate_content(
        model=model,
        contents=contents,
    )


def generate_with_gemini(
    contents: Any,
    model: str = "gemini-3-flash-preview",
    max_retries: int = 3,
    temperature: float = 0.1,
    env=None,
) -> Any:
    """
    Generic AI call.

    Returns (backward compatible):
      - dict: {"text": "...", "usage": {...}, "model": "..."}  (preferred)
      - raises on fatal errors

    `contents` can be:
      - a string prompt
      - a list like [uploaded_file, prompt] OR [prompt, uploaded_file] OR [file1, file2, prompt]
    
    NOTE: When contents includes file objects, the SDK will make GET requests
    to fetch file metadata before each generate_content() call. This is expected SDK
    behavior for file validation. You may see repeated GET requests for the same file
    IDs in logs - this is normal and cannot be avoided without modifying the SDK.
    
    Args:
        contents: Content to send to the AI service
        model: Model name to use
        max_retries: Maximum retry attempts
        temperature: Temperature for generation
        env: Optional Odoo environment (api.Environment). Used to get API key from system parameters.
    """
    if genai is None:
        raise RuntimeError("google-genai package is not installed")
    
    client = _get_client(env=env)
    last_err: Optional[Exception] = None

    _logger.debug("GEMINI API: Calling generate_content() - Model: %s, Temperature: %.2f", 
                  model, temperature)

    for attempt in range(max_retries + 1):
        try:
            if attempt > 0:
                _logger.warning("GEMINI API: Retry attempt %d/%d", attempt, max_retries)
            
            t0 = time.time()
            with _GEMINI_SEM:
                response = _generate_content_compat(client, model=model, contents=contents, temperature=temperature)
            t1 = time.time()

            text = _extract_text(response)
            usage = _extract_usage(response)
            duration_ms = int((t1 - t0) * 1000)

            _logger.debug("GEMINI API: ✓ generate_content() completed - Duration: %.2fs, Tokens: %s", 
                         duration_ms / 1000, usage)

            return {
                "text": text,
                "usage": usage,
                "model": model,
                "durationMs": duration_ms,
            }

        except genai_errors.ClientError as e:
            msg = str(e)

            # quota/rate limit
            if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                wait = _sleep_from_retry_message(msg, 10)
                time.sleep(wait)
                last_err = e
                continue

            # model not found / not allowed
            if "404" in msg or "NOT_FOUND" in msg:
                raise RuntimeError(
                    f"Model not found or not allowed: '{model}'. "
                    f"Try list_models() to see valid models for your key."
                )

            raise

        except Exception as e:
            last_err = e
            time.sleep(1)

    raise RuntimeError(f"AI call failed after retries: {last_err}")
