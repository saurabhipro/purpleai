# -*- coding: utf-8 -*-
import logging
from PIL import Image as PILImage

try:
    import fitz
except ImportError:
    fitz = None

_logger = logging.getLogger(__name__)

def _preprocess_image(pil_img, config):
    """Apply smart preprocessing to improve OCR accuracy.
    
    Includes:
    - Denoise: MedianFilter to remove noise while preserving edges
    - Deskew: Detect and correct text rotation
    - Contrast: Enhance difference between text and background
    - Threshold: DISABLED by default - too destructive for low quality PDFs
    
    Note: Threshold is NOT applied as it destroys text details in low-quality scans.
    """
    try:
        from PIL import ImageFilter, ImageEnhance
    except ImportError:
        return pil_img
    
    if not any([config.get('preprocess_denoise'), config.get('preprocess_deskew'), 
                config.get('preprocess_contrast')]):
        return pil_img
    
    target_mode = config.get('image_mode', 'RGB')
    if pil_img.mode != target_mode:
        pil_img = pil_img.convert(target_mode)
    
    try:
        # Step 1: Denoise - smooth out noise while keeping text sharp
        if config.get('preprocess_denoise'):
            # Use MedianFilter for edge-preserving noise reduction
            pil_img = pil_img.filter(ImageFilter.MedianFilter(size=3))
            _logger.debug("Applied denoise filter")
        
        # Step 2: Deskew - correct text rotation
        if config.get('preprocess_deskew'):
            pil_img = _deskew_image(pil_img)
            _logger.debug("Applied deskew filter")
        
        # Step 3: Contrast enhancement - improve text legibility
        if config.get('preprocess_contrast'):
            enhancer = ImageEnhance.Contrast(pil_img)
            pil_img = enhancer.enhance(1.3)  # Softer than 1.5
            _logger.debug("Applied contrast enhancement (1.3x)")
        
        # NOTE: preprocess_threshold is intentionally disabled as it destroys text
        # Binary thresholding converts to pure black/white per pixel, which:
        # - Destroys sub-pixel antialiasing on text
        # - Removes gradients in low-quality scans
        # - Converts font rendering artifacts to noise
        # Instead, rely on Tesseract's built-in adaptive thresholding (--psm modes)
        
        return pil_img
    except Exception as e:
        _logger.warning("Image preprocessing failed: %s", e)
        return pil_img


def _deskew_image(pil_img):
    """Detect and correct text rotation in image.
    
    Uses edge detection + Hough transform to find dominant text angle.
    Handles rotations ±15 degrees.
    """
    try:
        import numpy as np
        import cv2
        
        # Convert to grayscale for rotation detection
        img_cv = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2GRAY)
        
        # Edge detection to find text boundaries
        edges = cv2.Canny(img_cv, 50, 150)
        
        # Find lines using Hough transform
        lines = cv2.HoughLines(edges, 1, np.pi/180, 100)
        
        if lines is None or len(lines) == 0:
            _logger.debug("No text rotation detected")
            return pil_img
        
        # Calculate average angle from detected lines
        angles = []
        for line in lines:
            rho, theta = line[0]
            # Convert from Hough theta to rotation angle in degrees
            angle = np.degrees(theta) - 90
            # Normalize to [-45, 45] range
            if angle > 45:
                angle -= 180
            if angle < -45:
                angle += 180
            angles.append(angle)
        
        # Use median angle to avoid outliers
        if angles:
            avg_angle = np.median(angles)
            # Only correct if rotation is significant (>1 degree)
            if abs(avg_angle) > 1:
                _logger.debug("Correcting text rotation: %.2f degrees", avg_angle)
                # Rotate image to level the text
                height, width = img_cv.shape
                center = (width // 2, height // 2)
                matrix = cv2.getRotationMatrix2D(center, -avg_angle, 1.0)
                rotated = cv2.warpAffine(np.array(pil_img), matrix[:2], (width, height), 
                                        borderMode=cv2.BORDER_REPLICATE)
                pil_img = PILImage.fromarray(rotated)
        
        return pil_img
    except ImportError:
        _logger.debug("OpenCV not available, skipping deskew")
        return pil_img
    except Exception as e:
        _logger.warning("Deskew operation failed: %s", e)
        return pil_img

def check_pdf_searchability(file_path, config, env=None):
    if not fitz: return True, 0
    try:
        threshold = config.get('searchability_threshold', 100)
        doc = fitz.open(file_path)
        total_text = sum(len(doc[i].get_text().strip()) for i in range(min(len(doc), 5)))
        doc.close()
        return total_text >= threshold, total_text
    except Exception: return True, 0

def _cleanup_tesseract_processes():
    try:
        import psutil
        for p in psutil.process_iter(['name']):
            if p.info.get('name') and 'tesseract' in p.info.get('name').lower():
                try: p.kill()
                except Exception: pass
    except Exception:
        try:
            import subprocess
            subprocess.run(['pkill', '-f', 'tesseract'], timeout=2)
        except Exception: pass
