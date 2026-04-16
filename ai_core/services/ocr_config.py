# -*- coding: utf-8 -*-
"""
OCR Configuration Module

Centralized configuration management for OCR services.
Retrieves settings from Odoo database (ir.config_parameter).
"""
import logging

_logger = logging.getLogger(__name__)


def _get_ocr_config(env=None):
    """Get OCR configuration from database settings.
    
    Args:
        env: Odoo environment for database access
    
    Returns:
        dict with OCR configuration. Falls back to defaults if env is unavailable.
    """
    defaults = {
        'engine': 'tesseract',
        'dpi': 200,
        'languages': 'hin+eng',
        'timeout_per_page': 30,
        'timeout_total': 300,
        'mistral_ocr_url': '',
        'mistral_ocr_token': '',
        'mistral_ocr_model': 'mistral-document-ai-2505',
        'paddle_ocr_use_gpu': False,
        'paddle_ocr_enable_angle': True,
        'paddle_ocr_model_dir': '~/.paddleocr',
        'paddle_ocr_num_threads': 4,
        'paddle_ocr_cls_batch_num': 30,
        'paddle_ocr_det_db_thresh': 0.3,
        'preprocess_denoise': False,
        'preprocess_deskew': False,
        'preprocess_contrast': False,
        'preprocess_threshold': False,
        'image_mode': 'RGB',
        'psm_mode': 3,
        'oem_mode': 3,
        'max_memory_mb': 1024,
        'render_scale_factor': 2.78,
        'check_searchability': True,
        'searchability_threshold': 100,
        'enable_box_refinement': True,
        'box_refinement_threshold': 0.7,
        'enable_ocr_fallback': True,
        'retry_on_error': True,
        'enable_debug_logging': False,
    }
    
    if not env:
        return defaults
    
    try:
        config_param = env['ir.config_parameter'].sudo()
        config = {}
        
        # Fetch OCR engine selection
        config['engine'] = config_param.get_param('ai_core.ocr_engine', defaults['engine'])
        
        # Fetch all OCR settings from database
        config['dpi'] = int(config_param.get_param('ai_core.ocr_dpi', defaults['dpi']))
        config['languages'] = config_param.get_param('ai_core.ocr_languages', defaults['languages'])
        config['timeout_per_page'] = int(config_param.get_param('ai_core.ocr_timeout_per_page', defaults['timeout_per_page']))
        config['timeout_total'] = int(config_param.get_param('ai_core.ocr_timeout_total', defaults['timeout_total']))
        
        # Mistral OCR settings
        config['mistral_ocr_url'] = config_param.get_param('ai_core.mistral_ocr_url', defaults['mistral_ocr_url'])
        config['mistral_ocr_token'] = config_param.get_param('ai_core.mistral_ocr_token', defaults['mistral_ocr_token'])
        config['mistral_ocr_model'] = config_param.get_param('ai_core.mistral_ocr_model', defaults['mistral_ocr_model'])
        
        # Paddle OCR settings
        config['paddle_ocr_use_gpu'] = config_param.get_param('ai_core.paddle_ocr_use_gpu', 'False').lower() in ('true', '1', 'yes')
        config['paddle_ocr_enable_angle'] = config_param.get_param('ai_core.paddle_ocr_enable_angle', 'True').lower() in ('true', '1', 'yes')
        config['paddle_ocr_model_dir'] = config_param.get_param('ai_core.paddle_ocr_model_dir', defaults['paddle_ocr_model_dir'])
        config['paddle_ocr_num_threads'] = int(config_param.get_param('ai_core.paddle_ocr_num_threads', defaults['paddle_ocr_num_threads']))
        config['paddle_ocr_cls_batch_num'] = int(config_param.get_param('ai_core.paddle_ocr_cls_batch_num', defaults['paddle_ocr_cls_batch_num']))
        config['paddle_ocr_det_db_thresh'] = float(config_param.get_param('ai_core.paddle_ocr_det_db_thresh', defaults['paddle_ocr_det_db_thresh']))
        
        config['preprocess_denoise'] = config_param.get_param('ai_core.ocr_preprocess_denoise', 'False').lower() in ('true', '1', 'yes')
        config['preprocess_deskew'] = config_param.get_param('ai_core.ocr_preprocess_deskew', 'False').lower() in ('true', '1', 'yes')
        config['preprocess_contrast'] = config_param.get_param('ai_core.ocr_preprocess_contrast', 'False').lower() in ('true', '1', 'yes')
        config['preprocess_threshold'] = config_param.get_param('ai_core.ocr_preprocess_threshold', 'False').lower() in ('true', '1', 'yes')
        config['image_mode'] = config_param.get_param('ai_core.ocr_image_mode', defaults['image_mode'])
        config['psm_mode'] = int(config_param.get_param('ai_core.ocr_psm_mode', defaults['psm_mode']))
        config['oem_mode'] = int(config_param.get_param('ai_core.ocr_oem_mode', defaults['oem_mode']))
        config['max_memory_mb'] = int(config_param.get_param('ai_core.ocr_max_memory_mb', defaults['max_memory_mb']))
        config['render_scale_factor'] = float(config_param.get_param('ai_core.ocr_render_scale_factor', defaults['render_scale_factor']))
        config['check_searchability'] = config_param.get_param('ai_core.ocr_check_searchability', 'True').lower() in ('true', '1', 'yes')
        config['searchability_threshold'] = int(config_param.get_param('ai_core.ocr_searchability_threshold', defaults['searchability_threshold']))
        config['enable_box_refinement'] = config_param.get_param('ai_core.ocr_enable_box_refinement', 'True').lower() in ('true', '1', 'yes')
        config['box_refinement_threshold'] = float(config_param.get_param('ai_core.ocr_box_refinement_threshold', defaults['box_refinement_threshold']))
        config['enable_ocr_fallback'] = config_param.get_param('ai_core.ocr_enable_ocr_fallback', 'True').lower() in ('true', '1', 'yes')
        config['retry_on_error'] = config_param.get_param('ai_core.ocr_retry_on_error', 'True').lower() in ('true', '1', 'yes')
        config['enable_debug_logging'] = config_param.get_param('ai_core.ocr_enable_debug_logging', 'False').lower() in ('true', '1', 'yes')
        
        return config
    except Exception as e:
        _logger.warning("Error loading OCR config from database, using defaults: %s", e)
        return defaults


def _detailed_logging_enabled(env):
    """Check if detailed logging is enabled via ir.config_parameter."""
    try:
        val = env['ir.config_parameter'].sudo().get_param('purple_ai.detailed_logging', 'False')
        return str(val).lower() in ('1', 'true', 'yes', 'y')
    except Exception:
        return False

