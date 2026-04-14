# -*- coding: utf-8 -*-
"""
Box Refinement Service Module

Handles PDF text-matching for bounding box refinement and coordinates snapping.
Provides utilities to precisely locate extracted field values within PDF text layers.

Features:
  - Variant-based text search (numbers, currencies, partial matches)
  - Bounding box IoU (Intersection over Union) calculation
  - Automatic OCR fallback for image-heavy PDFs
  - Hierarchical box selection (best IoU match or largest box)
"""
import os
import re
import logging

try:
    import fitz
except ImportError:
    fitz = None

_logger = logging.getLogger(__name__)


def _detailed_logging_enabled(env):
    """Check if detailed logging is enabled via ir.config_parameter."""
    try:
        val = env['ir.config_parameter'].sudo().get_param('purple_ai.detailed_logging', 'False')
        return str(val).lower() in ('1', 'true', 'yes', 'y')
    except Exception:
        return False


def search_string_variants(value):
    """Candidate substrings to find extracted values inside PDF text.
    
    Generates multiple variants of a string to maximize text search matches,
    handling currency symbols, spaces, numbers, and partial matches.
    
    Args:
        value: The value to search for (string/number)
    
    Returns:
        List of candidate search strings
    """
    if value is None:
        return []
    s = str(value).strip()
    if not s or s.lower() in ('---', 'null', 'none', 'n/a', 'undefined'):
        return []
    seen = set()
    out = []

    def add(x):
        x = str(x).strip()
        if x and x not in seen and len(x) >= 1:
            seen.add(x)
            out.append(x)

    add(s)
    
    # Variants: remove spaces and currency symbols
    compact = re.sub(r'[\s₹$€]', '', s)
    compact = compact.replace(',', '')
    if compact and compact != s.replace(' ', ''):
        add(compact)
    
    # Try with dashes removed too
    no_dash = s.replace('-', '')
    if no_dash and no_dash != s:
        add(no_dash)
    
    # Extract numeric part and variants
    num = re.search(r'-?[\d]+(?:[.,][\d]+)?', s.replace(',', ''))
    if num:
        raw = num.group(0).replace(',', '.')
        add(raw)
        try:
            f = float(raw)
            # Try different formats
            if abs(f - round(f)) < 1e-9:
                add(str(int(round(f))))
            add(f'{f:.2f}')
            add(f'{f:.1f}')
            add(str(int(f)))
        except ValueError:
            pass
    
    # For short strings, try partial matches
    if 1 <= len(s) <= 15:
        for i in range(len(s) - 1):
            for j in range(i + 2, len(s) + 1):
                substr = s[i:j].strip()
                if len(substr) >= 2:
                    add(substr)
    
    return out


def rect_to_box2d(rect, pw, ph):
    """Convert PyMuPDF rectangle to normalized 2D box [y0, x0, y1, x1].
    
    Normalizes coordinates to 0-1000 scale and validates box dimensions.
    
    Args:
        rect: PyMuPDF Rect object
        pw: Page width in pixels
        ph: Page height in pixels
    
    Returns:
        [y0, x0, y1, x1] normalized box, or None if invalid
    """
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


def box_iou_yxyx(a, b):
    """Calculate Intersection over Union (IoU) between two normalized boxes.
    
    Both boxes are in [y0, x0, y1, x1] format on scale 0-1000.
    
    Args:
        a: First box [y0, x0, y1, x1]
        b: Second box [y0, x0, y1, x1]
    
    Returns:
        IoU score (0.0 to 1.0)
    """
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


def page_search_hits(page, query, ignore_case=False):
    """Search for text in a PDF page and return rectangles.
    
    Args:
        page: PyMuPDF page object
        query: Search string
        ignore_case: Whether to ignore case (for non-numeric searches)
    
    Returns:
        List of fitz.Rect objects where text was found
    """
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


def pick_best_rect(rects, pw, ph, existing_box):
    """Select the best bounding rectangle from search results.
    
    Prioritizes rectangles with highest IoU overlap with existing_box.
    Falls back to largest rectangle if no good overlap found.
    
    Args:
        rects: List of PyMuPDF Rect objects
        pw: Page width
        ph: Page height
        existing_box: Existing normalized box [y0, x0, y1, x1] to align with
    
    Returns:
        fitz.Rect object (the best match), or None
    """
    if not rects:
        return None
    if len(rects) == 1:
        return rects[0]
    if existing_box and isinstance(existing_box, list) and len(existing_box) == 4:
        best_r = None
        best_iou = 0.0
        for r in rects:
            b = rect_to_box2d(r, pw, ph)
            if not b:
                continue
            iou = box_iou_yxyx(existing_box, b)
            if iou > best_iou:
                best_iou = iou
                best_r = r
        if best_r is not None and best_iou >= 0.02:
            return best_r

    # For text-only providers (Azure/OpenAI): pick largest rectangle
    def area(r):
        return max(0.0, (r.x1 - r.x0) * (r.y1 - r.y0))
    
    return max(rects, key=area) if rects else None


def refine_extracted_boxes_with_fitz(file_path, data, env=None):
    """Snap model box_2d to PyMuPDF text hits so highlights match real glyphs.
    
    For PDFs with images (e.g., scanned documents), automatically applies OCR
    to create a searchable text layer when text search fails, enabling bounding
    box extraction for Azure AI and other providers that don't provide coordinates.
    
    Args:
        file_path: Path to PDF file
        data: Extracted data dictionary with 'field_key': {value, box_2d, page_number, ...}
        env: Odoo environment (for logging configuration)
    
    Returns:
        Updated data dictionary with refined box_2d values
    """
    if not fitz or not isinstance(data, dict):
        return data
    path = str(file_path or '')
    if not path.lower().endswith('.pdf') or not os.path.isfile(path):
        return data
    
    doc = None
    ocr_doc = None  # Fallback OCR'd PDF for image-heavy documents
    
    try:
        doc = fitz.open(path)
    except Exception as e:
        _logger.debug('refine_extracted_boxes_with_fitz: open failed: %s', e)
        return data
    
    try:
        for key, item in list(data.items()):
            if key == 'validations' or not isinstance(item, dict):
                continue
            val = item.get('value')
            variants = search_string_variants(val)
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
                    page_search_hits(page, q, ignore_case=not numericish)
                )
            
            # If no text found, PDF may contain images. Apply OCR once and retry search.
            if not rects:
                if ocr_doc is None:
                    if _detailed_logging_enabled(env) and env is not None:
                        _logger.info("refine_extracted_boxes_with_fitz: Text search failed for field '%s' (value='%s') -> attempting OCR on %s", key, val, os.path.basename(path))
                    try:
                        from odoo.addons.invoiceai.services import ocr_service
                        ocr_doc = ocr_service.apply_ocr_to_pdf(path, env=env)
                        if ocr_doc is not None:
                            if _detailed_logging_enabled(env) and env is not None:
                                _logger.info("refine_extracted_boxes_with_fitz: OCR applied successfully; retrying text search for '%s'", key)
                        else:
                            if _detailed_logging_enabled(env) and env is not None:
                                _logger.warning("refine_extracted_boxes_with_fitz: OCR returned None for %s", os.path.basename(path))
                    except Exception as e:
                        if _detailed_logging_enabled(env) and env is not None:
                            _logger.error("refine_extracted_boxes_with_fitz: OCR failed for %s: %s", os.path.basename(path), e)
                
                # Retry search on OCR'd PDF if available
                if ocr_doc is not None and pidx < len(ocr_doc):
                    ocr_page = ocr_doc[pidx]
                    variants_found = []
                    for q in variants:
                        hits = page_search_hits(ocr_page, q, ignore_case=not numericish)
                        if hits:
                            variants_found.append(q)
                        rects.extend(hits)
                    if rects:
                        if _detailed_logging_enabled(env) and env is not None:
                            _logger.info("refine_extracted_boxes_with_fitz: SUCCESS - Field '%s' (value='%s') found in OCR'd PDF via variants: %s", key, val, variants_found)
                    else:
                        if _detailed_logging_enabled(env) and env is not None:
                            _logger.debug("refine_extracted_boxes_with_fitz: Field '%s' (value='%s') NOT found even in OCR'd PDF, tried variants: %s", key, val, variants)
            
            if not rects:
                continue
            existing = item.get('box_2d')
            chosen = pick_best_rect(rects, pw, ph, existing if isinstance(existing, list) else None)
            if not chosen:
                continue
            new_box = rect_to_box2d(chosen, pw, ph)
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
        if ocr_doc is not None:
            try:
                ocr_doc.close()
            except:
                pass
