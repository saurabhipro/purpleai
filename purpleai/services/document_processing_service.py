# -*- coding: utf-8 -*-
import os
import re
import json
import logging
import base64
import io
from odoo import fields, _
from odoo.addons.purpleai.services import ai_service

try:
    import fitz
except ImportError:
    fitz = None

_logger = logging.getLogger(__name__)


def _extract_json(raw_text: str) -> str:
    """
    Robustly extract a JSON object from an AI response string.

    Handles all common real-world formats:
      1. Plain JSON:              {"key": "value"}
      2. Markdown-fenced JSON:   ```json\n{...}\n```
      3. Markdown-fenced plain:  ```\n{...}\n```
      4. JSON buried in prose:   "Here is the data:\n{...}\nLet me know..."
      5. JSON with trailing text: {"key": "val"} Note: ...
    
    Returns the cleaned JSON string, or empty string if nothing found.
    """
    if not raw_text:
        return ''

    text = raw_text.strip()

    # Strategy 1: Markdown code fences  ```json ... ``` or ``` ... ```
    fence_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    if fence_match:
        candidate = fence_match.group(1).strip()
        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            pass

    # Strategy 2: Direct parse — the whole response is JSON
    try:
        json.loads(text)
        return text
    except json.JSONDecodeError:
        pass

    # Strategy 3: Find the first '{' and last '}' — extract largest JSON block
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1 and end > start:
        candidate = text[start:end + 1]
        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            # Strategy 4: Walk backwards from rfind to find valid JSON
            # (handles trailing text after the closing brace)
            for i in range(end, start, -1):
                if text[i] == '}':
                    candidate = text[start:i + 1]
                    try:
                        json.loads(candidate)
                        return candidate
                    except json.JSONDecodeError:
                        continue

    _logger.warning("_extract_json: no valid JSON found in response: %.200s", raw_text)
    return ''


def process_document(env, client, file_path, filename):
    """
    Orchestrates the AI extraction and record creation for a file.
    Optimized to perform validation and highlighting in a single pass.

    """
    # 1. Prepare Prompt
    template = client.extraction_master_id
    fields_to_extract = template.field_ids.filtered(lambda f: f.active)
    if not fields_to_extract:
        _logger.warning("No active fields in template %s for client %s", template.name, client.name)
        return False

    field_prompts = [f"- {f.field_key}: {f.instruction}" for f in fields_to_extract]
    field_list = "\n".join(field_prompts)

    rules_to_eval = template.rule_ids.filtered(lambda r: r.active and r.eval_type == 'ai')
    rule_prompts = [f"- {r.rule_code}: {r.description}" for r in rules_to_eval]
    rule_list = "\n".join(rule_prompts) if rule_prompts else ""
    
    system_prompt = (
        "You are a specialized data extraction AI. "
        "Extract fields from the document. Return a JSON object with: "
        "'value', 'box_2d' ([ymin, xmin, ymax, xmax] 0-1000), 'page_number' (1-indexed).\n\n"
    )

    if rule_list:
        system_prompt += (
            "Additionally, evaluate these VALIDATION RULES. "
            "Add a 'validations' key to your JSON with 'status', 'msg', 'box_2d', 'page_number'.\n"
            f"RULES TO EVALUATE:\n{rule_list}\n\n"
        )

    system_prompt += f"FIELDS TO EXTRACT:\n{field_list}"

    # 2. Call AI
    uploaded = ai_service.upload_file(file_path, env=env)
    res = ai_service.generate([system_prompt, uploaded], env=env, max_retries=0)
    
    raw_text = res.get('text', '') if isinstance(res, dict) else str(res)
    usage = res.get('usage', {})

    p_tok = usage.get('promptTokens', 0)
    o_tok = usage.get('outputTokens', 0)
    
    _logger.info(
        "AI response for %s [%s tokens]: %.300s%s",
        filename, p_tok + o_tok, raw_text, '...' if len(raw_text) > 300 else ''
    )

    # ── Robust JSON extraction ────────────────────────────────────────────────
    json_str = _extract_json(raw_text)
    if not json_str:
        _logger.error("Could not extract JSON from AI response for %s. Raw: %s", filename, raw_text[:500])

    # 3. Validation and Single-Pass Rendering
    # Create the result record first without the PDF to get an ID for the processor
    ResultModel = env['purple_ai.extraction_result']
    cost = ResultModel._get_estimated_cost(res.get('provider'), res.get('model'), p_tok, o_tok)
    
    result_rec = ResultModel.create({
        'client_id': client.id,
        'filename': filename,
        'raw_response': raw_text,
        'extracted_data': json_str or '{}',
        'state': 'done' if json_str else 'error',
        'error_log': None if json_str else f'Could not parse JSON from AI response:\n{raw_text[:1000]}',
        'provider': res.get('provider'),
        'model_used': res.get('model'),
        'duration_ms': res.get('durationMs', 0),
        'prompt_tokens': p_tok,
        'output_tokens': o_tok,
        'total_tokens': p_tok + o_tok,
        'cost': cost
    })


    # Create processor and get failures immediately
    proc = env['purple_ai.invoice_processor'].create_from_extraction(result_rec.id)
    failures = proc.action_validate() or []
    
    # Render PDF highlights ONCE (Yellow for data, Red for failures)
    try:
        extracted_json = json.loads(json_str)
        annotated_pdf = apply_pdf_highlights(file_path, extracted_json, failures)
        if annotated_pdf:
            result_rec.write({
                'pdf_file': annotated_pdf,
                'pdf_filename': f"annotated_{filename}"
            })
        else:
            # Fallback to direct read if highlighting failed
            with open(file_path, 'rb') as f:
                result_rec.write({
                    'pdf_file': base64.b64encode(f.read()),
                    'pdf_filename': filename
                })
    except Exception as e:
        _logger.error("Highlighting or post-processing failed for %s: %s", filename, str(e))
    
    return result_rec

def apply_pdf_highlights(file_path, extracted_json, failures=None):
    """Uses fitz to draw highlights. Yellow for data, Red for failures."""
    if not fitz:
        _logger.warning("fitz (PyMuPDF) is not installed. Highlighting skipped.")
        return False
    
    failures = failures or []
    failed_fields = {f['field']: f['msg'] for f in failures}

    try:
        doc = fitz.open(file_path)
        for key, data in extracted_json.items():
            if not isinstance(data, dict):
                continue
            
            box = data.get('box_2d')
            p_num = data.get('page_number')
            
            if not (box and len(box) == 4 and p_num):
                continue

            page_idx = int(p_num) - 1
            if not (0 <= page_idx < len(doc)):
                continue

            page = doc[page_idx]
            w, h = page.rect.width, page.rect.height

            ymin, xmin, ymax, xmax = [float(v) for v in box]

            # Validate: coordinates must be in 0–1000 range
            if not all(0 <= v <= 1000 for v in (ymin, xmin, ymax, xmax)):
                _logger.debug("Skipping out-of-range box_2d for field '%s': %s", key, box)
                continue

            # Validate: box must not cover more than 70% of either dimension
            # (prevents full-page yellow overlay from imprecise AI coordinates)
            width_frac  = (xmax - xmin) / 1000
            height_frac = (ymax - ymin) / 1000
            if width_frac > 0.70 or height_frac > 0.70:
                _logger.debug(
                    "Skipping oversized box_2d for field '%s': covers %.0f%% W x %.0f%% H",
                    key, width_frac * 100, height_frac * 100
                )
                continue

            # Clamp to page bounds (safety net)
            xmin = max(0, min(xmin, 1000))
            xmax = max(0, min(xmax, 1000))
            ymin = max(0, min(ymin, 1000))
            ymax = max(0, min(ymax, 1000))

            fitz_rect = fitz.Rect(
                xmin * w / 1000,
                ymin * h / 1000,
                xmax * w / 1000,
                ymax * h / 1000,
            )

            is_failed = key in failed_fields
            color = (1, 0, 0) if is_failed else (1, 1, 0)  # Red if failed, Yellow otherwise

            annot = page.add_highlight_annot(fitz_rect)
            annot.set_colors(stroke=color)
            if is_failed:
                annot.set_info(content=failed_fields[key])
            annot.update()

        out = io.BytesIO()
        doc.save(out)
        doc.close()
        return base64.b64encode(out.getvalue())
    except Exception as e:
        _logger.error("Highlight rendering error: %s", str(e))
        return False

