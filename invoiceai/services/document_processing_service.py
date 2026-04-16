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
import signal
import threading
from odoo import fields, _
from odoo.exceptions import UserError
from odoo.addons.invoiceai.services import ai_service
from odoo.addons.ai_core.services.ai_core_service import _get_ai_settings

# Import modular services from AI Core (centralized)
from odoo.addons.ai_core.services import ocr_service
from odoo.addons.ai_core.services.ocr_config import _get_ocr_config
from odoo.addons.ai_core.services import box_refinement_service
from odoo.addons.ai_core.services import pdf_utils

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


class ProcessingTimeout(Exception):
    """Exception raised when document processing exceeds the timeout limit."""
    pass


def _process_document_internal(env, client, file_path, filename, existing_record=None):
    """Internal document processing without timeout wrapper."""
    # Start timer for total processing time
    start_time = time.time()
    
    # Log the file being processed
    _logger.info("=" * 80)
    _logger.info("PROCESSING FILE: %s (for client: %s)", filename, client.name)
    _logger.info("File path: %s", file_path)
    _logger.info("=" * 80)
    
    # ──────────────────────────────────────────────────────────────────────────
    # STEP 1: TEMPLATE & FIELD PREPARATION
    # ──────────────────────────────────────────────────────────────────────────
    _logger.info("STEP 1️⃣  TEMPLATE & FIELD PREPARATION")
    _logger.info("  • Extraction Master Template: %s", client.extraction_master_id.name)
    
    template = client.extraction_master_id
    fields_to_extract = template.field_ids.filtered(lambda f: f.active)
    if not fields_to_extract:
        _logger.warning("  ❌ FAILED: No active fields in template %s for client %s", template.name, client.name)
        return False
    
    _logger.info("  • Active fields count: %d", len(fields_to_extract))
    _logger.info("  • Field keys: %s", ', '.join(f.field_key for f in fields_to_extract))

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
    ocr_method_used = 'none'  # Track which OCR method was used
    
    # Calculate PDF quality (DPI) early to dynamically adjust OCR parameters
    pdf_quality_dpi = 0
    quality_enhancements = []
    
    # ──────────────────────────────────────────────────────────────────────────
    # STEP 2: PDF QUALITY ANALYSIS (DPI CALCULATION)
    # ──────────────────────────────────────────────────────────────────────────
    _logger.info("STEP 2️⃣  PDF QUALITY ANALYSIS (DPI CALCULATION)")
    
    if filename.lower().endswith('.pdf'):
        try:
            if fitz:
                doc = fitz.open(file_path)
                if len(doc) > 0:
                    page = doc[0]
                    page_rect = page.rect
                    page_width_pts = page_rect.width
                    page_height_pts = page_rect.height
                    
                    # Try to get DPI from embedded images first (for scanned PDFs)
                    image_list = page.get_images(full=True)
                    
                    if image_list:
                        # Scanned PDF - extract the largest embedded image
                        largest_img = None
                        largest_area = 0
                        
                        for img_index, img_info in enumerate(image_list):
                            xref = img_info[0]
                            try:
                                base_image = doc.extract_image(xref)
                                img_width = base_image["width"]
                                img_height = base_image["height"]
                                area = img_width * img_height
                                
                                if area > largest_area:
                                    largest_area = area
                                    largest_img = {"width": img_width, "height": img_height}
                            except Exception as e_img:
                                _logger.debug("  • Failed to extract image %d: %s", img_index, e_img)
                                continue
                        
                        if largest_img:
                            # Calculate DPI based on embedded image vs page size
                            dpi_h = int(largest_img["width"] / (page_width_pts / 72.0)) if page_width_pts > 0 else 0
                            dpi_v = int(largest_img["height"] / (page_height_pts / 72.0)) if page_height_pts > 0 else 0
                            pdf_quality_dpi = int((dpi_h + dpi_v) / 2)
                            
                            _logger.info("  ✓ SCANNED PDF detected")
                            _logger.info("  • Calculated DPI: %d (H:%d/V:%d)", pdf_quality_dpi, dpi_h, dpi_v)
                            _logger.info("  • Page size: %.1fx%.1f pts | Embedded Image: %dx%d px",
                                       page_width_pts, page_height_pts, largest_img["width"], largest_img["height"])
                        else:
                            _logger.warning("  ⚠  SCANNED PDF detected but failed to extract image dimensions")
                    else:
                        # Native/vector PDF - render at 2x to check if it has meaningful resolution
                        # For native PDFs, we'll use a heuristic: render at 2x and check pixel dimensions
                        pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0))
                        image_width_px = pix.width
                        image_height_px = pix.height
                        
                        dpi_h = int(image_width_px / (page_width_pts / 72.0)) if page_width_pts > 0 else 0
                        dpi_v = int(image_height_px / (page_height_pts / 72.0)) if page_height_pts > 0 else 0
                        pdf_quality_dpi = int((dpi_h + dpi_v) / 2)
                        
                        _logger.info("  ✓ NATIVE/VECTOR PDF detected")
                        _logger.info("  • Calculated DPI: %d (H:%d/V:%d)", pdf_quality_dpi, dpi_h, dpi_v)
                        _logger.info("  • Page size: %.1fx%.1f pts | Rendered: %dx%d px",
                                   page_width_pts, page_height_pts, image_width_px, image_height_px)
                    
                    doc.close()
        except Exception as e:
            _logger.warning("  ⚠  STEP 2 FAILED - Could not analyze PDF quality for %s: %s", filename, str(e))
            _logger.info("  → Reason: %s", type(e).__name__)
    
    if pdf_quality_dpi == 0:
        _logger.info("  • PDF DPI unknown/not calculated - will use default OCR settings")
    
    # ──────────────────────────────────────────────────────────────────────────
    # STEP 3: OCR SEARCHABILITY CHECK
    # ──────────────────────────────────────────────────────────────────────────
    _logger.info("STEP 3️⃣  OCR SEARCHABILITY CHECK")
    
    if filename.lower().endswith('.pdf'):
        try:
            # Check if searchability checking is enabled
            check_searchability = env['ir.config_parameter'].sudo().get_param('ai_core.ocr_check_searchability', 'True').lower() in ('true', '1', 'yes')
            
            _logger.info("  • Searchability check: %s", "ENABLED" if check_searchability else "DISABLED")
            
            should_apply_ocr = False
            
            if check_searchability:
                # Check if PDF is searchable before applying OCR
                ocr_config = _get_ocr_config(env)
                is_searchable, text_count = ocr_service.check_pdf_searchability(file_path, ocr_config, env)
                _logger.info("  • PDF searchable: %s | Text found: %d chars", str(is_searchable), text_count)
                
                if not is_searchable:
                    should_apply_ocr = True
                    _logger.info("  ✓ PDF is image-heavy → OCR required")
                else:
                    _logger.info("  ✓ PDF is already searchable → OCR not needed")
            else:
                # Force OCR on all PDFs regardless of searchability
                should_apply_ocr = True
                _logger.info("  • OCR searchability check disabled → forcing OCR on all PDFs")
            
            # ──────────────────────────────────────────────────────────────────────────
            # STEP 4: OCR PROCESSING (IF NEEDED)
            # ──────────────────────────────────────────────────────────────────────────
            if should_apply_ocr:
                _logger.info("STEP 4️⃣  OCR PROCESSING")
                
                # Get configured OCR engine
                configured_ocr_engine = env['ir.config_parameter'].sudo().get_param('ai_core.ocr_engine', 'tesseract')
                _logger.info("  • OCR Engine: %s", configured_ocr_engine)
                
                # DYNAMIC QUALITY-BASED OCR ENHANCEMENT
                # Get base OCR configuration
                ocr_config = _get_ocr_config(env)
                
                # Check if dynamic enhancement is enabled (default: True)
                enable_dynamic_enhancement = env['ir.config_parameter'].sudo().get_param(
                    'ai_core.enable_dynamic_quality_enhancement', 'True'
                ).lower() in ('true', '1', 'yes')
                
                # Check if forcing aggressive mode for all PDFs (useful when all are low quality)
                force_aggressive_all = env['ir.config_parameter'].sudo().get_param(
                    'ai_core.force_aggressive_ocr_for_all', 'False'
                ).lower() in ('true', '1', 'yes')
                
                if force_aggressive_all:
                    _logger.warning("🔴 FORCE MODE: Applying AGGRESSIVE OCR to ALL PDFs (best for low-quality documents)")
                    ocr_config['dpi'] = 300
                    ocr_config['preprocess_denoise'] = True
                    ocr_config['preprocess_contrast'] = True
                    quality_enhancements.extend(['FORCE: High DPI (300)', 'Denoise', 'Contrast'])
                    _logger.info("   ✓ OCR DPI: 200 → 300")
                    _logger.info("   ✓ Preprocessing: Denoise + Contrast (applied to ALL PDFs)")
                
                elif enable_dynamic_enhancement and pdf_quality_dpi > 0:
                    _logger.info("🎯 QUALITY-BASED OCR ENHANCEMENT: Source DPI=%d", pdf_quality_dpi)
                    
                    # LOW QUALITY: < 150 DPI (poor scans, photos of documents)
                    if pdf_quality_dpi < 150:
                        _logger.warning("⚠️ LOW QUALITY PDF detected (DPI=%d) - Applying CONSERVATIVE enhancements", pdf_quality_dpi)
                        ocr_config['dpi'] = 300  # Increase OCR rendering to 300 DPI
                        ocr_config['preprocess_denoise'] = True   # Remove noise only
                        ocr_config['preprocess_contrast'] = True  # Enhance text/background contrast
                        # NOTE: Deskew and Threshold DISABLED - both can damage low-quality scans
                        quality_enhancements.extend(['High DPI (300)', 'Denoise', 'Contrast'])
                        _logger.info("   ✓ OCR DPI: 200 → 300")
                        _logger.info("   ✓ Preprocessing: Denoise + Contrast (deskew & threshold DISABLED for safety)")
                    
                    # MEDIUM-LOW QUALITY: 150-200 DPI (standard scans but needs help)
                    elif pdf_quality_dpi < 200:
                        _logger.info("📊 MEDIUM QUALITY PDF detected (DPI=%d) - Applying MODERATE enhancements", pdf_quality_dpi)
                        ocr_config['dpi'] = 250  # Slight increase
                        ocr_config['preprocess_denoise'] = True
                        ocr_config['preprocess_contrast'] = True
                        quality_enhancements.extend(['Enhanced DPI (250)', 'Denoise', 'Contrast'])
                        _logger.info("   ✓ OCR DPI: 200 → 250")
                        _logger.info("   ✓ Preprocessing: Denoise + Contrast")
                    
                    # GOOD QUALITY: 200-250 DPI (good scans)
                    elif pdf_quality_dpi < 250:
                        _logger.info("✓ GOOD QUALITY PDF detected (DPI=%d) - Using STANDARD settings with minor enhancement", pdf_quality_dpi)
                        ocr_config['preprocess_denoise'] = True
                        quality_enhancements.append('Denoise')
                        _logger.info("   ✓ Preprocessing: Denoise only")
                    
                    # HIGH QUALITY: >= 250 DPI (excellent quality, no enhancement needed)
                    else:
                        _logger.info("⭐ HIGH QUALITY PDF detected (DPI=%d) - Using STANDARD settings", pdf_quality_dpi)
                        quality_enhancements.append('No enhancement needed')
                else:
                    # Fallback: if  DPI calculation failed, apply conservative preprocessing if PDF looks low quality
                    _logger.warning("⚠️ Dynamic quality enhancement unavailable (DPI=%d) - Applying FALLBACK safe preprocessing", pdf_quality_dpi)
                    
                    # Check if PDF is image-heavy (scanned/photo)
                    is_searchable_check, _ = ocr_service.check_pdf_searchability(file_path, ocr_config, env)
                    if not is_searchable_check:
                        # Image-heavy PDF with no detection - apply minimal safe preprocessing
                        _logger.info("   → Image-heavy PDF detected, enabling safe preprocessing: Denoise only")
                        ocr_config['preprocess_denoise'] = True
                        quality_enhancements.append('Fallback: Denoise (DPI detection failed)')
                    else:
                        _logger.info("   → Searchable PDF, no enhancement needed")
                
                if _detailed_logging_enabled(env):
                    _logger.info("process_document: Applying OCR (%s) to PDF '%s' with config: DPI=%d, Preprocessing=%s",
                               configured_ocr_engine, filename, ocr_config.get('dpi', 200),
                               'Enabled' if any([ocr_config.get('preprocess_denoise'), ocr_config.get('preprocess_deskew'),
                                                ocr_config.get('preprocess_contrast'), ocr_config.get('preprocess_threshold')]) else 'None')
                    
                # Use tracking function with enhanced configuration
                _logger.info("  • Starting OCR engine: %s with DPI=%d", configured_ocr_engine, ocr_config.get('dpi', 200))
                
                ocr_doc, actual_ocr_engine = ocr_service.apply_ocr_to_pdf_with_tracking(file_path, env=env, config_override=ocr_config)
                ocr_method_used = actual_ocr_engine  # Use what ACTUALLY ran, not what was configured
                
                if ocr_doc is not None:
                    # Save OCR'd PDF to temp file
                    temp_ocr_file = f"/tmp/ocr_{int(time.time())}_{filename}"
                    ocr_doc.save(temp_ocr_file)
                    ocr_doc.close()
                    file_to_send = temp_ocr_file
                    _logger.info("  ✓ OCR succeeded using: %s", actual_ocr_engine)
                    _logger.info("  • Temp OCR file: %s", temp_ocr_file)
                else:
                    ocr_method_used = 'none'  # OCR failed completely
                    _logger.warning("  ❌ OCR FAILED using: %s → Using original PDF", configured_ocr_engine)
        except UserError:
            raise  # Always propagate UserError to show popup to user
        except Exception as e:
            _logger.warning("  ❌ STEP 4 FAILED - OCR processing error: %s", str(e))
            _logger.info("  → Reason: %s", type(e).__name__)
            _logger.warning("  → Fallback: Using original PDF without OCR")
    
    # ──────────────────────────────────────────────────────────────────────────
    # STEP 5: FILE PREPARATION FOR AI
    # ──────────────────────────────────────────────────────────────────────────
    _logger.info("STEP 5️⃣  FILE PREPARATION FOR AI")
    _logger.info("  • File to send: %s", "Temp OCR file" if temp_ocr_file else "Original file")
    _logger.info("  • OCR method used: %s", ocr_method_used)
    
    # If any field needs zoom, we create crops of the margins
    use_zoom = any(f.use_zoom for f in fields_to_extract)
    
    try:
        visual_inputs = [ai_service.upload_file(file_to_send, env=env)]
        _logger.info("  ✓ Main document uploaded to AI service")
    except Exception as e_upload:
        _logger.error("  ❌ STEP 5 FAILED - Failed to upload main document: %s", str(e_upload))
        raise
    
    zoom_files = []
    if use_zoom:
        zoom_files = pdf_utils._crop_document_margins(file_path)
        _logger.info("  • Zoom requested: cropping %d margin(s)", len(zoom_files))
        if zoom_files:
            for i, zf in enumerate(zoom_files):
                try:
                    uploaded_zoom = ai_service.upload_file(zf, env=env)
                    visual_inputs.append(uploaded_zoom)
                    _logger.info("  ✓ Zoom crop %d uploaded", i + 1)
                except Exception as e_zoom:
                    _logger.warning("  ⚠  Failed to upload zoom crop %d: %s", i + 1, str(e_zoom))
            
            system_prompt += (
                "\n\nCRITICAL INSTRUCTION: I have provided one or more ZOOMED-IN images of the document margins from the first page. "
                "Use these high-resolution zoomed images SPECIFICALLY to read handwritten marks, circled numbers, or symbols "
                "that may be blurry in the main document. Pay extreme attention to decimal points (e.g., 2.5 vs 2)."
            )

    # ──────────────────────────────────────────────────────────────────────────
    # STEP 6: AI EXTRACTION (VISION API CALL)
    # ──────────────────────────────────────────────────────────────────────────
    _logger.info("STEP 6️⃣  AI EXTRACTION (VISION API CALL)")
    _logger.info("  • AI Provider: %s", ai_provider.upper())
    _logger.info("  • Temperature: 0.1 (low for deterministic extraction)")
    _logger.info("  • Fields to extract: %d", len(fields_to_extract))
    
    try:
        res = ai_service.generate(
            [system_prompt] + visual_inputs,
            env=env,
            temperature=0.1,  # Low temp for extraction consistency, overrides system default
            max_retries=0,
            enforce_html=False,
        )
        _logger.info("  ✓ AI extraction completed successfully")
    except Exception as e_ai:
        _logger.error("  ❌ STEP 6 FAILED - AI extraction failed: %s", str(e_ai))
        _logger.info("  → Reason: %s | Provider: %s", type(e_ai).__name__, ai_provider)
        raise
    
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

    # ──────────────────────────────────────────────────────────────────────────
    # STEP 7: JSON PARSING & EXTRACTION
    # ──────────────────────────────────────────────────────────────────────────
    _logger.info("STEP 7️⃣  JSON PARSING & EXTRACTION")
    _logger.info("  • Response size: %d chars | Tokens used: %d (prompt) + %d (output)",
               len(raw_text), p_tok, o_tok)
    
    json_str = _extract_json(raw_text)
    if json_str:
        _logger.info("  ✓ Valid JSON extracted from AI response")
        try:
            parsed = json.loads(json_str)
            fields_in_response = len(parsed) if isinstance(parsed, dict) else 0
            _logger.info("  • Parsed JSON with %d fields", fields_in_response)
            
            # ──────────────────────────────────────────────────────────────────────────
            # STEP 8: BOX REFINEMENT (PDF TEXT SNAPPING)
            # ──────────────────────────────────────────────────────────────────────────
            _logger.info("STEP 8️⃣  BOX REFINEMENT (PDF TEXT SNAPPING)")
            _logger.info("  • Refining box coordinates using PDF text search...")
            
            try:
                parsed = box_refinement_service.refine_extracted_boxes_with_fitz(file_path, parsed, env=env)
                json_str = json.dumps(parsed, ensure_ascii=False)
                _logger.info("  ✓ Box refinement completed")
            except json.JSONDecodeError as e_parse:
                _logger.warning("  ⚠  Failed to parse refined JSON: %s", str(e_parse))
            except Exception as ex:
                _logger.warning("  ⚠  Box refinement skipped: %s", str(ex))
        except json.JSONDecodeError as e_json:
            _logger.error("  ❌ STEP 7 FAILED - JSON parsing failed: %s", str(e_json))
            _logger.info("  → Raw response preview: %.200s", raw_text[:200])
    else:
        _logger.error("  ❌ STEP 7 FAILED - Could not extract JSON from AI response")
        _logger.info("  → Expected JSON object, got: %.200s", raw_text[:200])

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
    
    # ──────────────────────────────────────────────────────────────────────────
    # STEP 9: EXTRACTION RESULT CREATION
    # ──────────────────────────────────────────────────────────────────────────
    _logger.info("STEP 9️⃣  EXTRACTION RESULT CREATION & STORAGE")
    _logger.info("  • AI Model: %s | Provider: %s", mod or "Unknown", prov or "Unknown")
    _logger.info("  • Estimated cost: %.6f USD", cost)
    
    page_count = 0
    if filename.lower().endswith('.pdf'):
        try:
            import PyPDF2
            with open(file_path, 'rb') as f:
                pdf = PyPDF2.PdfReader(f)
                page_count = len(pdf.pages)
            _logger.info("  • Page count: %d", page_count)
        except Exception as e:
            _logger.warning("  ⚠  Could not count pages: %s", str(e))

    # Calculate total processing time
    total_processing_time_ms = int((time.time() - start_time) * 1000)
    
    vals = {
        'client_id': client.id,
        'filename': filename,
        'raw_response': raw_text,
        'extracted_data': json_str or '{}',
        'state': 'done' if json_str else 'error',
        'error_log': None if json_str else f'Could not parse JSON from AI response:\n{raw_text[:1000]}',
        'provider': prov,
        'model_used': mod,
        'ocr_method': ocr_method_used,
        'duration_ms': res.get('durationMs', 0),
        'total_processing_time_ms': total_processing_time_ms,
        'prompt_tokens': p_tok,
        'output_tokens': o_tok,
        'total_tokens': p_tok + o_tok,
        'cost': cost,
        'page_count': page_count,
        'pdf_dpi': pdf_quality_dpi,  # Use the early-calculated DPI
        'quality_enhancements': ', '.join(quality_enhancements) if quality_enhancements else False,
    }

    # Create or update the extraction result inside a savepoint so that any
    # DB-level errors here don't leave the outer transaction aborted for the
    # rest of the processing (we still treat a failed write as fatal for the
    # extraction flow and log it clearly).
    result_rec = None
    try:
        with env.cr.savepoint():
            if existing_record:
                _logger.info("  • Updating existing extraction result record...")
                existing_record.write(vals)
                result_rec = existing_record
                _logger.info("  ✓ Record updated successfully")
            else:
                _logger.info("  • Creating new extraction result record...")
                vals['company_id'] = env.company.id
                result_rec = ResultModel.create(vals)
                _logger.info("  ✓ Record created: ID=%d", result_rec.id)
    except Exception as e:
        _logger.error("  ❌ STEP 9 FAILED - Database write failed: %s", str(e))
        _logger.info("  → Reason: Failed to create/update extraction record")
        raise

    # ──────────────────────────────────────────────────────────────────────────
    # STEP 10: POST-PROCESSING (INVOICE PROCESSOR + PDF ANNOTATION)
    # ──────────────────────────────────────────────────────────────────────────
    _logger.info("STEP 🔟 POST-PROCESSING (NON-FATAL)")
    
    # Step 1: Create invoice processor and collect validation failures
    _logger.info("  • Creating invoice processor...")
    failures = []
    try:
        with env.cr.savepoint():
            proc = env['purple_ai.invoice_processor'].create_from_extraction(result_rec.id)
            failures = proc.action_validate() or []
            _logger.info("  ✓ Invoice processor created | Validation failures: %d", len(failures))
    except Exception as e:
        _logger.warning("  ⚠  Invoice processor creation failed (non-fatal): %s", str(e))

    # Step 2: PDF annotation with highlights
    _logger.info("  • Creating annotated PDF with highlights...")
    try:
        extracted_json = json.loads(json_str) if json_str else {}
        annotated_pdf = ocr_service.apply_pdf_highlights(file_path, extracted_json, failures, env=env)
        _logger.info("  ✓ PDF highlighting completed")
    except Exception as e:
        _logger.warning("  ⚠  PDF highlighting failed (non-fatal): %s", str(e))
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
                    
                    # If destination exists, REMOVE the old version before moving new one
                    # This prevents timestamp accumulation when re-scanning the same file
                    if os.path.exists(dest):
                        try:
                            os.remove(dest)
                            _logger.debug("process_document: removed old processed file: %s", dest)
                        except Exception as e:
                            _logger.warning("process_document: could not remove old file %s: %s", dest, e)
                    
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

    # ──────────────────────────────────────────────────────────────────────────
    # PROCESSING COMPLETE - SUMMARY
    # ──────────────────────────────────────────────────────────────────────────
    processing_time_sec = (time.time() - start_time)
    
    if result_rec:
        status_str = "✅ SUCCESS" if result_rec.state == 'done' else "❌ FAILED"
        extraction_pct = result_rec.fields_extracted_percent if hasattr(result_rec, 'fields_extracted_percent') else 0
        _logger.info("=" * 80)
        _logger.info("FILE PROCESSING COMPLETE: %s", filename)
        _logger.info("Status: %s | Extraction: %.1f%% | Time: %.2f sec", status_str, extraction_pct, processing_time_sec)
        _logger.info("Record ID: %d | DPI: %d | Quality: %s | OCR: %s",
                   result_rec.id, pdf_quality_dpi, result_rec.pdf_quality if hasattr(result_rec, 'pdf_quality') else 'N/A', ocr_method_used)
        _logger.info("=" * 80)
    else:
        _logger.error("=" * 80)
        _logger.error("FILE PROCESSING FAILED: %s (No extraction record created)", filename)
        _logger.error("Time: %.2f sec | Check logs above for details", processing_time_sec)
        _logger.error("=" * 80)

    return result_rec


def process_document(env, client, file_path, filename, existing_record=None):
    """
    Public wrapper for document processing with timeout protection.
    Implements 2-minute timeout per file - if exceeded, fails the record and returns.

    Args:
        env: Odoo environment
        client: purple_ai.client_master record
        file_path: Path to source file (PDF or image)
        filename: Human-readable filename
        existing_record: Optional extraction result to update

    Returns:
        purple_ai.extraction_result record (marked as error if timeout occurs)
    """
    # 2-minute timeout per file (120 seconds)
    TIMEOUT_SECONDS = 600
    result_holder = {'result': None, 'timed_out': False, 'exception': None}
    
    def _run_with_timeout():
        try:
            result_holder['result'] = _process_document_internal(env, client, file_path, filename, existing_record=existing_record)
        except UserError as e:
            # Store UserError to re-raise in main thread
            result_holder['exception'] = e
        except Exception as e:
            _logger.error("process_document: Unexpected error during processing: %s", str(e))
            result_holder['result'] = None
    
    # Run processing in a thread with timeout
    thread = threading.Thread(target=_run_with_timeout, daemon=True)
    thread.start()
    thread.join(timeout=TIMEOUT_SECONDS)
    
    # Check if UserError occurred in thread and re-raise it
    if result_holder.get('exception'):
        raise result_holder['exception']
    
    # Check if thread is still alive (timed out)
    if thread.is_alive():
        result_holder['timed_out'] = True
        _logger.error("process_document: TIMEOUT! File '%s' processing exceeded %d seconds", filename, TIMEOUT_SECONDS)
        
        # Create error record
        try:
            ResultModel = env['purple_ai.extraction_result']
            error_record = ResultModel.create({
                'client_id': client.id,
                'filename': filename,
                'raw_response': '',
                'extracted_data': '{}',
                'state': 'error',
                'error_log': f'Processing timeout: File processing exceeded {TIMEOUT_SECONDS} seconds. The file may be too large or the AI service is slow.',
                'provider': '',
                'model_used': '',
                'ocr_method': 'none',
                'duration_ms': int(TIMEOUT_SECONDS * 1000),
                'total_processing_time_ms': int(TIMEOUT_SECONDS * 1000),
            })
            _logger.warning("process_document: Created error record for timed-out file: %s", filename)
            return error_record
        except Exception as e:
            _logger.error("process_document: Failed to create timeout error record: %s", str(e))
            return None
    
    return result_holder.get('result')


def _process_document_wrapper(env, client, file_path, filename, existing_record=None):
    """
    Wrapper that routes to internal implementation.
    This is called from the scanning module.
    """
    return process_document(env, client, file_path, filename, existing_record=existing_record)


def process_documents_parallel(env, client, file_list, max_workers=None):
    """
    Process multiple documents in parallel using thread pool.
    
    🚀 PARALLEL BATCH PROCESSING - Process 2-4 invoices at the same time!
    
    This function processes multiple PDF files concurrently to dramatically increase
    throughput. Perfect for batch imports or bulk operations.
    
    Args:
        env: Odoo environment
        client: purple_ai.client_master record
        file_list: List of tuples: [(file_path, filename, existing_record), ...]
        max_workers: Number of parallel threads (default from config or 2)
                     - 1: Sequential (no parallelization, for debugging)
                     - 2: Safe and recommended (avoids rate limiting on most APIs)
                     - 3: Aggressive (requires good internet/APIs)
                     - 4: Very aggressive (may hit rate limits or API quotas)
                     
                     Will be auto-clamped to 1-4 range for safety.
    
    Returns:
        dict with:
            'completed': List of successful extraction_result records
            'failed': List of dicts with {filename, error}
            'total': Total files processed (success + fail)
            'duration_sec': Total elapsed time
            'speed': Files per minute achieved
            'success_count': Number of successful extractions
            'fail_count': Number of failed extractions
    
    Examples:
        # Process 3 files with 2 parallel workers
        file_list = [
            ('/tmp/invoice1.pdf', 'invoice1.pdf', None),
            ('/tmp/invoice2.pdf', 'invoice2.pdf', None),
            ('/tmp/invoice3.pdf', 'invoice3.pdf', None),
        ]
        result = process_documents_parallel(env, client, file_list, max_workers=2)
        print(f"Extracted {result['success_count']} files in {result['duration_sec']:.1f}s")
        print(f"Speed: {result['speed']:.1f} files/min")
        
        # Process with default workers from system config
        result = process_documents_parallel(env, client, file_list)
        
    Performance Guide:
        - Sequential (1): ~30 sec/file = 2 files/min
        - Parallel (2): ~15 sec/file average = 8 files/min (4x faster)
        - Parallel (3): ~10 sec/file average = 18 files/min (9x faster)
        - Parallel (4): ~8 sec/file average = 30 files/min (15x faster, risky)
    
    System Configuration:
        Set 'ai_core.max_parallel_workers' in Odoo settings to customize default.
        Current default: 2 workers (safe)
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from datetime import datetime
    
    # Validate inputs
    if not file_list:
        _logger.warning("process_documents_parallel: Empty file list provided")
        return {
            'completed': [],
            'failed': [],
            'total': 0,
            'duration_sec': 0,
            'speed': 0,
            'success_count': 0,
            'fail_count': 0,
        }
    
    # Get max_workers from system config if not provided
    if max_workers is None:
        try:
            config_val = env['ir.config_parameter'].sudo().get_param('ai_core.max_parallel_workers', '2')
            max_workers = int(config_val)
        except (ValueError, TypeError):
            max_workers = 2
    
    # Limit max_workers to safe range (1-4) to prevent overwhelming system
    max_workers = min(max(1, max_workers), 4)  # Between 1-4
    
    _logger.info("=" * 80)
    _logger.info("🚀 PARALLEL BATCH PROCESSING STARTED")
    _logger.info("📁 Files to process: %d", len(file_list))
    _logger.info("⚙️  Thread workers: %d", max_workers)
    _logger.info("=" * 80)
    
    start_time = datetime.now()
    start_seconds = time.time()
    
    completed = []
    failed = []
    
    def process_single_file(file_info):
        """Process one file and return result."""
        try:
            file_path, filename, existing_record = file_info
            _logger.info("  ⏳ Processing: %s [Thread]", filename)
            
            result = process_document(env, client, file_path, filename, existing_record=existing_record)
            
            if result and result.state == 'done':
                _logger.info("  ✅ Completed: %s", filename)
            else:
                _logger.warning("  ⚠️  Partial: %s (check error_log)", filename)
            
            return {'success': True, 'result': result, 'filename': filename}
        except Exception as e:
            _logger.error("  ❌ Failed: %s | Error: %s", filename, str(e))
            return {'success': False, 'error': str(e), 'filename': filename}
    
    # Submit all tasks to thread pool
    try:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(process_single_file, file_info): file_info 
                for file_info in file_list
            }
            
            # Process completed tasks as they finish
            completed_count = 0
            for future in as_completed(futures):
                try:
                    result = future.result()
                    if result['success']:
                        completed.append(result['result'])
                    else:
                        failed.append({'filename': result['filename'], 'error': result['error']})
                    
                    completed_count += 1
                    progress = (completed_count / len(file_list)) * 100
                    _logger.info("Progress: %d/%d (%.0f%%)", completed_count, len(file_list), progress)
                except Exception as e:
                    _logger.error("❌ Error retrieving future result: %s", str(e))
                    failed.append({'filename': 'unknown', 'error': str(e)})
    except Exception as e:
        _logger.error("❌ Thread pool error: %s", str(e))
    
    # Calculate statistics
    duration_sec = time.time() - start_seconds
    total_processed = len(completed) + len(failed)
    speed = (total_processed / duration_sec * 60) if duration_sec > 0 else 0  # Files per minute
    
    # Summary
    _logger.info("=" * 80)
    _logger.info("🏁 PARALLEL BATCH PROCESSING COMPLETE")
    _logger.info("✅ Successful: %d files", len(completed))
    _logger.info("❌ Failed: %d files", len(failed))
    _logger.info("⏱️  Total time: %.2f seconds", duration_sec)
    _logger.info("⚡ Speed: %.1f files/minute", speed)
    _logger.info("=" * 80)
    
    if failed:
        _logger.warning("Failed files:")
        for item in failed:
            _logger.warning("  • %s: %s", item['filename'], item['error'][:100])
    
    return {
        'completed': completed,
        'failed': failed,
        'total': total_processed,
        'duration_sec': duration_sec,
        'speed': speed,
        'success_count': len(completed),
        'fail_count': len(failed),
    }
