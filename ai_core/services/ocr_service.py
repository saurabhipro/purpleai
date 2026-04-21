# -*- coding: utf-8 -*-
"""
OCR Service Module - Main Entry Point

Orchestrates OCR operations using engine-specific modules:
- Tesseract (ocr_tesseract.py)
- Paddle OCR (ocr_paddle.py)  
- Mistral OCR (ocr_mistral.py)

Provides main entry points:
- apply_ocr_to_pdf: Create searchable PDF from scanned document
- apply_pdf_highlights: Return searchable PDF as base64
"""
import io
import logging
import os
import base64
from odoo import _
from odoo.exceptions import UserError

try:
    import fitz
    from PIL import Image as PILImage
except ImportError:
    fitz = None
    PILImage = None

from .ocr_config import _get_ocr_config
from .ocr_utils import _preprocess_image, check_pdf_searchability
from .ocr_tesseract import _extract_pdf_bytes_using_tesseract
from .ocr_paddle import _extract_pdf_bytes_using_paddle
from .ocr_mistral import _extract_pdf_bytes_using_mistral

_logger = logging.getLogger(__name__)


def apply_ocr_to_pdf(file_path, env=None, config_override=None):
    """Apply OCR to PDF with images to create searchable text layer.
    
    Args:
        file_path: Path to the PDF file
        env: Odoo environment (for configuration)
        config_override: Optional dict to override OCR config settings (for dynamic quality adjustment)
    
    Returns:
        fitz.Document with OCR text layer, or None on failure
    """
    if not fitz:
        _logger.warning("PyMuPDF (fitz) not available; OCR skipped")
        return None
    
    if not PILImage:
        _logger.warning("PIL not available; OCR skipped")
        return None
    
    # Use provided config or get from environment
    if config_override:
        config = config_override
    else:
        config = _get_ocr_config(env)
    engine = config.get('engine', 'tesseract')
    
    # Validate engine configuration before processing
    if engine in ('mistral', 'paddle'):
        from . import ocr_engines
        test_engine = ocr_engines.get_ocr_engine(config)
        if test_engine and not test_engine.is_available():
            error_msg = (
                f"OCR Engine '{engine.upper()}' is NOT configured properly.\n\n"
                f"{'Please configure Mistral OCR settings in Settings > OCR Settings:' if engine == 'mistral' else 'Paddle OCR library is not installed.'}"
            )
            if engine == 'mistral':
                error_msg += "\n• Mistral OCR API URL\n• Mistral OCR Token\n• Mistral OCR Model (default: Mistral OCR 2)"
            else:
                error_msg += "\n\nInstall with: pip install paddleocr paddlepaddle"
            
            _logger.error(
                "OCR engine '%s' is selected but NOT properly configured. "
                "Processing stopped.", engine
            )
            raise UserError(error_msg)
    
    try:
        doc = fitz.open(file_path)
        if len(doc) == 0:
            _logger.warning("Empty PDF: %s", file_path)
            doc.close()
            return None
        
        if config.get('enable_debug_logging'):
            _logger.info("Starting OCR on %s (%d pages) using %s engine", 
                        file_path, len(doc), engine)
        
        merged = fitz.open()
        page_count = 0
        
        # MEMORY SAFETY: Cap DPI for Tesseract (high DPI causes malloc failures)
        # Tesseract memory usage grows quadratically with DPI
        # At 200 DPI: ~180-200MB per page (unsafe for most systems)
        # At 150 DPI: ~100-120MB per page (safe)
        # At 120 DPI: ~60-80MB per page (safest)
        dpi = config['dpi']
        if engine == 'tesseract':
            if dpi > 150:
                _logger.warning(
                    "DPI %d too high for Tesseract (memory usage ~%dMB per page). "
                    "Reducing to 150 DPI for memory safety.", 
                    dpi, int((dpi/72.0)**2 * 10)  # Rough estimate
                )
                dpi = 150
            
        scale = dpi / 72.0
        
        # Process pages
        for page_num in range(min(len(doc), 10)):  # Limit to 10 pages
            try:
                page = doc[page_num]
                mat = fitz.Matrix(scale, scale)
                pix = page.get_pixmap(matrix=mat, alpha=False)
                img = PILImage.open(io.BytesIO(pix.tobytes("jpeg")))
                
                # Preprocess image
                img = _preprocess_image(img, config)
                
                # Route to appropriate engine
                if engine == 'tesseract':
                    pdf_bytes = _extract_pdf_bytes_using_tesseract(img, config)
                elif engine == 'paddle':
                    pdf_bytes = _extract_pdf_bytes_using_paddle(img, config)
                elif engine == 'mistral':
                    pdf_bytes = _extract_pdf_bytes_using_mistral(img, config)
                else:
                    _logger.error("Unknown OCR engine: %s", engine)
                    pdf_bytes = None
                
                if pdf_bytes:
                    page_pdf = fitz.open("pdf", pdf_bytes)
                    merged.insert_pdf(page_pdf)
                    page_pdf.close()
                    page_count += 1
                else:
                    # If engine returned nothing, treat as a critical configuration or API failure
                    error_msg = f"OCR engine '{engine}' failed to process page {page_num + 1}. Please check your API/Library configuration."
                    _logger.error(error_msg)
                    raise UserError(error_msg)
                    
            except UserError:
                raise  # Always propagate UserError (config issues) to show popup
            except MemoryError as e:
                # Handle out-of-memory gracefully with helpful message
                _logger.error("OUT OF MEMORY during OCR on page %d. Tesseract exhausted available RAM.", page_num)
                raise UserError(
                    _("❌ Out of Memory: Tesseract OCR ran out of memory on page %d.\n\n"
                      "This is a Tesseract limitation with high-resolution PDFs.\n\n"
                      "🛠️ SOLUTIONS:\n"
                      "1. Switch to Paddle OCR (more memory efficient)\n"
                      "2. Switch to Mistral OCR (cloud-based)\n"
                      "3. Reduce DPI to 100-120 (but loses quality)\n\n"
                      "⚠️ Current OCR DPI=%d is too high for this system's available RAM.\n"
                      "Tesseract needs ~%dMB per page at this DPI.") 
                    % (page_num + 1, dpi, int((dpi/72.0)**2 * 10))
                )
            except Exception as e:
                # Treat any engine-level exception (e.g., NetworkError, LibraryError) 
                # as a reason to STOP immediately and show a popup.
                error_str = str(e)
                if 'malloc' in error_str.lower():
                    _logger.error("MALLOC FAILURE on page %d: %s. System has insufficient RAM for Tesseract at %d DPI.", page_num, e, dpi)
                    raise UserError(
                        _("❌ Memory Allocation Failed on page %d.\n\n"
                          "Tesseract couldn't allocate %s bytes.\n\n"
                          "🛠️ SOLUTIONS:\n"
                          "1. Best: Switch to Paddle OCR (handles high-res PDFs better)\n"
                          "2. Alternative: Use Mistral OCR (cloud-based)\n"
                          "3. Workaround: Reduce DPI to 100-120 DPI\n\n"
                          "Current DPI=%d") 
                        % (page_num + 1, error_str.split('malloc')[1].split(')')[0] if 'malloc' in error_str else '?', dpi)
                    )
                else:
                    _logger.error("OCR failed critically on page %d: %s", page_num, e)
                    raise UserError(_("OCR engine '%s' failed critically on page %d. Error: %s") % (engine, page_num + 1, str(e)))
        
        doc.close()
        
        if len(merged) > 0:
            if config.get('enable_debug_logging'):
                _logger.info("OCR SUCCESS: %d pages processed with %s", page_count, engine)
            return merged
        else:
            _logger.warning("OCR produced no pages")
            merged.close()
            return None
            
    except UserError:
        raise  # Propagate UserError to stop processing
    except Exception as e:
        _logger.error("OCR failed for %s: %s", file_path, e)
        # Convert critical network/API errors to UserError to stop batch
        error_msg = str(e)
        if "HTTPSConnectionPool" in error_msg or "NameResolutionError" in error_msg:
            raise UserError(_("OCR Network Error: Failed to connect to %s. Please check your internet connection or URL.\n\nDetails: %s") % (engine, error_msg))
        return None


def apply_ocr_to_pdf_with_tracking(file_path, env=None, config_override=None):
    """Apply OCR to PDF and return both document and engine used.
    
    Args:
        file_path: Path to the PDF file
        env: Odoo environment
        config_override: Optional dict to override OCR config settings (for dynamic quality adjustment)
    
    Returns:
        Tuple of (document, engine_name) or (None, engine_name)
        If OCR fails or is misconfigured, returns (None, engine_name)
    """
    config = _get_ocr_config(env)
    
    # Apply config overrides for dynamic quality enhancement
    if config_override:
        config.update(config_override)
    
    configured_engine = config.get('engine', 'tesseract')
    
    ocr_doc = apply_ocr_to_pdf(file_path, env, config_override=config)
    
    # Return result without any fallback
    return ocr_doc, configured_engine


def apply_pdf_highlights(file_path, extracted_json=None, failures=None, env=None):
    """Returns searchable PDF as base64.
    
    Args:
        file_path: Path to source file
        extracted_json: Extracted field data (unused, for compatibility)
        failures: Validation failures (unused, for compatibility)
        env: Odoo environment
    
    Returns:
        Base64-encoded PDF bytes
    """
    IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp', '.gif', '.webp'}
    ext = os.path.splitext(file_path)[1].lower()

    def _raw_bytes():
        try:
            with open(file_path, 'rb') as f:
                return base64.b64encode(f.read())
        except Exception:
            return False

    if not fitz:
        return _raw_bytes()
    
    config = _get_ocr_config(env)
    
    # Check if already searchable
    try:
        doc = fitz.open(file_path)
        if config.get('check_searchability'):
            has_text = (ext not in IMAGE_EXTS) and any(p.get_text().strip() for p in doc)
        else:
            has_text = False
        doc.close()
    except Exception:
        return _raw_bytes()

    if has_text:
        if config.get('enable_debug_logging'):
            _logger.info("PDF already searchable, skipping OCR: %s", file_path)
        return _raw_bytes()

    # Apply OCR
    ocr_doc = apply_ocr_to_pdf(file_path, env)
    if not ocr_doc:
        _logger.warning("OCR failed for %s, returning original", file_path)
        return _raw_bytes()

    # Return as base64
    out = io.BytesIO()
    ocr_doc.save(out, garbage=4, deflate=True)
    ocr_doc.close()
    return base64.b64encode(out.getvalue())

