# -*- coding: utf-8 -*-
import logging
try:
    import pytesseract
except ImportError:
    pytesseract = None
from .ocr_utils import _cleanup_tesseract_processes

_logger = logging.getLogger(__name__)

def _extract_pdf_bytes_using_tesseract(pil_img, config):
    if not pytesseract: return None
    try:
        return pytesseract.image_to_pdf_or_hocr(
            pil_img, lang=config.get('languages', 'eng'), extension='pdf',
            timeout=config.get('timeout_per_page', 30),
            config=f"--psm {config.get('psm_mode', 3)} --oem {config.get('oem_mode', 3)}"
        )
    except Exception as e:
        _logger.error("Tesseract PDF failed: %s", e)
        _cleanup_tesseract_processes()
        return None
