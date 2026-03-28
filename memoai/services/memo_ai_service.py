# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)


def _get_ai_settings(env):
    """Read AI provider settings from memo_ai's own config parameters."""
    config = env['ir.config_parameter'].sudo()
    return {
        'provider':         config.get_param('memo_ai.ai_provider', 'openai'),
        'openai_key':       config.get_param('memo_ai.openai_api_key', ''),
        'openai_model':     config.get_param('memo_ai.openai_model', 'gpt-4o'),
        'gemini_key':       config.get_param('memo_ai.gemini_api_key', ''),
        'gemini_model':     config.get_param('memo_ai.gemini_model', 'gemini-1.5-pro'),
        'azure_key':        config.get_param('memo_ai.azure_api_key', ''),
        'azure_endpoint':   config.get_param('memo_ai.azure_endpoint', ''),
        'azure_deployment': config.get_param('memo_ai.azure_deployment', ''),
        'azure_api_version':config.get_param('memo_ai.azure_api_version', '2024-12-01-preview'),
    }


def call_ai(env, prompt):
    """
    Dispatch to the configured AI provider.
    Reads from memo_ai.* ir.config_parameter keys — completely independent of purpleai.
    """
    settings = _get_ai_settings(env)
    provider = settings['provider']

    if provider == 'gemini':
        return call_gemini(env, prompt, settings)
    elif provider == 'azure':
        return call_azure_openai(env, prompt, settings)
    else:
        return call_openai(env, prompt, settings)


def call_openai(env, prompt, settings=None):
    """Call OpenAI chat completion."""
    if settings is None:
        settings = _get_ai_settings(env)
    api_key = settings['openai_key']
    if not api_key:
        raise ValueError(
            "OpenAI API key is not configured. "
            "Go to Memo AI → Configuration → Settings to add your key."
        )
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=settings['openai_model'],
            messages=[
                {"role": "system", "content": "You are an expert financial and legal analyst."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=4096,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        _logger.error("OpenAI call failed: %s", str(e))
        raise


def call_gemini(env, prompt, settings=None):
    """Call Google Gemini Pro."""
    if settings is None:
        settings = _get_ai_settings(env)
    api_key = settings['gemini_key']
    if not api_key:
        raise ValueError(
            "Gemini API key is not configured. "
            "Go to Memo AI → Configuration → Settings to add your key."
        )
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(settings['gemini_model'])
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        _logger.error("Gemini call failed: %s", str(e))
        raise


def call_azure_openai(env, prompt, settings=None):
    """Call Azure OpenAI."""
    if settings is None:
        settings = _get_ai_settings(env)
    api_key = settings['azure_key']
    endpoint = settings['azure_endpoint']
    if not api_key or not endpoint:
        raise ValueError(
            "Azure OpenAI credentials are not configured. "
            "Go to Memo AI → Configuration → Settings to add your credentials."
        )
    try:
        from openai import AzureOpenAI
        client = AzureOpenAI(
            api_key=api_key,
            azure_endpoint=endpoint,
            api_version=settings['azure_api_version'],
        )
        response = client.chat.completions.create(
            model=settings['azure_deployment'],
            messages=[
                {"role": "system", "content": "You are an expert financial and legal analyst."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=4096,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        _logger.error("Azure OpenAI call failed: %s", str(e))
        raise
