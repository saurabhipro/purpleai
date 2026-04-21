# -*- coding: utf-8 -*-
"""Thin wrapper over AI Core.

Invoice **document extraction** must send the actual PDF/images to the provider.
The legacy ``call_ai`` path only posts plain text; using it with file paths in the
prompt breaks vision and produces hallucinated ``value`` / ``box_2d``. When
AI Core provider is **gemini**, we use ``GeminiService`` with real file uploads
(google-genai SDK), matching the pre-centralization behaviour.
"""

import logging
import os
import base64
import io

from odoo.addons.ai_core.services.ai_core_service import (
    call_ai as _call_ai,
    get_embedding as _get_embedding,
    _get_ai_settings as _get_ai_settings,
)

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

try:
    from PIL import Image as PILImage
except ImportError:
    PILImage = None

_logger = logging.getLogger(__name__)


def _model_for_provider(settings, provider):
    """Human-readable model id stored on extraction rows + dashboard."""
    p = (provider or '').lower().strip()
    if p == 'gemini':
        return (settings.get('gemini_model') or '').strip() or None
    if p == 'openai':
        return (settings.get('openai_model') or '').strip() or None
    if p == 'azure':
        return (settings.get('azure_deployment') or '').strip() or None
    if p == 'mistral':
        return (settings.get('mistral_model') or '').strip() or None
    return None


def _normalize_call_ai_response(raw, settings, provider_key):
    """Memo/Core ``call_ai`` returns snake_case tokens and no provider/model.
    Match the dict shape from ``GeminiService._build_response`` for one downstream path."""
    if not isinstance(raw, dict):
        raw = {'text': str(raw)}
    pt = int(raw.get('prompt_tokens') or 0)
    ct = int(raw.get('completion_tokens') or 0)
    return {
        'text': raw.get('text') or '',
        'usage': {
            'promptTokens': pt,
            'outputTokens': ct,
            'totalTokens': int(raw.get('total_tokens') or (pt + ct)),
        },
        'provider': provider_key,
        'model': _model_for_provider(settings, provider_key) or '',
        'durationMs': int(raw.get('duration_ms') or 0),
    }


def _content_part_to_text(part):
    """Normalize one item from ``contents`` (dict message, plain str, or other)."""
    if isinstance(part, dict):
        return str(part.get('content', part))
    return str(part)


def _is_existing_file_path(part):
    if not isinstance(part, str):
        return False
    p = part.strip()
    return bool(p) and os.path.isfile(p)


def _extract_text_from_pdf(file_path, max_pages=10, max_chars=3000):
    """Extract text from a searchable PDF using PyMuPDF.
    Limits output to first N characters to avoid bloating prompt.
    Returns tuple (text, is_searchable) where is_searchable indicates if PDF has text layer."""
    if not fitz:
        return '', False
    
    doc = fitz.open(file_path)
    all_text = []
    total_chars = 0
    
    num_pages = min(len(doc), max_pages)
    for page_num in range(num_pages):
        if total_chars >= max_chars:
            break
        page = doc[page_num]
        text = page.get_text("text")
        if text:
            all_text.append(text)
            total_chars += len(text)
    
    doc.close()
    
    # Consider searchable if we found meaningful text (at least 50 chars)
    extracted = '\n'.join(all_text)
    if len(extracted) > max_chars:
        extracted = extracted[:max_chars] + "\n[... text truncated ...]"
    is_searchable = total_chars > 50
    
    _logger.info("PDF text extraction: %s, extracted=%d chars (limited to %d), searchable=%s", 
                 os.path.basename(file_path), total_chars, max_chars, is_searchable)
    
    return extracted, is_searchable


def _pdf_to_base64_images(file_path, max_pages=5, dpi=150):
    """Convert PDF pages to base64-encoded PNG images for vision API."""
    if not fitz:
        raise ImportError("PyMuPDF (fitz) is required for PDF processing")
    
    images = []
    doc = fitz.open(file_path)
    num_pages = min(len(doc), max_pages)
    
    for page_num in range(num_pages):
        page = doc[page_num]
        # Render page to image
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=mat)
        
        # Convert to PNG bytes
        img_bytes = pix.tobytes("png")
        
        # Encode as base64
        b64_str = base64.b64encode(img_bytes).decode('utf-8')
        images.append({
            'page': page_num + 1,
            'base64': b64_str,
            'media_type': 'image/png'
        })
    
    doc.close()
    return images


def _image_to_base64(file_path):
    """Convert image file to base64 for vision API."""
    ext = os.path.splitext(file_path)[1].lower()
    media_types = {
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.gif': 'image/gif',
        '.webp': 'image/webp',
    }
    media_type = media_types.get(ext, 'image/png')
    
    with open(file_path, 'rb') as f:
        img_bytes = f.read()
    
    b64_str = base64.b64encode(img_bytes).decode('utf-8')
    return [{
        'page': 1,
        'base64': b64_str,
        'media_type': media_type
    }]


def _call_azure_vision(settings, prompt, file_paths):
    """Call Azure OpenAI with vision (images) support."""
    from openai import AzureOpenAI
    
    api_key = settings['azure_key']
    endpoint = settings['azure_endpoint']
    deployment = settings['azure_deployment']
    api_version = settings.get('azure_api_version', '2024-12-01-preview')
    
    if not api_key or not endpoint:
        raise ValueError("Azure OpenAI credentials not configured")
    
    client = AzureOpenAI(
        api_key=api_key,
        azure_endpoint=endpoint,
        api_version=api_version,
    )
    
    # Build messages with images
    content_parts = [{"type": "text", "text": prompt}]
    
    for fp in file_paths:
        ext = os.path.splitext(fp)[1].lower()
        
        if ext == '.pdf':
            images = _pdf_to_base64_images(fp)
        else:
            images = _image_to_base64(fp)
        
        for img in images:
            content_parts.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:{img['media_type']};base64,{img['base64']}",
                    "detail": "high"
                }
            })
    
    _logger.info("Azure Vision API call: deployment=%s, images=%d", deployment, len(content_parts) - 1)
    
    response = client.chat.completions.create(
        model=deployment,
        messages=[
            {"role": "user", "content": content_parts}
        ],
        max_tokens=settings.get('max_tokens', 4096),
    )
    
    text = response.choices[0].message.content.strip()
    usage = response.usage
    pt = usage.prompt_tokens if usage else 0
    ct = usage.completion_tokens if usage else 0
    
    return {
        'text': text,
        'prompt_tokens': pt,
        'completion_tokens': ct,
        'total_tokens': pt + ct,
    }


def generate(
    contents,
    *,
    model=None,
    temperature=0.1,
    max_retries=3,
    provider=None,
    env=None,
    enforce_html=True,
):
    """Run a generation request.

    For **gemini**, ``contents`` may be a list mixing instruction strings and
    local file paths; paths are uploaded and sent as multimodal parts.

    For **openai** / **azure**, content is flattened to text and sent via Memo/Core
    (use null ``box_2d`` in extraction prompts when coordinates are unreliable).
    """
    settings = _get_ai_settings(env)
    resolved = (provider or settings.get('provider') or 'openai').lower().strip()

    # Debug: Log which provider and credentials are being used
    _logger.info(
        "Invoice AI generate: provider=%s, azure_endpoint=%s, azure_key_present=%s, azure_deployment=%s",
        resolved,
        settings.get('azure_endpoint', 'NOT SET'),
        'YES' if settings.get('azure_key') else 'NO',
        settings.get('azure_deployment', 'NOT SET'),
    )

    if resolved == 'gemini':
        from odoo.addons.ai_core.services.gemini_service import GeminiService

        svc = GeminiService()
        parts = contents if isinstance(contents, list) else [contents]
        text_segments = []
        file_paths = []
        for part in parts:
            if _is_existing_file_path(part):
                file_paths.append(part.strip())
            else:
                text_segments.append(_content_part_to_text(part) if isinstance(part, dict) else str(part))
        prompt = '\n\n'.join(s for s in text_segments if s)
        uploaded = []
        for fp in file_paths:
            uploaded.append(svc.upload_file(fp, env=env))
        multimodal = [prompt] + uploaded if prompt else uploaded
        if not multimodal:
            raise ValueError('Gemini generate: empty contents (no text and no files).')
        gemini_model = model or (settings.get('gemini_model') or '').strip() or None
        temp = float(settings.get('temperature', temperature))
        return svc.generate(
            multimodal,
            model=gemini_model,
            temperature=temp,
            max_retries=max_retries,
            env=env,
        )

    if resolved == 'mistral':
        from odoo.addons.ai_core.services.mistral_service import MistralService, _is_azure_ocr_endpoint, _get_mistral_endpoint

        svc = MistralService()
        api_endpoint = _get_mistral_endpoint(env)
        is_azure_ocr = _is_azure_ocr_endpoint(api_endpoint)

        parts = contents if isinstance(contents, list) else [contents]
        text_segments = []
        file_proxies = []
        for part in parts:
            if _is_existing_file_path(part):
                fp = part.strip()
                ext = os.path.splitext(fp)[1].lower()
                if ext == '.pdf':
                    if is_azure_ocr:
                        # Azure OCR: send original PDF as base64 data-URI (not rendered images)
                        import base64 as _b64
                        with open(fp, 'rb') as f:
                            pdf_b64 = _b64.b64encode(f.read()).decode('utf-8')
                        file_proxies.append({
                            "type": "file_proxy",
                            "url": f"data:application/pdf;base64,{pdf_b64}",
                        })
                        _logger.info("Mistral Azure OCR: sending original PDF as base64 (%d chars)", len(pdf_b64))
                    else:
                        # Render ALL pages as images for Pixtral vision
                        page_images = _pdf_to_base64_images(fp, max_pages=10, dpi=200)
                        for img in page_images:
                            file_proxies.append({
                                "type": "file_proxy",
                                "url": f"data:{img['media_type']};base64,{img['base64']}",
                            })
                        _logger.info("Mistral vision: rendered %d PDF pages as images", len(page_images))
                else:
                    # Image file - use upload_file which converts to data URL
                    file_proxies.append(svc.upload_file(fp, env=env))
            elif isinstance(part, dict) and part.get("type") == "file_proxy":
                file_proxies.append(part)
            else:
                text_segments.append(_content_part_to_text(part) if isinstance(part, dict) else str(part))

        prompt_text = '\n\n'.join(s for s in text_segments if s)
        # Build multimodal content: text + images in a single user message
        multimodal_content = []
        if prompt_text:
            multimodal_content.append(prompt_text)
        multimodal_content.extend(file_proxies)

        if not multimodal_content:
            raise ValueError('Mistral generate: empty contents (no text and no files).')

        mistral_model = model or (settings.get('mistral_model') or '').strip() or 'mistral-document-ai-2505'
        temp = float(settings.get('temperature', temperature))
        _logger.info("Mistral vision extraction: model=%s, images=%d, prompt=%d chars",
                     mistral_model, len(file_proxies), len(prompt_text))
        return svc.generate(
            multimodal_content,
            model=mistral_model,
            temperature=temp,
            max_retries=max_retries,
            env=env,
        )

    if isinstance(contents, list):
        # For Azure/OpenAI: extract text from PDFs instead of just flattening paths
        text_parts = []
        for msg in contents:
            if _is_existing_file_path(msg):
                file_path = msg.strip()
                ext = os.path.splitext(file_path)[1].lower()
                if ext == '.pdf':
                    extracted, is_searchable = _extract_text_from_pdf(file_path)
                    if is_searchable and extracted:
                        text_parts.append(extracted)
                        _logger.info("Added PDF text to prompt: %d chars", len(extracted))
                    else:
                        _logger.warning("PDF not searchable or empty: %s", file_path)
                else:
                    # For images, just note the filename (text-only path)
                    text_parts.append(f"[Image file: {os.path.basename(file_path)}]")
            else:
                text_parts.append(_content_part_to_text(msg) if isinstance(msg, dict) else str(msg))
        prompt = '\n\n'.join(text_parts)
        _logger.info("Final prompt for Azure/OpenAI: %d chars, provider=%s", len(prompt), resolved)
    else:
        prompt = str(contents)
    raw = _call_ai(env, prompt, enforce_html=enforce_html)
    _logger.info("Azure/OpenAI response text length: %d chars", len(raw.get('text', '') if isinstance(raw, dict) else str(raw)))
    return _normalize_call_ai_response(raw, settings, resolved)


def upload_file(file_path: str, provider: str = None, env=None, **kwargs):
    """Return the path; ``generate`` uploads when provider is Gemini."""
    return file_path


def list_models(provider: str = None, env=None):
    _logger.debug('list_models called – not implemented in ai_core wrapper')
    return []


def get_service(provider: str = None, env=None):
    return None


def available_providers():
    return ['openai', 'gemini', 'azure', 'mistral']


def register_provider(name: str, cls):
    _logger.warning('register_provider called on wrapper – operation ignored')
