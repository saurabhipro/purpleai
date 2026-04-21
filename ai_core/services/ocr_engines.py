# -*- coding: utf-8 -*-
"""
OCR Engines Module

Provides engine implementations for different OCR backends.
Each engine handles its specific initialization and text extraction logic.
"""
import logging
import base64
import io
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class BaseOCREngine:
    """Base class for OCR engines."""
    
    def __init__(self, config):
        self.config = config
        self.engine_name = "base"
    
    def extract_text(self, image_data):
        raise NotImplementedError("Subclasses must implement extract_text()")
    
    def is_available(self):
        raise NotImplementedError("Subclasses must implement is_available()")


class MistralOCREngine(BaseOCREngine):
    """Mistral OCR API engine implementation."""
    
    def __init__(self, config):
        super().__init__(config)
        self.engine_name = "mistral"
        self.url = (config.get('mistral_ocr_url') or '').strip()
        self.token = (config.get('mistral_ocr_token') or '').strip()
        self.model = (config.get('mistral_ocr_model') or 'mistral-document-ai-2505').strip()
    
    def is_available(self):
        """Check if Mistral OCR is configured with URL and token."""
        return bool(self.url and self.token)
    
    def extract_text(self, image_data):
        """Extract text using Mistral OCR API.
        
        Args:
            image_data: PIL Image object
        
        Returns:
            Extracted text string
        """
        if not self.is_available():
            _logger.error("Mistral OCR not configured (missing URL or token)")
            return ""
        
        try:
            import requests
            
            # Convert PIL Image to base64
            img_buffer = io.BytesIO()
            image_data.save(img_buffer, format='PNG')
            img_buffer.seek(0)
            img_base64 = base64.b64encode(img_buffer.read()).decode('utf-8')
            
            # Mistral Document AI OCR API expects document_url at top level
            img_data_uri = f"data:image/png;base64,{img_base64}"
            
            # Call Mistral OCR API
            headers = {
                'Authorization': f"Bearer {self.token}",
                'Content-Type': 'application/json'
            }
            
            # Mistral Document AI OCR API format:
            # document_url with data URI at document level (no type field)
            payload = {
                'model': self.model,
                'document': {
                    'document_url': img_data_uri
                }
            }
            
            _logger.debug("Mistral OCR request: url=%s, model=%s, image_size=%d bytes", 
                         self.url, self.model, len(img_base64))
            
            response = requests.post(
                self.url.rstrip('/'),
                json=payload,
                headers=headers,
                timeout=self.config.get('timeout_per_page', 30)
            )
            
            if response.status_code == 200:
                result = response.json()
                
                # Handle different possible response structures from Mistral OCR
                text = ''
                if 'pages' in result and result['pages']:  # Pages array response (primary format)
                    pages_text = []
                    for page in result['pages']:
                        if isinstance(page, dict):
                            # Mistral OCR returns 'markdown' per page
                            if 'markdown' in page:
                                pages_text.append(page['markdown'])
                            elif 'text' in page:
                                pages_text.append(page['text'])
                        elif isinstance(page, str):
                            pages_text.append(page)
                    text = '\n'.join(pages_text)
                elif 'text' in result:  # Direct text response
                    text = result.get('text', '')
                elif 'result' in result:  # Wrapped result
                    if isinstance(result['result'], dict):
                        text = result['result'].get('text', '')
                    elif isinstance(result['result'], list) and result['result']:
                        text = result['result'][0].get('text', '')
                elif 'documents' in result and result['documents']:  # Document array response
                    text = result['documents'][0].get('text', '')
                
                if not text:
                    # If no text extracted, log the full response for debugging
                    _logger.warning("Mistral OCR returned 200 but no text found: %s", str(result)[:200])
                
                _logger.debug("Mistral OCR extracted %d characters", len(text))
                return text
            else:
                # Extract error details from JSON response if available
                try:
                    error_json = response.json()
                    error_detail = error_json.get('error', {})
                    if isinstance(error_detail, dict):
                        error_detail = error_detail.get('message', str(error_detail)[:200])
                    else:
                        error_detail = str(error_detail)[:200]
                except Exception:
                    error_detail = response.text[:300]
                
                # Log full error for debugging 422 issues
                _logger.error("Mistral OCR API Error %d: %s | Full Response: %s", 
                             response.status_code, error_detail, response.text[:500])
                
                error_msg = (
                    f"Mistral OCR API Error: {response.status_code}\\n\\n"
                    f"Details: {error_detail}\\n\\n"
                    f"Please check your Mistral OCR configuration in Settings > OCR Settings."
                )
                _logger.error("Mistral OCR API error: %s - %s", response.status_code, error_detail)
                raise UserError(error_msg)
                
        except UserError:
            raise  # Re-raise UserError without wrapping
        except Exception as e:
            error_msg = (
                f"Mistral OCR Processing Error\\n\\n"
                f"Error: {str(e)}\\n\\n"
                f"This could be a network issue or API configuration problem."
            )
            _logger.error("Mistral OCR error: %s", e)
            raise UserError(error_msg)


class PaddleOCREngine(BaseOCREngine):
    """Paddle OCR engine implementation."""
    
    def __init__(self, config):
        super().__init__(config)
        self.engine_name = "paddle"
        self.ocr = None
        
        try:
            from paddleocr import PaddleOCR
            self.PaddleOCR = PaddleOCR
            self.available = True
        except ImportError:
            self.PaddleOCR = None
            self.available = False
            _logger.warning("Paddle OCR: paddleocr not installed")
    
    def is_available(self):
        """Check if Paddle OCR library is available."""
        return self.available
    
    def _get_ocr_instance(self):
        """Get or initialize PaddleOCR instance with caching."""
        if self.ocr is None and self.PaddleOCR:
            try:
                import os
                
                # Set cache directory if configured
                cache_dir = self.config.get('paddle_ocr_model_dir', '~/.paddleocr')
                if cache_dir:
                    os.environ.setdefault('PADDLE_CACHE_HOME', os.path.expanduser(cache_dir))
                
                # Initialize with current parameter names (not deprecated ones)
                self.ocr = self.PaddleOCR(
                    use_textline_orientation=self.config.get('paddle_ocr_enable_angle', True),
                    text_recognition_batch_size=self.config.get('paddle_ocr_cls_batch_num', 30),
                    text_det_thresh=self.config.get('paddle_ocr_det_db_thresh', 0.3),
                    cpu_threads=self.config.get('paddle_ocr_num_threads', 4),
                    lang='en'  # Default to English
                )
                
                _logger.info("Paddle OCR initialized successfully")
                
            except Exception as e:
                _logger.error("Paddle OCR initialization failed: %s", e)
                return None
        
        return self.ocr
    
    def extract_text(self, image_data):
        """Extract text using Paddle OCR.
        
        Args:
            image_data: PIL Image object
        
        Returns:
            Extracted text string
        """
        if not self.is_available():
            _logger.error("Paddle OCR engine not available")
            return ""
        
        try:
            ocr = self._get_ocr_instance()
            if ocr is None:
                return ""
            
            # Convert PIL Image to numpy array
            import numpy as np
            image_array = np.array(image_data.convert('RGB'))
            
            # Run OCR
            result = ocr.ocr(image_array, cls=True)
            
            # Extract text from result
            text_lines = []
            if result and result[0]:
                for line in result[0]:
                    if line and len(line) >= 2:
                        text_lines.append(line[1][0])  # line[1][0] is the text
            
            text = '\n'.join(text_lines)
            _logger.debug("Paddle OCR extracted %d characters", len(text))
            return text
            
        except Exception as e:
            _logger.error("Paddle OCR error: %s", e)
            return ""


def get_ocr_engine(config):
    """Factory function to get appropriate OCR engine.
    
    Args:
        config: OCR configuration dict
    
    Returns:
        OCR engine instance based on config['engine']
    """
    engine_type = config.get('engine', 'tesseract')
    
    if engine_type == 'mistral':
        _logger.info("Creating Mistral OCR engine")
        return MistralOCREngine(config)
    elif engine_type == 'paddle':
        _logger.info("Creating Paddle OCR engine")
        return PaddleOCREngine(config)
    else:
        _logger.warning("Unknown OCR engine type: %s, using None", engine_type)
        return None
