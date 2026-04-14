# -*- coding: utf-8 -*-
import os
import logging
try:
    import fitz
except Exception:
    fitz = None

_logger = logging.getLogger(__name__)


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
