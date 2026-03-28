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
        'gemini_model':     config.get_param('memo_ai.gemini_model', 'gemini-2.5-flash'),
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


# ───────────────────────────────────────────────────────────────────────────
# AI Output HTML Enforcer
# ───────────────────────────────────────────────────────────────────────────
def _enforce_html_prompt(prompt):
    return f"{prompt}\n\nIMPORTANT FORMATTING INSTRUCTION:\nFormat your entire response using ONLY valid HTML tags (like <ul>, <li>, <p>, <strong>, <br>). Do NOT use Markdown (no asterisks or hashtags). Do NOT wrap your response in ```html codeblocks. Return only the raw HTML output."

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
                {"role": "user", "content": _enforce_html_prompt(prompt)},
            ],
            temperature=0.3,
            max_tokens=4096,
        )
        text = response.choices[0].message.content.strip()
        usage = response.usage
        pt = usage.prompt_tokens if usage else 0
        ct = usage.completion_tokens if usage else 0
        
        # Simple cost approximation
        cost = 0.0
        model = settings['openai_model'].lower()
        if 'mini' in model:
            cost = (pt * 0.15 + ct * 0.60) / 1000000.0
        else:
            cost = (pt * 2.50 + ct * 10.00) / 1000000.0
            
        return {
            'text': text,
            'prompt_tokens': pt,
            'completion_tokens': ct,
            'total_tokens': pt + ct,
            'cost': cost
        }
    except Exception as e:
        _logger.error("OpenAI call failed: %s", str(e))
        raise


def call_gemini(env, prompt, settings=None):
    """Call Google Gemini Pro using REST API."""
    if settings is None:
        settings = _get_ai_settings(env)
    api_key = settings['gemini_key']
    if not api_key:
        raise ValueError(
            "Gemini API key is not configured. "
            "Go to Memo AI → Configuration → Settings to add your key."
        )
    try:
        import requests
        api_key = api_key.strip()
        model_name = settings['gemini_model'].strip()
        clean_model = model_name if not model_name.startswith('models/') else model_name.replace('models/', '')
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{clean_model}:generateContent?key={api_key}"
        data = {
            "contents": [{"parts": [{"text": _enforce_html_prompt(prompt)}]}],
            "generationConfig": {"temperature": 0.3}
        }
        response = requests.post(url, headers={'Content-Type': 'application/json'}, json=data, timeout=60)
        
        if response.status_code == 200:
            resp_json = response.json()
            text = resp_json.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', '').strip()
            
            usage = resp_json.get('usageMetadata', {})
            pt = usage.get('promptTokenCount', 0)
            ct = usage.get('candidatesTokenCount', 0)
            
            # Simple cost approximation
            cost = 0.0
            if 'pro' in clean_model.lower():
                cost = (pt * 1.25 + ct * 5.00) / 1000000.0
            else:
                cost = (pt * 0.075 + ct * 0.30) / 1000000.0
                
            return {
                'text': text,
                'prompt_tokens': pt,
                'completion_tokens': ct,
                'total_tokens': pt + ct,
                'cost': cost
            }
        else:
            raise ValueError(f"Gemini API Error {response.status_code}: {response.text}")
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
                {"role": "user", "content": _enforce_html_prompt(prompt)},
            ],
            temperature=0.3,
            max_tokens=4096,
        )
        text = response.choices[0].message.content.strip()
        usage = response.usage
        pt = usage.prompt_tokens if usage else 0
        ct = usage.completion_tokens if usage else 0
        
        cost = (pt * 2.50 + ct * 10.00) / 1000000.0
        return {
            'text': text,
            'prompt_tokens': pt,
            'completion_tokens': ct,
            'total_tokens': pt + ct,
            'cost': cost
        }
    except Exception as e:
        _logger.error("Azure OpenAI call failed: %s", str(e))
        raise

# ───────────────────────────────────────────────────────────────────────────
# Vector Embeddings
# ───────────────────────────────────────────────────────────────────────────
def get_embedding(env, text):
    """Generate a high-dimensional vector embedding for RAG chunks."""
    settings = _get_ai_settings(env)
    provider = settings['provider']
    
    if provider == 'gemini':
        from google import genai
        api_key = settings['gemini_key'].strip()
        client = genai.Client(api_key=api_key)
        
        try:
            # 1. Flagship text-embedding-004
            result = client.models.embed_content(
                model="text-embedding-004",
                contents=text[:9000]
            )
            return result.embeddings[0].values
        except Exception as e:
            # 2. Universal gemini-embedding-001
            try:
                fallback = client.models.embed_content(
                    model="gemini-embedding-001",
                    contents=text[:9000]
                )
                return fallback.embeddings[0].values
            except Exception:
                # 3. Newest gemini-embedding-2-preview
                try:
                    p_fallback = client.models.embed_content(
                        model="gemini-embedding-2-preview",
                        contents=text[:9000]
                    )
                    return p_fallback.embeddings[0].values
                except Exception as final_err:
                    raise ValueError(f"Gemini SDK Embed Error (All Models Failed: 004, 001, Preview-2): {str(e)} | Final: {str(final_err)}")
    elif provider == 'openai':
        from openai import OpenAI
        client = OpenAI(api_key=settings['openai_key'])
        res = client.embeddings.create(input=text[:8000], model="text-embedding-3-small")
        return res.data[0].embedding
        
    elif provider == 'azure':
        from openai import AzureOpenAI
        client = AzureOpenAI(
            api_key=settings['azure_key'],
            azure_endpoint=settings['azure_endpoint'],
            api_version=settings['azure_api_version']
        )
        res = client.embeddings.create(input=text[:8000], model="text-embedding-3-small")
        return res.data[0].embedding
    
    raise ValueError("Configured AI Provider does not support Embeddings.")
