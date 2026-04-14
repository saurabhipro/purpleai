# -*- coding: utf-8 -*-
"""
Document Processing Service (Refactored)

Orchestrates AI-powered extraction pipeline for invoices and documents:
  1. PDF preparation and searchability checks
  2. AI extraction with vision inputs (main document + zoom crops)
  3. Box refinement via PDF text search
  4. PDF annotation and highlights
  5. Extraction record persistence

Delegates specialized tasks to modular services:
  - ocr_service: OCR and PDF searchability
  - box_refinement_service: Text search and box snapping
  - pdf_utils: PDF utilities (margins, rendering)
  - ai_service: LLM calls (external)

See also:
  - purpleai/services/ocr_service.py
  - purpleai/services/box_refinement_service.py
  - purpleai/services/pdf_utils.py
"""
import os
import re
import json
import logging
import time
import base64
import io
from odoo import fields, _
from odoo.addons.invoiceai.services import ai_service
from odoo.addons.ai_core.services.ai_core_service import _get_ai_settings

# Import new modular services
from odoo.addons.invoiceai.services import ocr_service
from odoo.addons.invoiceai.services import box_refinement_service
from odoo.addons.invoiceai.services import pdf_utils

try:
    import fitz
    from PIL import Image as PILImage
except ImportError:
    fitz = None
    PILImage = None

_logger = logging.getLogger(__name__)


def _detailed_logging_enabled(env):
    try:
        val = env['ir.config_parameter'].sudo().get_param('purple_ai.detailed_logging', 'False')
        return str(val).lower() in ('1', 'true', 'yes', 'y')
    except Exception:
        return False


def _extract_json(raw_text: str, _strip_html_once: bool = True) -> str:
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

    # If the model returned JSON wrapped in HTML (legacy / misconfigured prompts), try tag-stripped text once.
    if _strip_html_once and '<' in text and '>' in text:
        stripped = re.sub(r'<[^>]+>', '', text)
        if stripped != text:
            inner = _extract_json(stripped, _strip_html_once=False)
            if inner:
                return inner

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


def process_document(env, client, file_path, filename, existing_record=None):
    """
    Orchestrates the AI extraction and record creation for a file.
    Optimized to perform validation and highlighting in a single pass.

    Args:
        env: Odoo environment
        client: purple_ai.client_master record
        file_path: Path to source file (PDF or image)
        filename: Human-readable filename
        existing_record: Optional extraction result to update

    Returns:
        purple_ai.extraction_result record, or raises on fatal error
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
    
    # Must match the provider used by ai_service.generate (AI Core), not legacy tender_ai.*
    ai_provider = (_get_ai_settings(env).get('provider') or 'openai').lower().strip()
    
    system_prompt = (
        "You are a specialized data extraction AI. "
        "Extract fields from the document. Return a JSON object with: "
        "'value', 'box_2d' ([ymin, xmin, ymax, xmax] 0-1000), 'page_number' (1-indexed).\n\n"
        "COORDINATE SYSTEM GUIDE:\n"
        "- [0, 0, 1000, 1000] represents [top, left, bottom, right] of the document page.\n"
        "- [0, 0] is top-left, [1000, 1000] is bottom-right.\n\n"
        "CRITICAL PRECISION RULES:\n"
        "1. The 'box_2d' MUST be a tight bounding box that strictly encompasses ONLY the relevant text characters.\n"
        "2. Do NOT include field labels (e.g., if extracting GSTIN, do NOT include the word 'GSTIN:' in the box).\n"
        "3. Do NOT include surrounding whitespace, icons, logos, or borders.\n"
        "4. If a value spans multiple lines, ensure the bounding box covers the entire block precisely.\n"
        "5. The accuracy is used for visual highlighting; if the box is loose or covers other text, the audit will fail.\n"
    )
    
    if ai_provider != 'gemini':
        system_prompt += "6. IMPORTANT: For your model, DO NOT guess coordinates. You MUST return null for all 'box_2d' values so the system can use exact text-search fallback.\n\n"
    else:
        system_prompt += (
            "6. Place each box_2d strictly over the printed value glyphs (digits, decimals, letters as shown), "
            "not over neighbouring empty table cells or labels. The UI will also snap boxes to PDF text when possible.\n\n"
        )

    if rule_list:
        system_prompt += (
            "Additionally, evaluate these VALIDATION RULES. "
            "Add a 'validations' array to your JSON. Each item must include: "
            "'rule' (the rule code exactly as listed), 'status' (boolean), 'msg' (short explanation). "
            "Optionally add 'field_key' (same string as the extracted field this rule concerns, for UI navigation), "
            "plus 'box_2d' and 'page_number' if you cite evidence on the document.\n"
            f"RULES TO EVALUATE:\n{rule_list}\n\n"
        )

    system_prompt += f"FIELDS TO EXTRACT:\n{field_list}"
    system_prompt += (
        "\n\nOUTPUT: Respond with exactly one JSON object and nothing else — "
        "no HTML tags, no markdown fences, no commentary before or after."
    )

    # 2. Prepare visual inputs
    # For PDFs with images (no searchable text), apply OCR first so Azure gets clean text
    # Check if PDF is image-heavy and convert with OCR if needed
    file_to_send = file_path
    temp_ocr_file = None
    
    if filename.lower().endswith('.pdf'):
        try:
            is_searchable, text_count = ocr_service.check_pdf_searchability(file_path)
            if not is_searchable:
                if _detailed_logging_enabled(env):
                    _logger.info("process_document: PDF '%s' is image-heavy (text_count=%d) -> applying OCR before sending to Azure", filename, text_count)
                ocr_doc = ocr_service.apply_ocr_to_pdf(file_path, env=env)
                if ocr_doc is not None:
                    # Save OCR'd PDF to temp file
                    temp_ocr_file = f"/tmp/ocr_{int(time.time())}_{filename}"
                    ocr_doc.save(temp_ocr_file)
                    ocr_doc.close()
                    file_to_send = temp_ocr_file
                    if _detailed_logging_enabled(env):
                        _logger.info("process_document: OCR'd PDF saved to temp for Azure: %s", temp_ocr_file)
                else:
                    if _detailed_logging_enabled(env):
                        _logger.warning("process_document: OCR failed, falling back to original PDF")
            else:
                if _detailed_logging_enabled(env):
                    _logger.info("process_document: PDF '%s' is already searchable (text_count=%d), sending as-is to Azure", filename, text_count)
        except Exception as e:
            _logger.warning("process_document: Searchability check failed: %s, sending original PDF", e)
    
    # If any field needs zoom, we create crops of the margins
    use_zoom = any(f.use_zoom for f in fields_to_extract)
    visual_inputs = [ai_service.upload_file(file_to_send, env=env)]
    
    zoom_files = []
    if use_zoom:
        zoom_files = pdf_utils._crop_document_margins(file_path)
        if zoom_files:
            _logger.info("Zoom-in requested: cropping %d margin(s) for %s", len(zoom_files), filename)
            for zf in zoom_files:
                uploaded_zoom = ai_service.upload_file(zf, env=env)
                visual_inputs.append(uploaded_zoom)
            
            system_prompt += (
                "\n\nCRITICAL INSTRUCTION: I have provided one or more ZOOMED-IN images of the document margins from the first page. "
                "Use these high-resolution zoomed images SPECIFICALLY to read handwritten marks, circled numbers, or symbols "
                "that may be blurry in the main document. Pay extreme attention to decimal points (e.g., 2.5 vs 2)."
            )

    # 3. Call AI with low temperature for deterministic extraction
    # Temperature=0.1 ensures consistent field extraction (1.0 is too random for structured data)
    res = ai_service.generate(
        [system_prompt] + visual_inputs,
        env=env,
        temperature=0.1,  # Low temp for extraction consistency, overrides system default
        max_retries=0,
        enforce_html=False,
    )
    
    # Clean up temp zoom files if created
    for zf in zoom_files:
        if zf and os.path.exists(zf):
            try:
                os.remove(zf)
            except:
                pass
    
    # Clean up temp OCR file if created
    if temp_ocr_file and os.path.exists(temp_ocr_file):
        try:
            os.remove(temp_ocr_file)
            _logger.debug("Cleaned up temp OCR file: %s", temp_ocr_file)
        except Exception as e:
            _logger.warning("Could not remove temp OCR file %s: %s", temp_ocr_file, e)
    
    raw_text = res.get('text', '') if isinstance(res, dict) else str(res)
    usage = (res.get('usage') if isinstance(res, dict) else None) or {}
    p_tok = int(usage.get('promptTokens') or (res.get('prompt_tokens') if isinstance(res, dict) else 0) or 0)
    o_tok = int(usage.get('outputTokens') or (res.get('completion_tokens') if isinstance(res, dict) else 0) or 0)
    detailed = _detailed_logging_enabled(env)
    if detailed:
        _logger.info(
            "AI response for %s [%s tokens]: %.300s%s",
            filename, p_tok + o_tok, raw_text, '...' if len(raw_text) > 300 else ''
        )
    else:
        _logger.info("process_document: received AI response for %s (tokens=%d)", filename, p_tok + o_tok)

    # ── Robust JSON extraction ────────────────────────────────────────────────
    json_str = _extract_json(raw_text)
    if json_str:
        try:
            parsed = json.loads(json_str)
            parsed = box_refinement_service.refine_extracted_boxes_with_fitz(file_path, parsed, env=env)
            json_str = json.dumps(parsed, ensure_ascii=False)
        except json.JSONDecodeError:
            pass
        except Exception as ex:
            _logger.warning('box_2d text snap skipped for %s: %s', filename, ex)
    if not json_str:
        _logger.error("Could not extract JSON from AI response for %s. Raw: %s", filename, raw_text[:500])

    # 3. Validation and Single-Pass Rendering
    ResultModel = env['purple_ai.extraction_result']
    st = _get_ai_settings(env)
    prov = (res.get('provider') if isinstance(res, dict) else None) or st.get('provider') or ''
    mod = (res.get('model') if isinstance(res, dict) else None) or ''
    if not mod:
        pl = (prov or '').lower()
        if pl == 'gemini':
            mod = (st.get('gemini_model') or '').strip()
        elif pl == 'openai':
            mod = (st.get('openai_model') or '').strip()
        elif pl == 'azure':
            mod = (st.get('azure_deployment') or '').strip()
    cost = ResultModel._get_estimated_cost(prov, mod, p_tok, o_tok)
    
    page_count = 0
    if filename.lower().endswith('.pdf'):
        try:
            import PyPDF2
            with open(file_path, 'rb') as f:
                pdf = PyPDF2.PdfReader(f)
                page_count = len(pdf.pages)
        except Exception as e:
            _logger.warning("Could not count pages for %s: %s", filename, str(e))

    vals = {
        'client_id': client.id,
        'filename': filename,
        'raw_response': raw_text,
        'extracted_data': json_str or '{}',
        'state': 'done' if json_str else 'error',
        'error_log': None if json_str else f'Could not parse JSON from AI response:\n{raw_text[:1000]}',
        'provider': prov,
        'model_used': mod,
        'duration_ms': res.get('durationMs', 0),
        'prompt_tokens': p_tok,
        'output_tokens': o_tok,
        'total_tokens': p_tok + o_tok,
        'cost': cost,
        'page_count': page_count,
    }

    # Create or update the extraction result inside a savepoint so that any
    # DB-level errors here don't leave the outer transaction aborted for the
    # rest of the processing (we still treat a failed write as fatal for the
    # extraction flow and log it clearly).
    result_rec = None
    try:
        with env.cr.savepoint():
            if existing_record:
                existing_record.write(vals)
                result_rec = existing_record
            else:
                vals['company_id'] = env.company.id
                result_rec = ResultModel.create(vals)
    except Exception as e:
        _logger.error("process_document: failed to create/update extraction result for %s: %s", filename, e)
        # Bubble up the exception so the caller can surface an error state.
        raise

    # ── Post-processing: invoice processor + PDF annotation (non-fatal) ──────
    # Each step is wrapped in its own savepoint so a failure here does NOT
    # corrupt the main cursor and roll back the extraction record above.

    # Step 1: Create invoice processor and collect validation failures
    failures = []
    try:
        with env.cr.savepoint():
            proc = env['purple_ai.invoice_processor'].create_from_extraction(result_rec.id)
            failures = proc.action_validate() or []
    except Exception as e:
        _logger.warning("Invoice processor creation failed for %s (non-fatal): %s", filename, str(e))

    # Step 2: OCR / PDF preparation — done OUTSIDE the savepoint so the
    # long-running OCR does NOT hold the DB transaction lock open.
    # Only the final write (fast) happens inside a savepoint.
    try:
        extracted_json = json.loads(json_str) if json_str else {}
        annotated_pdf = ocr_service.apply_pdf_highlights(file_path, extracted_json, failures, env=env)
    except Exception as e:
        _logger.warning("PDF preparation failed for %s (non-fatal): %s", filename, str(e))
        annotated_pdf = None

    try:
        with env.cr.savepoint():
            if annotated_pdf:
                result_rec.write({
                    'pdf_file': annotated_pdf,
                    'pdf_filename': f"annotated_{filename}",
                })
            else:
                with open(file_path, 'rb') as f:
                    result_rec.write({
                        'pdf_file': base64.b64encode(f.read()),
                        'pdf_filename': filename,
                    })
    except Exception as e:
        _logger.error("PDF storage write failed for %s (non-fatal): %s", filename, str(e))

    # Move the processed source file into a `processed` subfolder under the
    # client's folder to avoid accidental re-processing. This is a best-effort
    # operation and never fatal for the extraction result.
    try:
        client_folder = getattr(client, 'folder_path', None)
        if client_folder and isinstance(client_folder, str) and client_folder.strip():
            try:
                abs_file = os.path.abspath(file_path)
                abs_client = os.path.abspath(client_folder)
                if abs_file.startswith(abs_client):
                    proc_dir = os.path.join(abs_client, 'processed')
                    os.makedirs(proc_dir, exist_ok=True)
                    dest = os.path.join(proc_dir, os.path.basename(file_path))
                    # If destination exists, append timestamp to avoid overwrite
                    if os.path.exists(dest):
                        base, ext = os.path.splitext(dest)
                        dest = f"{base}_{int(time.time())}{ext}"
                    try:
                        if not os.path.exists(abs_file):
                            _logger.debug("process_document: source file not found, skipping move: %s", abs_file)
                        else:
                            import shutil
                            shutil.move(abs_file, dest)
                            _logger.info("process_document: moved processed file to %s", dest)
                    except Exception as e:
                        _logger.warning("process_document: could not move file %s to processed folder: %s", file_path, e)
            except Exception as e:
                _logger.debug("process_document: skipping move to processed folder: %s", e)
    except Exception:
        pass

    return result_rec
