# -*- coding: utf-8 -*-
"""
Paddle OCR Module

Handles Paddle OCR text extraction using ocr_engines.
"""
import io
import logging
from odoo.exceptions import UserError

try:
    from . import ocr_engines
except ImportError:
    ocr_engines = None

_logger = logging.getLogger(__name__)


def _extract_text_using_paddle(pil_img, config):
    """Extract text from image using Paddle OCR engine.
    
    Args:
        pil_img: PIL Image object
        config: OCR configuration dict
    
    Returns:
        Extracted text string
    """
    if not ocr_engines:
        _logger.error("ocr_engines module not available for Paddle OCR")
        return ""
    
    try:
        # Get Paddle engine from factory
        paddle_config = config.copy()
        paddle_config['engine'] = 'paddle'
        
        engine = ocr_engines.get_ocr_engine(paddle_config)
        if not engine.is_available():
            _logger.error(
                "Paddle OCR NOT CONFIGURED: Library not installed. "
                "Install with: pip install paddleocr paddlepaddle. "
                "Processing stopped."
            )
            return ""
        
        text = engine.extract_text(pil_img)
        if config.get('enable_debug_logging'):
            _logger.info("Paddle OCR extracted %d characters", len(text))
        return text
    except UserError:
        raise  # Re-raise UserError to stop processing and show popup
    except Exception as e:
        error_msg = f"Paddle OCR extraction failed: {str(e)}"
        _logger.error(error_msg)
        raise UserError(error_msg)


def _extract_pdf_bytes_using_paddle(pil_img, config):
    """Generate PDF bytes with text layer using Paddle OCR.
    
    Args:
        pil_img: PIL Image object
        config: OCR configuration dict
    
    Returns:
        PDF bytes or None if extraction fails
    """
    text = _extract_text_using_paddle(pil_img, config)
    if not text:
        return None
    
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
        
        pdf_buffer = io.BytesIO()
        c = canvas.Canvas(pdf_buffer, pagesize=letter)
        y = 750
        
        for line in text.split('\n'):
            if y < 50:
                c.showPage()
                y = 750
            # Truncate long lines to prevent reportlab errors
            c.drawString(50, y, line[:100])
            y -= 12
        
        c.save()
        pdf_buffer.seek(0)
        return pdf_buffer.getvalue()
    except Exception as e:
        _logger.error("Paddle PDF generation failed: %s", e)
        return None
