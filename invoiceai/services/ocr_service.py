# -*- coding: utf-8 -*-
"""
OCR Service Module

Handles Tesseract-based OCR operations for image-heavy and scanned PDFs.
Provides searchable text layer generation and document image handling.

Features:
  - Per-page Tesseract timeout and zombie process cleanup
  - Automatic language detection (English + Hindi)
  - Searchability detection (skips OCR if text layer exists)
  - Graceful fallback on failure
"""
import os
import io
import logging
import time

try:
    import fitz
    from PIL import Image as PILImage
except ImportError:
    fitz = None
    PILImage = None

try:
    import pytesseract
except ImportError:
    pytesseract = None

_logger = logging.getLogger(__name__)


def _detailed_logging_enabled(env):
    """Check if detailed logging is enabled via ir.config_parameter."""
    try:
        val = env['ir.config_parameter'].sudo().get_param('purple_ai.detailed_logging', 'False')
        return str(val).lower() in ('1', 'true', 'yes', 'y')
    except Exception:
        return False


def check_pdf_searchability(file_path):
    """Check if PDF has searchable text or is image-heavy.
    
    Returns:
        (is_searchable: bool, text_count: int)
        - is_searchable=True if PDF has extractable text (not image-heavy)
        - text_count = total characters found across all pages
    """
    if not fitz:
        return True, 0  # Can't check, assume searchable
    
    try:
        doc = fitz.open(file_path)
        total_text = 0
        
        for page_num in range(min(len(doc), 5)):  # Check first 5 pages
            page = doc[page_num]
            text = page.get_text().strip()
            total_text += len(text)
        
        doc.close()
        
        # If less than 100 characters found in 5 pages, it's image-heavy
        is_searchable = total_text >= 100
        _logger.debug("check_pdf_searchability: %s - searchable=%s, text_count=%d", file_path, is_searchable, total_text)
        return is_searchable, total_text
        
    except Exception as e:
        _logger.warning("check_pdf_searchability failed for %s: %s", file_path, e)
        return True, 0  # Default to searchable if check fails


def apply_ocr_to_pdf(file_path, env=None):
    """Apply OCR to PDF with images to create searchable text layer.
    
    Returns a PyMuPDF Document with OCR-generated text layer, or None on failure.
    This enables bounding box detection for PDFs that primarily contain images.
    
    Uses system Tesseract installation with default language lookup (hin+eng).
    Falls back gracefully if Tesseract or language data is unavailable.
    
    Args:
        file_path: Path to the PDF file
        env: Odoo environment (for logging configuration)
    
    Returns:
        fitz.open() document with OCR text layer, or None on failure
    """
    if not pytesseract or not fitz:
        _logger.warning("pytesseract or fitz not available; OCR skipped for image-heavy PDFs")
        return None
    
    try:
        doc = fitz.open(file_path)
        if len(doc) == 0:
            _logger.warning("apply_ocr_to_pdf: PDF is empty - %s", file_path)
            doc.close()
            return None
        
        if _detailed_logging_enabled(env) and env is not None:
            _logger.info("apply_ocr_to_pdf: Starting OCR on %s (%d pages)", file_path, len(doc))
        merged = fitz.open()
        page_count = 0
        extracted_data = []  # Collect OCR text for logging

        # Timeout (seconds) for each Tesseract invocation
        ocr_timeout = 30

        # Process pages individually with a per-page timeout to avoid long-running/hung tesseract
        for page_num in range(min(len(doc), 10)):
            try:
                page = doc[page_num]
                # Render page at ~200 DPI for good OCR accuracy
                mat = fitz.Matrix(200 / 72, 200 / 72)
                pix = page.get_pixmap(matrix=mat, alpha=False)
                img_bytes = pix.tobytes("jpeg")

                pil_img = PILImage.open(io.BytesIO(img_bytes))
                if pil_img.mode not in ('RGB', 'L'):
                    pil_img = pil_img.convert('RGB')

                # OCR with English + Hindi
                if _detailed_logging_enabled(env) and env is not None:
                    _logger.debug("apply_ocr_to_pdf: Running Tesseract on page %d (lang=hin+eng, DPI=200, timeout=%ds)", page_num, ocr_timeout)
                try:
                    pdf_bytes = pytesseract.image_to_pdf_or_hocr(
                        pil_img,
                        lang='hin+eng',
                        extension='pdf',
                        timeout=ocr_timeout,
                    )
                except Exception as e:
                    # Handle subprocess timeout and other errors gracefully.
                    if _detailed_logging_enabled(env) and env is not None:
                        _logger.error("apply_ocr_to_pdf: Tesseract failed on page %d: %s", page_num, e)
                    # Attempt to clean up any lingering tesseract processes to avoid zombies
                    _cleanup_tesseract_processes()
                    continue

                # Extract text from OCR'd PDF to log what was detected
                try:
                    ocr_page_doc = fitz.open("pdf", pdf_bytes)
                    ocr_text = ocr_page_doc[0].get_text().strip()
                    if ocr_text:
                        extracted_data.append(ocr_text[:200])  # Log first 200 chars
                        if _detailed_logging_enabled(env) and env is not None:
                            _logger.info("apply_ocr_to_pdf: Page %d extracted text: %s", page_num, ocr_text[:300])
                    else:
                        if _detailed_logging_enabled(env) and env is not None:
                            _logger.warning("apply_ocr_to_pdf: Page %d - Tesseract found NO text", page_num)
                    ocr_page_doc.close()
                except Exception as e:
                    _logger.debug("apply_ocr_to_pdf: Could not extract text from OCR PDF for logging: %s", e)

                page_pdf = fitz.open("pdf", pdf_bytes)
                merged.insert_pdf(page_pdf)
                page_pdf.close()
                page_count += 1
            except Exception as e:
                _logger.error("apply_ocr_to_pdf: OCR failed for page %d: %s", page_num, e)
                continue
        
        doc.close()
        
        if len(merged) > 0:
            if _detailed_logging_enabled(env) and env is not None:
                _logger.info("apply_ocr_to_pdf: SUCCESS - Created searchable PDF from %d pages with extracted text: %s", page_count, ', '.join(extracted_data[:3]))
            return merged
        else:
            if _detailed_logging_enabled(env) and env is not None:
                _logger.warning("apply_ocr_to_pdf: Tesseract ran on %d pages but produced no searchable content", page_count)
            merged.close()
            return None
            
    except Exception as e:
        _logger.error("apply_ocr_to_pdf: FAILED for %s: %s", file_path, e)
        return None


def _cleanup_tesseract_processes():
    """Attempt to clean up any lingering tesseract processes to avoid zombies."""
    try:
        import psutil
        for p in psutil.process_iter(['name', 'pid']):
            if p.info.get('name') and 'tesseract' in p.info.get('name').lower():
                _logger.info("_cleanup_tesseract_processes: terminating lingering tesseract pid=%s", p.info.get('pid'))
                try:
                    p.kill()
                except Exception:
                    pass
    except Exception:
        try:
            import subprocess
            subprocess.run(['pkill', '-f', 'tesseract'], timeout=5)
        except Exception:
            pass


def apply_pdf_highlights(file_path, extracted_json, failures=None, env=None):
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
    
    Uses system Tesseract installation with default language paths.
    
    Args:
        file_path: Path to source file (PDF or image)
        extracted_json: Extracted field data (unused, kept for compatibility)
        failures: Validation failures (unused, kept for compatibility)
        env: Odoo environment (for logging configuration)
    
    Returns:
        Base64-encoded PDF bytes
    """
    IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp', '.gif', '.webp'}

    def _raw_bytes():
        try:
            with open(file_path, 'rb') as f:
                import base64
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
    if not pytesseract:
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

            # OCR with timeout of 30 seconds per page
            pdf_bytes = pytesseract.image_to_pdf_or_hocr(
                pil_img,
                lang='hin+eng',
                extension='pdf',
                timeout=30,
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
        if _detailed_logging_enabled(env):
            _logger.info("apply_pdf_highlights: OCR applied -> searchable PDF (%d page(s))", n)
        import base64
        return base64.b64encode(out.getvalue())

    except Exception as e:
        if _detailed_logging_enabled(env):
            _logger.error("apply_pdf_highlights: OCR failed for %s: %s", file_path, e)
        for obj in (doc, merged):
            try:
                obj.close()
            except Exception:
                pass
        return _raw_bytes()
