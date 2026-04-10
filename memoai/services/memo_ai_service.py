# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)
_LOCAL_EMBEDDER = None
_LOCAL_EMBED_MODEL = None


# Import centralized AI utilities from ai_core
# Circular import removed – memo_ai_service provides its own implementations



def call_ai(env, prompt):
    """Delegate AI call to the centralized ai_core service."""
    return _call_ai(env, prompt)



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
        payload = {
            "model": settings['openai_model'],
            "messages": [
                {"role": "system", "content": "You are an expert financial and legal analyst."},
                {"role": "user", "content": _enforce_html_prompt(prompt)},
            ],
            "temperature": settings['temperature'],
            "max_completion_tokens": settings['max_tokens'],
        }
        try:
            response = client.chat.completions.create(**payload)
        except Exception as e:
            err = str(e).lower()
            if "temperature" in err and ("unsupported" in err or "does not support" in err):
                payload.pop("temperature", None)
                response = client.chat.completions.create(**payload)
            elif "max_completion_tokens" in str(e):
                payload.pop("max_completion_tokens", None)
                payload["max_tokens"] = settings['max_tokens']
                response = client.chat.completions.create(**payload)
            else:
                raise
        text = response.choices[0].message.content.strip()
        usage = response.usage
        pt = usage.prompt_tokens if usage else 0
        ct = usage.completion_tokens if usage else 0
        
        # Calculate cost dynamically from settings
        cost = (pt * settings['prompt_cost'] + ct * settings['completion_cost']) / 1000000.0
            
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
            "generationConfig": {"temperature": settings['temperature']}
        }
        response = requests.post(url, headers={'Content-Type': 'application/json'}, json=data, timeout=60)
        
        if response.status_code == 200:
            resp_json = response.json()
            text = resp_json.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', '').strip()
            
            usage = resp_json.get('usageMetadata', {})
            pt = usage.get('promptTokenCount', 0)
            ct = usage.get('candidatesTokenCount', 0)
            
            # Calculate cost dynamically from settings
            cost = (pt * settings['prompt_cost'] + ct * settings['completion_cost']) / 1000000.0
                
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
        payload = {
            "model": settings['azure_deployment'],
            "messages": [
                {"role": "system", "content": "You are an expert financial and legal analyst."},
                {"role": "user", "content": _enforce_html_prompt(prompt)},
            ],
            "temperature": settings['temperature'],
            "max_completion_tokens": settings['max_tokens'],
        }
        try:
            response = client.chat.completions.create(**payload)
        except Exception as e:
            err = str(e).lower()
            if "temperature" in err and ("unsupported" in err or "does not support" in err):
                payload.pop("temperature", None)
                response = client.chat.completions.create(**payload)
            elif "max_completion_tokens" in str(e):
                payload.pop("max_completion_tokens", None)
                payload["max_tokens"] = settings['max_tokens']
                response = client.chat.completions.create(**payload)
            else:
                raise
        text = response.choices[0].message.content.strip()
        usage = response.usage
        pt = usage.prompt_tokens if usage else 0
        ct = usage.completion_tokens if usage else 0
        
        # Calculate cost dynamically from settings
        cost = (pt * settings['prompt_cost'] + ct * settings['completion_cost']) / 1000000.0
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
    """
    Get vector embedding for a chunk of text.
    Resilient multi-provider support with Gemini multi-tier fallback.
    """
    settings = _get_ai_settings(env)
    provider = settings['provider']
    
    # Sanitize input: ensure we have actual text beyond just whitespace
    clean_text = (text or "").strip()
    if not clean_text:
        # Fallback for empty chunks (prevents Gemini API 400 error)
        return [0.0] * 768 
    
    # Trim to safe limit (approx 9k chars)
    payload = clean_text[:9000]

    if settings.get('use_local_embeddings'):
        global _LOCAL_EMBEDDER, _LOCAL_EMBED_MODEL
        local_model = (settings.get('local_embedding_model') or 'sentence-transformers/all-MiniLM-L6-v2').strip()
        try:
            from sentence_transformers import SentenceTransformer
            if _LOCAL_EMBEDDER is None or _LOCAL_EMBED_MODEL != local_model:
                _LOCAL_EMBEDDER = SentenceTransformer(local_model)
                _LOCAL_EMBED_MODEL = local_model
            vec = _LOCAL_EMBEDDER.encode(payload, normalize_embeddings=True)
            return vec.tolist() if hasattr(vec, 'tolist') else list(vec)
        except Exception as e:
            raise ValueError(
                "Local embedding failed. Install dependencies and verify model name. "
                f"Details: {str(e)}"
            )

    if provider == 'gemini':
        from google import genai
        api_key = (settings['gemini_key'] or "").strip()
        if not api_key:
            raise ValueError("Gemini API Key missing")
            
        client = genai.Client(api_key=api_key)
        
        # We attempt a resilient multi-tier fallback with both prefixed and raw names
        # Tiering: To prevent 404 delays on v1beta, we lead with the currently working preview model
        model_tiers = ["gemini-embedding-2-preview", "text-embedding-004", "embedding-001"]
        
        last_error = None
        for model_name in model_tiers:
            try:
                # The Gemini SDK expects 'contents' as a list/collection of parts
                result = client.models.embed_content(
                    model=model_name,
                    contents=[payload]
                )
                if result and result.embeddings:
                    return result.embeddings[0].values
            except Exception as e:
                _logger.warning("Gemini Embed failed for %s: %s", model_name, str(e))
                last_error = e
                continue
        
        raise ValueError(f"Gemini SDK Embed Error (All 6 Tier permutations failed): {str(last_error)}")
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
        emb_model = (settings.get('azure_embedding_deployment') or settings.get('azure_deployment') or '').strip()
        if not emb_model:
            raise ValueError(
                "Azure embedding deployment is missing. "
                "Set Memo AI -> Configuration -> Settings -> Embedding Deployment."
            )
        try:
            res = client.embeddings.create(input=text[:8000], model=emb_model)
            return res.data[0].embedding
        except Exception as e:
            msg = str(e)
            if "DeploymentNotFound" in msg:
                raise ValueError(
                    f"Azure embedding deployment '{emb_model}' not found. "
                    "Create it in Azure AI Studio and set the same name in Memo AI settings."
                )
            raise
    
    raise ValueError("Configured AI Provider does not support Embeddings.")

