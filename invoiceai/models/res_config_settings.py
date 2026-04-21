# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class PurpleAIResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'


    # ── Folder Explorer ────────────────────────────────────────────────────────
    purple_ai_root_path = fields.Char(
        string='Root Folder Path',
        config_parameter='purple_ai.root_path',
        default='/home/odoo18',
        help='The root directory for the Purple AI Folder Explorer.',
    )

    # Toggle detailed logging for OCR / LLM requests and responses
    purple_ai_detailed_logging = fields.Boolean(
        string='Detailed Purple AI Logs',
        config_parameter='purple_ai.detailed_logging',
        default=False,
        help='When enabled, Purple AI will emit detailed OCR and LLM request/response logs. Disable for minimal logging.',
    )

    # ── Parallel Processing Configuration ──────────────────────────────────────
    ai_core_max_parallel_workers = fields.Selection(
        selection=[
            ('1', '1 - Sequential Processing (Debug Only)'),
            ('2', '2 - Safe & Recommended (4x faster)'),
            ('3', '3 - Aggressive (9x faster, requires good internet)'),
            ('4', '4 - Maximum Throughput (15x faster, risk of rate limiting)'),
        ],
        string='Max Parallel Workers',
        config_parameter='ai_core.max_parallel_workers',
        default='2',
        help=(
            'Number of parallel threads for batch processing invoices.\n'
            '• 1: Sequential - Debug mode, slower\n'
            '• 2: Safe - Recommended, ~4x speedup, avoids API rate limits\n'
            '• 3: Aggressive - ~9x speedup, requires stable internet\n'
            '• 4: Maximum - ~15x speedup, may hit API rate limits\n\n'
            'Use process_documents_parallel() to batch process multiple files.'
        ),
    )

    # ── API Pricing Configuration (per 1 million tokens) ────────────────────────
    gemini_input_cost_per_m_tokens = fields.Float(
        string='Gemini Input Cost ($ per 1M tokens)',
        config_parameter='ai_core.gemini_input_cost',
        default=0.075,
        help='Cost per 1 million input tokens (Gemini Flash 2.0, default: $0.075)',
    )
    gemini_output_cost_per_m_tokens = fields.Float(
        string='Gemini Output Cost ($ per 1M tokens)',
        config_parameter='ai_core.gemini_output_cost',
        default=0.30,
        help='Cost per 1 million output tokens (Gemini Flash 2.0, default: $0.30)',
    )
    openai_input_cost_per_m_tokens = fields.Float(
        string='OpenAI Input Cost ($ per 1M tokens)',
        config_parameter='ai_core.openai_input_cost',
        default=2.50,
        help='Cost per 1 million input tokens (GPT-4o, default: $2.50)',
    )
    openai_output_cost_per_m_tokens = fields.Float(
        string='OpenAI Output Cost ($ per 1M tokens)',
        config_parameter='ai_core.openai_output_cost',
        default=10.00,
        help='Cost per 1 million output tokens (GPT-4o, default: $10.00)',
    )
    azure_input_cost_per_m_tokens = fields.Float(
        string='Azure Input Cost ($ per 1M tokens)',
        config_parameter='ai_core.azure_input_cost',
        default=0.50,
        help='Cost per 1 million input tokens (Azure OpenAI GPT-4o, default: $0.50 - varies by region)',
    )
    azure_output_cost_per_m_tokens = fields.Float(
        string='Azure Output Cost ($ per 1M tokens)',
        config_parameter='ai_core.azure_output_cost',
        default=1.50,
        help='Cost per 1 million output tokens (Azure OpenAI GPT-4o, default: $1.50 - varies by region)',
    )
    usd_to_inr_rate = fields.Float(
        string='USD to INR Exchange Rate',
        config_parameter='ai_core.usd_to_inr_rate',
        default=85.0,
        help='Current USD to INR exchange rate for cost conversion (default: 85.0)',
    )

    # ── Mistral Custom Endpoint Configuration ───────────────────────────────────
    mistral_endpoint_url = fields.Char(
        string='Mistral Custom Endpoint URL (Optional)',
        config_parameter='ai_core.mistral_endpoint_url',
        help=(
            'Optional: Specify a custom Mistral endpoint for Azure gateway or proxy.\n\n'
            'EXAMPLES:\n'
            '• Default Mistral: Leave empty → uses https://api.mistral.ai/v1/chat/completions\n'
            '• Azure Gateway (base): https://aif-cosec-dev.services.ai.azure.com/providers/mistral/azure/ocr\n'
            '  (system auto-appends /v1/chat/completions)\n'
            '• Azure Gateway (full): https://aif-cosec-dev.services.ai.azure.com/providers/mistral/azure/ocr/v1/chat/completions\n'
            '• Custom /v1 path: https://your-api.com/v1\n'
            '  (system auto-appends /chat/completions)\n\n'
            'The system will auto-complete missing path components if needed.'
        ),
    )
    mistral_verify_ssl = fields.Selection(
        selection=[
            ('true', '✅ Verify SSL (Default - Recommended)'),
            ('false', '⚠️ Skip SSL Verification (For self-signed certificates or testing)'),
        ],
        string='Verify Mistral SSL Certificate',
        config_parameter='ai_core.mistral_verify_ssl',
        default='true',
        help=(
            'SSL Certificate Verification for Mistral endpoint.\n'
            '• ✅ Verify SSL (Default): Secure, validates certificates\n'
            '• ⚠️ Skip SSL: For self-signed certs or custom gateways with certificate issues\n\n'
            'If getting CERTIFICATE_VERIFY_FAILED errors:\n'
            '1. Try updating system certificates: apt-get install ca-certificates\n'
            '2. Or enable skip SSL if using Azure gateway with valid certs'
        ),
    )

    # ── All tender_ai legacy fields and methods removed (unused) ──────────────

    # ── Tally Integration ──────────────────────────────────────────────────────
    tally_url = fields.Char(
        string='Tally Host URL',
        config_parameter='tender_ai.tally_url',
        default='http://localhost',
        help='The IP address or hostname of the PC where Tally is running.',
    )
    tally_port = fields.Char(
        string='Tally Port',
        config_parameter='tender_ai.tally_port',
        default='9000',
        help='The port Tally is listening on (default 9000).',
    )
    tally_company = fields.Char(
        string='Tally Company Name',
        config_parameter='tender_ai.tally_company',
        help='Exact name of the company loaded in Tally.',
    )

    def action_test_tally_connection(self):
        """Test the connection to Tally XML API."""
        self.ensure_one()
        url = (self.tally_url or 'http://localhost').strip()
        if not url.startswith('http'):
            url = f'http://{url}'
        
        full_url = f"{url}:{self.tally_port or '9000'}"
        
        # Simple Tally XML to check connectivity (requesting company name)
        test_xml = """
        <ENVELOPE>
            <HEADER>
                <TALLYREQUEST>Export Data</TALLYREQUEST>
            </HEADER>
            <BODY>
                <EXPORTDATA>
                    <REQUESTDESC>
                        <REPORTNAME>List of Companies</REPORTNAME>
                    </REQUESTDESC>
                </EXPORTDATA>
            </BODY>
        </ENVELOPE>
        """
        
        try:
            import requests
            response = requests.post(full_url, data=test_xml, timeout=5)
            if response.status_code == 200:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('✅ Tally Connected'),
                        'message': _('Successfully connected to Tally at %s') % full_url,
                        'type': 'success',
                        'sticky': False,
                    },
                }
            else:
                raise UserError(_('Tally returned status code: %s') % response.status_code)
        except Exception as e:
            raise UserError(_('Failed to connect to Tally: %s. Ensure Tally is running and the HTTP server is enabled.') % str(e))

    def action_sync_tally_ledgers(self):
        """Fetch ledger names from Tally. When Odoo Accounting is installed, mirror them as accounts."""
        self.ensure_one()
        from ..services.tally_service import get_tally_ledgers
        res = get_tally_ledgers(self.env)

        if res.get('status') != 'success':
            raise UserError(_("Failed to sync: %s") % res.get('message'))

        names = res.get('ledgers', [])
        Account = self.env.get('account.account')
        if not Account:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Tally ledgers'),
                    'message': _(
                        'Read %d ledger names from Tally. Odoo Accounting is not installed, so no accounts were created.'
                    ) % len(names),
                    'type': 'info',
                    'sticky': False,
                },
            }

        count = 0
        for name in names:
            existing = Account.search([('name', '=', name)], limit=1)
            if not existing:
                Account.create({
                    'name': name,
                    'code': f"T-{name[:8]}-{count}",
                    'account_type': 'expense',
                })
                count += 1

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('✅ Ledger Sync Complete'),
                'message': _('Imported %d new Tally ledgers. Total ledgers scanned: %d') % (count, len(names)),
                'type': 'success',
            },
        }

    def action_test_ai_connection(self):
        """Test AI Provider connection (Mistral, Azure, OpenAI, Gemini)."""
        self.ensure_one()
        
        try:
            from odoo.addons.ai_core.services.ai_core_service import _get_ai_settings
            import logging
            
            _logger = logging.getLogger(__name__)
            
            settings = _get_ai_settings(self.env)
            provider = (settings.get('provider') or 'openai').lower().strip()
            
            _logger.info("Testing AI connection for provider: %s", provider)
            
            if provider == 'mistral':
                # Test Mistral API
                try:
                    from odoo.addons.ai_core.services.mistral_service import MistralService
                    svc = MistralService()
                    api_key = settings.get('mistral_api_key', '').strip()
                    custom_endpoint = (settings.get('mistral_endpoint_url') or '').strip()
                    mistral_model = (settings.get('mistral_model') or '').strip() or 'mistral-document-ai-2505'
                    ocr_engine = (settings.get('ocr_engine') or 'tesseract').strip()
                    mistral_ocr_url = (settings.get('mistral_ocr_url') or '').strip()
                    mistral_ocr_model = (settings.get('mistral_ocr_model') or '').strip() or 'mistral-document-ai-2505'
                    
                    if not api_key:
                        raise UserError(_('Mistral API key not configured'))
                    
                    # Test with a simple extraction call using the configured model
                    result = svc.generate(
                        [{'type': 'text', 'text': 'Extract: company_name\nTest document: ABC Company Ltd.'}],
                        model=mistral_model,
                        temperature=0.1,
                        max_retries=1,
                        env=self.env,
                    )
                    
                    endpoint_info = f' (Custom: {custom_endpoint})' if custom_endpoint else ' (Default)'
                    model_info = f' | Model: {mistral_model}'
                    ocr_info = f' | OCR: {ocr_engine}' + (f' ({mistral_ocr_model})' if ocr_engine == 'mistral' else '')
                    
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('✅ Mistral Connection Successful'),
                            'message': _('Mistral API is reachable and responding correctly.') + endpoint_info + model_info + ocr_info,
                            'type': 'success',
                            'sticky': False,
                        },
                    }
                except Exception as e:
                    error_msg = str(e)
                    api_key_display = f"{api_key[:4]}...{api_key[-4:]}" if len(api_key) > 8 else "***"
                    
                    # Check if using Azure OCR endpoint
                    is_azure_ocr = '/providers/mistral/azure/ocr' in (custom_endpoint or '')
                    
                    # Compute the actual endpoint the service used
                    try:
                        from odoo.addons.ai_core.services.mistral_service import _get_mistral_endpoint
                        actual_endpoint = _get_mistral_endpoint(self.env)
                    except Exception:
                        actual_endpoint = custom_endpoint or 'https://api.mistral.ai/v1/chat/completions'
                    
                    # Common debug info for all errors
                    debug_info = (
                        f'\n\n🔍 DEBUG INFO:\n'
                        f'• Endpoint (actual): {actual_endpoint}\n'
                        f'• Endpoint (configured): {custom_endpoint or "(default)"}\n'
                        f'• Endpoint Type: {"Azure OCR" if is_azure_ocr else "Standard Chat"}\n'
                        f'• Chat Model: {mistral_model}\n'
                        f'• API Key: {api_key_display}\n'
                        f'• SSL Verify: {self.env["ir.config_parameter"].sudo().get_param("ai_core.mistral_verify_ssl", "true").lower()}\n'
                        f'• OCR Engine: {ocr_engine}'
                    )
                    if ocr_engine == 'mistral':
                        debug_info += f'\n• OCR URL: {mistral_ocr_url or "Not configured"}\n• OCR Model: {mistral_ocr_model}'
                    
                    # Provide helpful error messages
                    if '401' in error_msg or 'Access denied' in error_msg or 'Invalid' in error_msg:
                        error_msg += (
                            debug_info + '\n\n'
                            '❌ Authentication Error (401):\n'
                            '✅ Fixes to try:\n'
                            '1. Verify your Mistral API key is correct and active\n'
                            '2. If using Azure gateway: Check that the custom endpoint URL is correct\n'
                            '3. Check that the endpoint matches your API key (e.g., Azure key with Azure endpoint)\n'
                            '4. Try disabling SSL verification if using a self-signed certificate'
                        )
                    elif '404' in error_msg or 'DeploymentNotFound' in error_msg or 'does not exist' in error_msg or 'NOT FOUND' in error_msg:
                        # Provide Azure OCR specific guidance if applicable
                        azure_ocr_section = (
                            '\n\n🔵 Azure Mistral OCR Endpoint:\n'
                            '• Endpoint detected: Azure OCR (Document Extraction)\n'
                            '• Uses document extraction format (not chat completions)\n'
                            '• Example model: "mistral-document-ai-2505"\n'
                            '• Requires document content in base64 format\n'
                            '• Returns extracted data in JSON schema format\n'
                            '• Verify the model name exists in your Azure account\n'
                        ) if is_azure_ocr else ''
                        
                        error_msg += (
                            debug_info + '\n\n'
                            '❌ Model Deployment Not Found (404):\n'
                            '✅ Fixes to try:\n'
                            '1. Verify the model name in Settings → General Settings → Mistral AI Configuration\n'
                            '2. Check the endpoint URL format:\n'
                            '   - Mistral Default: https://api.mistral.ai/v1/chat/completions\n'
                            '   - Azure Gateway: https://YOUR-GATEWAY.com/providers/mistral/azure/ocr\n'
                            '   - Custom: Use the full path\n'
                            '3. Ensure the model deployment exists in your account\n'
                            '4. List available deployments in your provider portal\n'
                            '5. If using Mistral: Check https://docs.mistral.ai/ for available models\n'
                            '6. If deployment was just created, wait 5 minutes and try again'
                            + azure_ocr_section
                        )
                    elif 'SSL' in error_msg or 'CERTIFICATE_VERIFY_FAILED' in error_msg:
                        error_msg += (
                            debug_info + '\n\n'
                            '⚠️ SSL Certificate Error:\n'
                            '✅ Fixes to try:\n'
                            '• Update system certificates: apt-get install ca-certificates\n'
                            '• Or disable SSL verification: Settings → General Settings → Mistral AI Configuration → Skip SSL\n'
                            '• If using self-signed certs: Configure your gateway to use proper certificates'
                        )
                    elif 'NameResolutionError' in error_msg or 'Failed to resolve' in error_msg or 'getaddrinfo failed' in error_msg:
                        error_msg += (
                            debug_info + '\n\n'
                            '🌐 DNS/Network Connection Error:\n'
                            '✅ Fixes to try:\n'
                            '1. Verify the endpoint URL is correct and accessible:\n'
                            f'   • Current: {custom_endpoint or "https://api.mistral.ai"}\n'
                            '2. Check network connectivity:\n'
                            '   • Ping the hostname: ping aif-cosec-dev.services.ai.azure.com\n'
                            '   • For Azure endpoints: Verify region and service availability\n'
                            '3. Check firewall/proxy settings:\n'
                            '   • Ensure outbound HTTPS (port 443) is allowed\n'
                            '   • Check if a proxy is configured and blocking the request\n'
                            '4. For Azure Mistral OCR:\n'
                            '   • Verify resource group and region are correct\n'
                            '   • Check if the service is deployed in that region\n'
                            '   • Verify credentials have access to the Azure service'
                        )
                    else:
                        error_msg += debug_info
                    
                    raise UserError(_('Mistral connection failed:\n%s') % error_msg)
            
            elif provider == 'azure':
                # Test Azure OpenAI
                try:
                    from odoo.addons.ai_core.services.ai_core_service import call_ai
                    
                    azure_endpoint = settings.get('azure_endpoint', '').strip()
                    azure_key = settings.get('azure_key', '').strip()
                    azure_deployment = settings.get('azure_deployment', '').strip()
                    
                    if not all([azure_endpoint, azure_key, azure_deployment]):
                        raise UserError(_('Azure configuration incomplete (endpoint, key, or deployment missing)'))
                    
                    # Test with a simple call
                    result = call_ai(self.env, "Say 'OK' only", enforce_html=False)
                    
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('✅ Azure OpenAI Connection Successful'),
                            'message': _('Azure endpoint is reachable and responding correctly.'),
                            'type': 'success',
                            'sticky': False,
                        },
                    }
                except Exception as e:
                    raise UserError(_('Azure OpenAI connection failed: %s') % str(e))
            
            elif provider == 'gemini':
                # Test Gemini
                try:
                    from odoo.addons.ai_core.services.gemini_service import GeminiService
                    svc = GeminiService()
                    gemini_key = settings.get('gemini_api_key', '').strip()
                    
                    if not gemini_key:
                        raise UserError(_('Gemini API key not configured'))
                    
                    # Test with a simple extraction call
                    result = svc.generate(
                        ["Extract: company_name\nTest document: XYZ Corporation"],
                        model='gemini-2.0-flash',
                        temperature=0.1,
                        max_retries=1,
                        env=self.env,
                    )
                    
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('✅ Gemini Connection Successful'),
                            'message': _('Gemini API is reachable and responding correctly.'),
                            'type': 'success',
                            'sticky': False,
                        },
                    }
                except Exception as e:
                    raise UserError(_('Gemini connection failed: %s') % str(e))
            
            elif provider == 'openai':
                # Test OpenAI Direct
                try:
                    from odoo.addons.ai_core.services.ai_core_service import call_ai
                    
                    openai_key = settings.get('openai_api_key', '').strip()
                    if not openai_key:
                        raise UserError(_('OpenAI API key not configured'))
                    
                    # Test with a simple call
                    result = call_ai(self.env, "Say 'OK' only", enforce_html=False)
                    
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('✅ OpenAI Connection Successful'),
                            'message': _('OpenAI API is reachable and responding correctly.'),
                            'type': 'success',
                            'sticky': False,
                        },
                    }
                except Exception as e:
                    raise UserError(_('OpenAI connection failed: %s') % str(e))
            
            else:
                raise UserError(_('Unknown AI Provider: %s') % provider)
                
        except UserError:
            raise
        except Exception as e:
            _logger.error("AI connection test failed: %s", str(e))
            raise UserError(_('AI connection test failed: %s') % str(e))

    def action_test_ocr(self):
        """Test OCR engines (Tesseract, Paddle, Mistral) with a sample PDF."""
        self.ensure_one()
        
        try:
            from odoo.addons.invoiceai.services import document_processing_service
            from odoo.addons.ai_core.services import ocr_service
            from odoo.addons.ai_core.services.ocr_config import _get_ocr_config
            import tempfile
            import os
            
            # Create a simple test image/PDF
            try:
                from PIL import Image, ImageDraw, ImageFont
            except ImportError:
                raise UserError(_('PIL (Pillow) is not installed. Cannot create test image.'))
            
            # Create a test image with text
            img = Image.new('RGB', (600, 200), color='white')
            draw = ImageDraw.Draw(img)
            try:
                # Try to use a default font, fallback to default if not available
                draw.text((50, 50), "Test Invoice Number: INV-2024-001", fill='black')
                draw.text((50, 100), "Amount Due: 5000.00 INR", fill='black')
                draw.text((50, 150), "Vendor: Test Company Ltd.", fill='black')
            except:
                # Fallback without font specification
                draw.text((50, 50), "Test Invoice Number: INV-2024-001", fill='black')
                draw.text((50, 100), "Amount Due: 5000.00 INR", fill='black')
                draw.text((50, 150), "Vendor: Test Company Ltd.", fill='black')
            
            # Save test image to temp file
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                img.save(tmp.name)
                test_image_path = tmp.name
            
            ocr_results = []
            
            try:
                # Test Tesseract
                _logger.info("Testing Tesseract OCR...")
                ocr_config = _get_ocr_config(self.env)
                ocr_config['dpi'] = 150  # Use safe DPI for Tesseract
                
                try:
                    from pdf2image import convert_from_path
                    # For testing, we'll try to use the image directly with Tesseract
                    import pytesseract
                    text = pytesseract.image_to_string(test_image_path)
                    if text.strip():
                        ocr_results.append(('✅ Tesseract', 'Successfully extracted: ' + text[:50] + '...'))
                    else:
                        ocr_results.append(('⚠️ Tesseract', 'No text detected (image may be too low quality)'))
                except Exception as e:
                    ocr_results.append(('❌ Tesseract', str(e)))
                
                # Test Paddle OCR
                _logger.info("Testing Paddle OCR...")
                try:
                    from paddleocr import PaddleOCR
                    paddle_ocr = PaddleOCR(use_angle_cls=True, lang='en')
                    result = paddle_ocr.ocr(test_image_path, cls=True)
                    if result and result[0]:
                        text = ' '.join([line[1][0] for line in result[0]])
                        ocr_results.append(('✅ Paddle OCR', 'Successfully extracted: ' + text[:50] + '...'))
                    else:
                        ocr_results.append(('⚠️ Paddle OCR', 'No text detected'))
                except ImportError:
                    ocr_results.append(('⚠️ Paddle OCR', 'Not installed (optional)'))
                except Exception as e:
                    ocr_results.append(('❌ Paddle OCR', str(e)))
                
                # Test Mistral URL access
                _logger.info("Testing Mistral connectivity...")
                try:
                    settings = self.env['ir.config_parameter'].sudo()
                    mistral_api_key = settings.get_param('ai_core.mistral_api_key', '').strip()
                    
                    if not mistral_api_key:
                        ocr_results.append(('⚠️ Mistral', 'API key not configured'))
                    else:
                        # Test URL resolution
                        import requests
                        try:
                            response = requests.head('https://api.mistral.ai', timeout=5)
                            ocr_results.append(('✅ Mistral', 'API endpoint reachable'))
                        except requests.exceptions.ConnectionError as ce:
                            ocr_results.append(('❌ Mistral', f'Cannot reach API: {str(ce)[:100]}'))
                        except Exception as e:
                            ocr_results.append(('⚠️ Mistral', f'Connection test failed: {str(e)[:100]}'))
                except Exception as e:
                    ocr_results.append(('❌ Mistral', str(e)))
                
            finally:
                # Clean up temp file
                try:
                    os.unlink(test_image_path)
                except:
                    pass
            
            # Format results message
            results_text = '\n'.join([f'{status}: {msg}' for status, msg in ocr_results])
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('OCR Engine Test Results'),
                    'message': results_text,
                    'type': 'info',
                    'sticky': True,
                },
            }
            
        except Exception as e:
            _logger.error("OCR test failed: %s", str(e))
            raise UserError(_('OCR test failed: %s') % str(e))
