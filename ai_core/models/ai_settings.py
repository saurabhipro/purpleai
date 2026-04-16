# -*- coding: utf-8 -*-
from odoo import fields, models

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # OCR Engine Selection
    ocr_engine = fields.Selection([
        ('tesseract', 'Tesseract OCR'),
        ('paddle', 'Paddle OCR'),
        ('mistral', 'Mistral OCR'),
    ], string='OCR Engine', default='tesseract', config_parameter='ai_core.ocr_engine')

    # Paddle OCR Settings
    paddle_ocr_use_gpu = fields.Boolean(config_parameter='ai_core.paddle_ocr_use_gpu', default=False)
    paddle_ocr_enable_angle = fields.Boolean(config_parameter='ai_core.paddle_ocr_enable_angle', default=True)
    paddle_ocr_model_dir = fields.Char(config_parameter='ai_core.paddle_ocr_model_dir', default='~/.paddleocr')
    paddle_ocr_num_threads = fields.Integer(config_parameter='ai_core.paddle_ocr_num_threads', default=4)
    paddle_ocr_cls_batch_num = fields.Integer(config_parameter='ai_core.paddle_ocr_cls_batch_num', default=30)
    paddle_ocr_det_db_thresh = fields.Float(config_parameter='ai_core.paddle_ocr_det_db_thresh', default=0.3)

    # Mistral OCR Settings
    mistral_ocr_url = fields.Char(string='Mistral OCR API URL', config_parameter='ai_core.mistral_ocr_url', default='')
    mistral_ocr_token = fields.Char(string='Mistral OCR Token', config_parameter='ai_core.mistral_ocr_token', default='')
    mistral_ocr_model = fields.Char(string='Mistral OCR Model', config_parameter='ai_core.mistral_ocr_model', default='mistral-document-ai-2505')

    # Common OCR Settings
    ocr_dpi = fields.Integer(config_parameter='ai_core.ocr_dpi', default=200)
    ocr_languages = fields.Char(config_parameter='ai_core.ocr_languages', default='hin+eng')
    ocr_timeout_per_page = fields.Integer(config_parameter='ai_core.ocr_timeout_per_page', default=30) 
    ocr_timeout_total = fields.Integer(config_parameter='ai_core.ocr_timeout_total', default=300)      
    ocr_preprocess_denoise = fields.Boolean(config_parameter='ai_core.ocr_preprocess_denoise', default=False)
    ocr_preprocess_deskew = fields.Boolean(config_parameter='ai_core.ocr_preprocess_deskew', default=False)
    ocr_preprocess_contrast = fields.Boolean(config_parameter='ai_core.ocr_preprocess_contrast', default=False)
    ocr_preprocess_threshold = fields.Boolean(config_parameter='ai_core.ocr_preprocess_threshold', default=False)
    ocr_image_mode = fields.Selection([('RGB', 'RGB'), ('L', 'Grayscale')], config_parameter='ai_core.ocr_image_mode', default='RGB')
    ocr_psm_mode = fields.Integer(config_parameter='ai_core.ocr_psm_mode', default=3)
    ocr_oem_mode = fields.Integer(config_parameter='ai_core.ocr_oem_mode', default=3)
    ocr_max_memory_mb = fields.Integer(config_parameter='ai_core.ocr_max_memory_mb', default=1024)     
    ocr_concurrent_jobs = fields.Integer(config_parameter='ai_core.ocr_concurrent_jobs', default=2)    
    ocr_render_scale_factor = fields.Float(config_parameter='ai_core.ocr_render_scale_factor', default=2.78)
    ocr_check_searchability = fields.Boolean(config_parameter='ai_core.ocr_check_searchability', default=True)
    ocr_searchability_threshold = fields.Integer(config_parameter='ai_core.ocr_searchability_threshold', default=100)
    ocr_enable_box_refinement = fields.Boolean(config_parameter='ai_core.ocr_enable_box_refinement', default=True)
    ocr_box_refinement_threshold = fields.Float(config_parameter='ai_core.ocr_box_refinement_threshold', default=0.7)
    ocr_enable_ocr_fallback = fields.Boolean(config_parameter='ai_core.ocr_enable_ocr_fallback', default=True)
    ocr_retry_on_error = fields.Boolean(config_parameter='ai_core.ocr_retry_on_error', default=True)   
    ocr_enable_debug_logging = fields.Boolean(config_parameter='ai_core.ocr_enable_debug_logging', default=False)
    ocr_save_debug_images = fields.Boolean(config_parameter='ai_core.ocr_save_debug_images', default=False)

    # AI Provider Settings
    provider = fields.Selection([
        ('openai', 'OpenAI'),
        ('gemini', 'Google Gemini'),
        ('azure', 'Azure OpenAI'),
    ], string='AI Core Provider', default='openai', config_parameter='ai_core.ai_provider')
    openai_key = fields.Char(config_parameter='ai_core.openai_api_key')
    openai_model = fields.Char(default='gpt-4o', config_parameter='ai_core.openai_model')
    gemini_key = fields.Char(config_parameter='ai_core.gemini_api_key')
    gemini_model = fields.Char(default='gemini-2.5-flash', config_parameter='ai_core.gemini_model')    
    azure_key = fields.Char(config_parameter='ai_core.azure_api_key')
    azure_endpoint = fields.Char(config_parameter='ai_core.azure_endpoint')
    azure_deployment = fields.Char(config_parameter='ai_core.azure_deployment')
    azure_embedding_deployment = fields.Char(default='text-embedding-3-small', config_parameter='ai_core.azure_embedding_deployment')
    azure_embedding_endpoint = fields.Char(config_parameter='ai_core.azure_embedding_endpoint')        
    azure_embedding_key = fields.Char(config_parameter='ai_core.azure_embedding_api_key')
    azure_api_version = fields.Char(default='2024-12-01-preview', config_parameter='ai_core.azure_api_version')
    use_local_embeddings = fields.Boolean(config_parameter='ai_core.use_local_embeddings')
    local_embedding_model = fields.Char(default='sentence-transformers/all-MiniLM-L6-v2', config_parameter='ai_core.local_embedding_model')
    temperature = fields.Float(default=0.3, config_parameter='ai_core.temperature')
    max_tokens = fields.Integer(default=4096, config_parameter='ai_core.max_tokens')
    react_dev_api_key = fields.Char(config_parameter='ai_core.react_dev_api_key')
    react_cors_origins = fields.Char(default='http://localhost:5173', config_parameter='ai_core.react_cors_origins')
    purple_ai_root_path = fields.Char(config_parameter='purple_ai.root_path')
    tally_url = fields.Char(config_parameter='tender_ai.tally_url')
    tally_port = fields.Char(config_parameter='tender_ai.tally_port')
    tally_company = fields.Char(config_parameter='tender_ai.tally_company')

    def action_test_ai_connection(self):
        return True
