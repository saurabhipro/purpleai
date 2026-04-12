# -*- coding: utf-8 -*-
import os
import re
import json
import logging
import base64
import io
from odoo import fields, _
from odoo.addons.invoiceai.services import ai_service
from odoo.addons.ai_core.services.ai_core_service import _get_ai_settings

try:
    import fitz
    from PIL import Image as PILImage
except ImportError:
    fitz = None
    PILImage = None

_logger = logging.getLogger(__name__)


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


def _search_string_variants(value):
    """Candidate substrings to find extracted values inside PDF text."""
    if value is None:
        return []
    s = str(value).strip()
    if not s or s.lower() in ('---', 'null', 'none', 'n/a', 'undefined'):
        return []
    seen = set()
    out = []

    def add(x):
        x = str(x).strip()
        if x and x not in seen:
            seen.add(x)
            out.append(x)

    add(s)
    compact = re.sub(r'[\s₹$€]', '', s)
    compact = compact.replace(',', '')
    if compact and compact != s.replace(' ', ''):
        add(compact)
    num = re.search(r'-?[\d]+(?:[.,][\d]+)?', s.replace(',', ''))
    if num:
        raw = num.group(0).replace(',', '.')
        add(raw)
        try:
            f = float(raw)
            if abs(f - round(f)) < 1e-9:
                add(str(int(round(f))))
            add(f'{f:.2f}')
            add(f'{f:.1f}')
        except ValueError:
            pass
    return out


def _rect_to_box2d(rect, pw, ph):
    if pw <= 0 or ph <= 0:
        return None
    y0 = int(round(1000 * rect.y0 / ph))
    x0 = int(round(1000 * rect.x0 / pw))
    y1 = int(round(1000 * rect.y1 / ph))
    x1 = int(round(1000 * rect.x1 / pw))
    y0 = max(0, min(1000, y0))
    x0 = max(0, min(1000, x0))
    y1 = max(0, min(1000, y1))
    x1 = max(0, min(1000, x1))
    if x1 <= x0 or y1 <= y0:
        return None
    if (x1 - x0) > 700 or (y1 - y0) > 700:
        return None
    return [y0, x0, y1, x1]


def _box_iou_yxyx(a, b):
    if not a or not b or len(a) != 4 or len(b) != 4:
        return 0.0
    ay0, ax0, ay1, ax1 = a
    by0, bx0, by1, bx1 = b
    iy0, iy1 = max(ay0, by0), min(ay1, by1)
    ix0, ix1 = max(ax0, bx0), min(ax1, bx1)
    if iy1 <= iy0 or ix1 <= ix0:
        return 0.0
    inter = (iy1 - iy0) * (ix1 - ix0)
    area_a = max(1, (ay1 - ay0) * (ax1 - ax0))
    area_b = max(1, (by1 - by0) * (bx1 - bx0))
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def _page_search_hits(page, query, ignore_case=False):
    if not query:
        return []
    flags = 0
    if ignore_case:
        flags = getattr(fitz, 'TEXT_SEARCH_IGNORECASE', 0) or 0
    try:
        if flags:
            return page.search_for(query, quads=False, flags=flags)
        return page.search_for(query, quads=False)
    except TypeError:
        try:
            return page.search_for(query, quads=False)
        except Exception:
            return []
    except Exception:
        return []


def _pick_best_rect(rects, pw, ph, existing_box):
    if not rects:
        return None
    if len(rects) == 1:
        return rects[0]
    if existing_box and isinstance(existing_box, list) and len(existing_box) == 4:
        best_r = None
        best_iou = 0.0
        for r in rects:
            b = _rect_to_box2d(r, pw, ph)
            if not b:
                continue
            iou = _box_iou_yxyx(existing_box, b)
            if iou > best_iou:
                best_iou = iou
                best_r = r
        if best_r is not None and best_iou >= 0.02:
            return best_r

    def area(r):
        return max(0.0, (r.x1 - r.x0) * (r.y1 - r.y0))

    return min(rects, key=area)


def refine_extracted_boxes_with_fitz(file_path, data):
    """Snap model box_2d to PyMuPDF text hits so highlights match real glyphs (Gemini offset fix)."""
    if not fitz or not isinstance(data, dict):
        return data
    path = str(file_path or '')
    if not path.lower().endswith('.pdf') or not os.path.isfile(path):
        return data
    doc = None
    try:
        doc = fitz.open(path)
    except Exception as e:
        _logger.debug('refine_extracted_boxes: open failed: %s', e)
        return data
    try:
        for key, item in list(data.items()):
            if key == 'validations' or not isinstance(item, dict):
                continue
            val = item.get('value')
            variants = _search_string_variants(val)
            if not variants:
                continue
            if max(len(v) for v in variants) < 2:
                continue
            page_no = item.get('page_number', 1)
            try:
                pidx = int(page_no) - 1
            except (TypeError, ValueError):
                pidx = 0
            if pidx < 0 or pidx >= len(doc):
                continue
            page = doc[pidx]
            pw, ph = page.rect.width, page.rect.height
            if pw <= 0 or ph <= 0:
                continue
            numericish = bool(re.match(r'^[\d\s.,₹$€+-]+$', str(val).strip()))
            rects = []
            for q in variants:
                rects.extend(
                    _page_search_hits(page, q, ignore_case=not numericish)
                )
            if not rects:
                continue
            existing = item.get('box_2d')
            chosen = _pick_best_rect(rects, pw, ph, existing if isinstance(existing, list) else None)
            if not chosen:
                continue
            new_box = _rect_to_box2d(chosen, pw, ph)
            if new_box:
                _logger.debug('Refined %s box_2d via PDF text: %s -> %s', key, existing, new_box)
                item['box_2d'] = new_box
        return data
    except Exception as e:
        _logger.warning('refine_extracted_boxes_with_fitz: %s', e)
        return data
    finally:
        if doc is not None:
            doc.close()


def _crop_document_margins(file_path):
    """
    Crops the LEFT and RIGHT 20% margins of the first page of the document.
    Returns a list of local paths to the cropped images.
    """
    if not fitz:
        return []
    
    import tempfile
    cropped_paths = []
    
    try:
        doc = fitz.open(file_path)
        if len(doc) == 0:
            return []
        page = doc[0]
        rect = page.rect
        
        # Define crop regions (Left 20% and Right 20%)
        # 20% is usually enough for margin marks and keeps the image focused
        margin_width = rect.width * 0.22 
        crops = [
            ("left", fitz.Rect(rect.x0, rect.y0, rect.x0 + margin_width, rect.y1)),
            ("right", fitz.Rect(rect.x1 - margin_width, rect.y0, rect.x1, rect.y1))
        ]
        
        for side, crop_rect in crops:
            # Render at high DPI (3.0 scale = approx 216 DPI) for crystal clear handwriting recognition
            pix = page.get_pixmap(clip=crop_rect, matrix=fitz.Matrix(3, 3))
            
            temp = tempfile.NamedTemporaryFile(suffix=f'_zoom_{side}.png', delete=False)
            temp_path = temp.name
            pix.save(temp_path)
            cropped_paths.append(temp_path)
            
        doc.close()
        return cropped_paths
    except Exception as e:
        _logger.error("Failed to crop margins for %s: %s", file_path, str(e))
        return cropped_paths


def process_document(env, client, file_path, filename, existing_record=None):
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
    # If any field needs zoom, we create crops of the margins
    use_zoom = any(f.use_zoom for f in fields_to_extract)
    visual_inputs = [ai_service.upload_file(file_path, env=env)]
    
    zoom_files = []
    if use_zoom:
        zoom_files = _crop_document_margins(file_path)
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

    # 3. Call AI
    res = ai_service.generate(
        [system_prompt] + visual_inputs,
        env=env,
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
    
    raw_text = res.get('text', '') if isinstance(res, dict) else str(res)
    usage = (res.get('usage') if isinstance(res, dict) else None) or {}
    p_tok = int(usage.get('promptTokens') or (res.get('prompt_tokens') if isinstance(res, dict) else 0) or 0)
    o_tok = int(usage.get('outputTokens') or (res.get('completion_tokens') if isinstance(res, dict) else 0) or 0)
    
    _logger.info(
        "AI response for %s [%s tokens]: %.300s%s",
        filename, p_tok + o_tok, raw_text, '...' if len(raw_text) > 300 else ''
    )

    # ── Robust JSON extraction ────────────────────────────────────────────────
    json_str = _extract_json(raw_text)
    if json_str:
        try:
            parsed = json.loads(json_str)
            parsed = refine_extracted_boxes_with_fitz(file_path, parsed)
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

    if existing_record:
        existing_record.write(vals)
        result_rec = existing_record
    else:
        vals['company_id'] = env.company.id
        result_rec = ResultModel.create(vals)

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
        annotated_pdf = apply_pdf_highlights(file_path, extracted_json, failures)
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

    return result_rec


def apply_pdf_highlights(file_path, extracted_json, failures=None):
    """Returns a SEARCHABLE PDF as base64.

    If the source is an image or a non-searchable PDF (scanned image), Tesseract
    OCR is applied to create a text layer so the document can be searched in the
    PDF viewer and field highlights can be drawn by ai_evidence_viewer.js.

    Flow:
      1. Open with fitz and check every page for existing text.
      2. If text found already -> return as-is (already searchable).
      3. No text -> render each page at 200 DPI and OCR with Tesseract hin+eng.
      4. Merge OCR pages into a single searchable PDF and return.
      5. Any failure -> graceful fallback to the raw file bytes.
    """
    TESSDATA_DIR = '/home/odoo18/tessdata'
    IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp', '.gif', '.webp'}

    def _raw_bytes():
        try:
            with open(file_path, 'rb') as f:
                return base64.b64encode(f.read())
        except Exception:
            return False

    if not fitz:
        return _raw_bytes()

    ext = os.path.splitext(file_path)[1].lower()

    try:
        doc = fitz.open(file_path)
        has_text = (ext not in IMAGE_EXTS) and any(page.get_text().strip() for page in doc)
    except Exception as e:
        _logger.warning("apply_pdf_highlights: fitz error on %s: %s", file_path, e)
        return _raw_bytes()

    if has_text:
        doc.close()
        return _raw_bytes()

    # No text layer - run OCR
    try:
        import pytesseract
        from PIL import Image as PILImage
        import os as _os
        _os.environ['TESSDATA_PREFIX'] = TESSDATA_DIR
    except ImportError:
        _logger.warning("pytesseract not installed; storing file without OCR text layer")
        doc.close()
        return _raw_bytes()

    merged = fitz.open()
    try:
        for page_num in range(len(doc)):
            page = doc[page_num]
            mat = fitz.Matrix(200 / 72, 200 / 72)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            img_bytes = pix.tobytes("jpeg")

            pil_img = PILImage.open(io.BytesIO(img_bytes))
            if pil_img.mode not in ('RGB', 'L'):
                pil_img = pil_img.convert('RGB')

            pdf_bytes = pytesseract.image_to_pdf_or_hocr(
                pil_img,
                lang='hin+eng',
                extension='pdf',
            )
            page_pdf = fitz.open("pdf", pdf_bytes)
            merged.insert_pdf(page_pdf)
            page_pdf.close()

        doc.close()
        if len(merged) == 0:
            merged.close()
            return _raw_bytes()

        out = io.BytesIO()
        merged.save(out, garbage=4, deflate=True)
        n = len(merged)
        merged.close()
        _logger.info("apply_pdf_highlights: OCR applied -> searchable PDF (%d page(s))", n)
        return base64.b64encode(out.getvalue())

    except Exception as e:
        _logger.error("apply_pdf_highlights: OCR failed for %s: %s", file_path, e)
        for obj in (doc, merged):
            try:
                obj.close()
            except Exception:
                pass
        return _raw_bytes()
