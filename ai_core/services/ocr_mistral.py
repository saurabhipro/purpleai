# -*- coding: utf-8 -*-
"""
Mistral OCR Module

Handles Mistral OCR API-based text extraction using ocr_engines.
Creates proper searchable PDFs with original image + invisible text layer.
"""
import io
import logging
from odoo.exceptions import UserError

try:
    import fitz
except ImportError:
    fitz = None

try:
    from . import ocr_engines
except ImportError:
    ocr_engines = None

_logger = logging.getLogger(__name__)


def _extract_text_using_mistral(pil_img, config):
    """Extract text from image using Mistral OCR engine.
    
    Args:
        pil_img: PIL Image object
        config: OCR configuration dict
    
    Returns:
        Extracted text string
    """
    if not ocr_engines:
        _logger.error("ocr_engines module not available for Mistral OCR")
        return ""
    
    try:
        # Get Mistral engine from factory
        mistral_config = config.copy()
        mistral_config['engine'] = 'mistral'
        
        engine = ocr_engines.get_ocr_engine(mistral_config)
        if not engine.is_available():
            url_missing = not (mistral_config.get('mistral_ocr_url') or '').strip()
            token_missing = not (mistral_config.get('mistral_ocr_token') or '').strip()
            
            if url_missing and token_missing:
                _logger.error("Mistral OCR NOT CONFIGURED: URL and token missing. Configure in Settings > OCR Settings. Processing stopped.")
            elif url_missing:
                _logger.error("Mistral OCR NOT CONFIGURED: URL missing. Configure in Settings > OCR Settings. Processing stopped.")
            else:
                _logger.error("Mistral OCR NOT CONFIGURED: Token missing. Configure in Settings > OCR Settings. Processing stopped.")
            return ""
        
        text = engine.extract_text(pil_img)
        if config.get('enable_debug_logging'):
            _logger.info("Mistral OCR extracted %d characters", len(text))
        return text
    except UserError:
        raise  # Re-raise UserError to stop processing and show popup
    except Exception as e:
        error_msg = f"Mistral OCR extraction failed: {str(e)}"
        _logger.error(error_msg)
        raise UserError(error_msg)


def _extract_pdf_bytes_using_mistral(pil_img, config):
    """Generate a searchable PDF: original image preserved for display.
    
    Mistral OCR returns markdown text WITHOUT position coordinates, so we cannot
    place text at correct positions on the page. Instead we:
    1. Create a PDF with the original image (so the PDF viewer shows the real document)
    2. Do NOT add a fake text layer (it would have wrong positions, breaking bounding boxes)
    3. The box_refinement_service will use its own OCR fallback (Tesseract) to create
       a properly-positioned text layer for bounding box coordinate snapping.
    
    Args:
        pil_img: PIL Image object
        config: OCR configuration dict
    
    Returns:
        PDF bytes or None if extraction fails
    """
    text = _extract_text_using_mistral(pil_img, config)
    if not text:
        return None
    
    if not fitz:
        _logger.error("PyMuPDF (fitz) not available; cannot create PDF for Mistral OCR")
        return None
    
    try:
        # Convert PIL image to bytes
        img_buffer = io.BytesIO()
        pil_img.save(img_buffer, format='JPEG', quality=95)
        img_buffer.seek(0)
        img_bytes = img_buffer.read()
        
        # Create a new PDF with the original image as the page background
        doc = fitz.open()
        
        # Get image dimensions to set page size correctly
        img_w, img_h = pil_img.size
        
        # Create page with same aspect ratio as the image (72 DPI base)
        max_dim = 842  # A4 height in points
        if img_h > img_w:
            page_h = max_dim
            page_w = int(img_w * max_dim / img_h)
        else:
            page_w = max_dim
            page_h = int(img_h * max_dim / img_w)
        
        page = doc.new_page(width=page_w, height=page_h)
        
        # Insert the original image as the page background
        page_rect = page.rect
        page.insert_image(page_rect, stream=img_bytes)
        
        # NOTE: We intentionally do NOT add an invisible text layer here.
        # Mistral OCR returns markdown text without position/coordinate data,
        # so any text we insert would be at arbitrary positions, causing
        # bounding boxes to be placed incorrectly.
        #
        # The box_refinement_service handles this gracefully:
        # 1. It first tries to search text in this PDF (will find nothing)
        # 2. It then falls back to apply_ocr_to_pdf() using Tesseract/Paddle
        #    which creates a PROPER text layer with correct spatial positions
        # 3. Bounding boxes are then snapped to the Tesseract text positions
        
        # Save PDF to bytes
        pdf_buffer = io.BytesIO()
        doc.save(pdf_buffer, garbage=4, deflate=True)
        doc.close()
        pdf_buffer.seek(0)
        
        _logger.info("Mistral OCR: Created image PDF (%d bytes) - text layer deferred to box refinement", 
                     len(pdf_buffer.getvalue()))
        
        return pdf_buffer.getvalue()
        
    except Exception as e:
        _logger.error("Mistral searchable PDF generation failed: %s", e)
        return None
