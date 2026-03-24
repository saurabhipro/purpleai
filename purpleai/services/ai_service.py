# -*- coding: utf-8 -*-
"""
ai_service.py
─────────────
Central AI dispatcher — the ONLY import all callers should use.

Usage
-----
    from odoo.addons.purpleai.services.ai_service import generate

    result = generate(contents="Summarise this text …", env=self.env)
    # result: {"text": str, "usage": {...}, "model": str, "provider": str, "durationMs": int}

The dispatcher reads the system parameter ``tender_ai.ai_provider``
(gemini | mistral | azure) and forwards the call to the correct provider.
If the parameter is absent it defaults to ``gemini``.

Supported providers
-------------------
    gemini  → GeminiService  (google-genai SDK)
    mistral → MistralService (Mistral REST API)
    azure   → AzureService   (Azure OpenAI REST API)
    openai  → OpenAIService  (OpenAI GPT REST API)

Adding a new provider
---------------------
1. Create ``my_provider_service.py`` extending ``BaseAIService``.
2. Register it in the ``_REGISTRY`` dict below.
3. Add the corresponding ``ir.config_parameter`` value and UI option.
That's it — no other file needs changing.
"""

import logging
from typing import Any, Dict, List, Optional, Type

from .base_ai_service import BaseAIService
from .gemini_service   import GeminiService
from .azure_service    import AzureService
from .mistral_service  import MistralService
from .openai_service   import OpenAIService

_logger = logging.getLogger(__name__)

# ── Provider registry ─────────────────────────────────────────────────────────
# Maps the string stored in tender_ai.ai_provider → service class
_REGISTRY: Dict[str, Type[BaseAIService]] = {
    "gemini":  GeminiService,
    "mistral": MistralService,
    "azure":   AzureService,
    "openai":  OpenAIService,
}

_DEFAULT_PROVIDER = "gemini"

# ── Per-class singleton cache ─────────────────────────────────────────────────
_instances: Dict[str, BaseAIService] = {}


def _get_service(provider: str) -> BaseAIService:
    """Return (or create) the singleton instance for *provider*."""
    if provider not in _REGISTRY:
        supported = ", ".join(_REGISTRY)
        raise ValueError(
            f"Unknown AI provider '{provider}'. Supported providers: {supported}"
        )
    if provider not in _instances:
        _instances[provider] = _REGISTRY[provider]()
    return _instances[provider]


def _resolve_provider(env) -> str:
    """Read tender_ai.ai_provider from Odoo system parameters."""
    if not env:
        return _DEFAULT_PROVIDER
    try:
        provider = (
            env["ir.config_parameter"]
            .sudo()
            .get_param("tender_ai.ai_provider", _DEFAULT_PROVIDER)
        )
        return (provider or _DEFAULT_PROVIDER).strip().lower()
    except Exception:
        return _DEFAULT_PROVIDER


# ════════════════════════════════════════════════════════════════════════════
# Public API
# ════════════════════════════════════════════════════════════════════════════

def generate(
    contents: Any,
    *,
    model: Optional[str] = None,
    temperature: float = 0.1,
    max_retries: int = 3,
    provider: Optional[str] = None,
    env=None,
) -> Dict[str, Any]:
    """
    Dispatch an AI generation request to the configured provider.

    Parameters
    ----------
    contents    : str | list
        Prompt text or a list of message dicts (``{"role": …, "content": …}``).
    model       : str, optional
        Override the default model for this call only.
    temperature : float
        Sampling temperature (0.0 = deterministic, 1.0 = creative).
    max_retries : int
        Number of additional attempts after a transient failure.
    provider    : str, optional
        Force a specific provider (``"gemini"``, ``"azure"``, ``"mistral"``).
        If omitted, reads ``tender_ai.ai_provider`` from system parameters.
    env         : odoo.api.Environment, optional
        Odoo environment for reading system parameters (strongly recommended).

    Returns
    -------
    dict with keys: ``text``, ``usage``, ``model``, ``provider``, ``durationMs``
    """
    chosen = (provider or _resolve_provider(env)).strip().lower()
    _logger.debug("AI dispatcher: provider=%s  model=%s", chosen, model or "(default)")

    service = _get_service(chosen)
    return service.generate(
        contents,
        model=model,
        temperature=temperature,
        max_retries=max_retries,
        env=env,
    )


def list_models(
    provider: Optional[str] = None,
    env=None,
) -> List[str]:
    """..."""
    chosen = (provider or _resolve_provider(env)).strip().lower()
    service = _get_service(chosen)
    return service.list_models(env=env)


def upload_file(
    file_path: str,
    provider: Optional[str] = None,
    env=None,
    **kwargs,
) -> Any:
    """
    Prepare a file (PDF, Image, etc.) for processing using the current provider.

    Returns a provider-specific file object (Gemini) or a 
    data-proxy dict (Azure/Mistral) that can be passed to generate().
    """
    chosen = (provider or _resolve_provider(env)).strip().lower()
    service = _get_service(chosen)
    return service.upload_file(file_path, env=env, **kwargs)


def get_service(
    provider: Optional[str] = None,
    env=None,
) -> BaseAIService:
    """
    Return the underlying service instance for advanced use.

    Example – calling Gemini-specific file upload::

        from odoo.addons.purpleai.services.ai_service import get_service
        from odoo.addons.purpleai.services.gemini_service import GeminiService

        svc = get_service(provider="gemini", env=self.env)
        if isinstance(svc, GeminiService):
            file_obj = svc.upload_file("/tmp/document.pdf", env=self.env)
    """
    chosen = (provider or _resolve_provider(env)).strip().lower()
    return _get_service(chosen)


def available_providers() -> List[str]:
    """Return the list of registered provider names."""
    return list(_REGISTRY)


def register_provider(name: str, cls: Type[BaseAIService]) -> None:
    """
    Register a custom AI provider at runtime.

    Parameters
    ----------
    name : str
        The identifier used in ``tender_ai.ai_provider`` (e.g. ``"openai"``).
    cls  : Type[BaseAIService]
        A class that extends ``BaseAIService`` and implements ``generate()``.

    Example::

        from odoo.addons.purpleai.services.ai_service import register_provider
        from my_module.services.openai_service import OpenAIService

        register_provider("openai", OpenAIService)
    """
    if not (isinstance(cls, type) and issubclass(cls, BaseAIService)):
        raise TypeError(f"cls must be a subclass of BaseAIService, got {cls!r}")
    _REGISTRY[name.strip().lower()] = cls
    # Evict cached instance so next call re-creates with new class
    _instances.pop(name.strip().lower(), None)
    _logger.info("AI dispatcher: registered provider '%s' → %s", name, cls.__name__)
