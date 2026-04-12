# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class TendeAIResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # ── AI Provider Selection ──────────────────────────────────────────────────
    ai_provider = fields.Selection(
        selection=[
            ('gemini', 'Google Gemini'),
            ('mistral', 'Mistral AI'),
            ('azure', 'Microsoft Azure Cloud Foundry'),
            ('openai', 'OpenAI GPT'),
        ],
        string='AI Provider',
        config_parameter='tender_ai.ai_provider',
        default='gemini',
        help='Select the AI cloud provider to use for all AI operations.',
    )

    # ── API Key ────────────────────────────────────────────────────────────────
    tender_ai_api_key = fields.Char(
        string='Gemini API Key',
        config_parameter='tender_ai.api_key',
        help='Your Google Gemini API key. Get one at https://aistudio.google.com/app/apikey',
    )

    # ── Model selection ────────────────────────────────────────────────────────
    tender_ai_default_model = fields.Selection(
        selection='_get_model_selection',
        string='Default AI Model',
        config_parameter='tender_ai.default_model',
        help='The Gemini model to use for all AI operations. Click "Fetch Models" to load available options.',
    )

    def _get_model_selection(self):
        """Returns the list of available models from the system parameter."""
        models_str = self.env['ir.config_parameter'].sudo().get_param('tender_ai.available_models_cache', '')
        if models_str:
            names = models_str.split('\n')
            return [(n, n) for n in names if n.strip()]
        
        # Default safety list if none are cached yet
        return [
            ('gemini-2.0-flash', 'Gemini 2.0 Flash (Fastest & Best)'),
            ('gemini-1.5-flash', 'Gemini 1.5 Flash (Stable)'),
            ('gemini-1.5-pro', 'Gemini 1.5 Pro (Most Capable)'),
            ('gemini-2.0-pro-exp-02-05', 'Gemini 2.0 Pro Exp'),
        ]

    # Available model names (stored as newline-separated value for the selection)
    tender_ai_available_models_json = fields.Char(
        string='Available Models (cache)',
        config_parameter='tender_ai.available_models_cache',
    )

    # ── Cost / Pricing ─────────────────────────────────────────────────────────
    tender_ai_input_cost = fields.Float(
        string='Input Cost (per 1M tokens)',
        config_parameter='tender_ai.input_cost',
        default=12.5,
        help='Cost per 1M input tokens (INR) used for usage/cost calculations.',
    )
    tender_ai_output_cost = fields.Float(
        string='Output Cost (per 1M tokens)',
        config_parameter='tender_ai.output_cost',
        default=50.0,
        help='Cost per 1M output tokens (INR) used for usage/cost calculations.',
    )


    # ── Folder Explorer ────────────────────────────────────────────────────────
    purple_ai_root_path = fields.Char(
        string='Root Folder Path',
        config_parameter='purple_ai.root_path',
        help='The root directory for the Purple AI Folder Explorer.',
    )

    # ── Computed: available models as selection list ───────────────────────────
    tender_ai_model_choices = fields.Text(
        string='Available Models',
        compute='_compute_model_choices',
    )

    @api.depends('tender_ai_available_models_json')
    def _compute_model_choices(self):
        for rec in self:
            rec.tender_ai_model_choices = rec.tender_ai_available_models_json or ''

    # ── Actions ────────────────────────────────────────────────────────────────
    def action_fetch_available_models(self):
        """Hit the Gemini API with the configured key and populate available models."""
        self.ensure_one()

        api_key = self.tender_ai_api_key
        if not api_key:
            # Try config file / env
            from ..services.gemini_service import get_gemini_api_key
            try:
                api_key = get_gemini_api_key(env=self.env)
            except Exception:
                pass

        if not api_key:
            raise UserError(_(
                'Please enter your Gemini API Key first before fetching models.'
            ))

        try:
            from google import genai
            client = genai.Client(api_key=api_key)
            models_list = list(client.models.list())
        except Exception as e:
            raise UserError(_('Failed to fetch models: %s') % str(e))

        # Filter to models that support generateContent and are standard Gemini models
        candidates = []
        for m in models_list:
            name = getattr(m, 'name', '') or ''
            clean_name = name.replace('models/', '') if name.startswith('models/') else name
            
            # Relaxed filtering for Gemini 3/3.1 and Previews
            if not clean_name.startswith('gemini-') and not clean_name.startswith('gemma-'):
                continue
            if any(x in clean_name for x in ('vision', 'bison', 'embedding', 'aqa', 'search', 'tuned')):
                continue
            
            supported = getattr(m, 'supported_actions', None) or getattr(m, 'supportedGenerationMethods', None) or []
            if 'generateContent' in str(supported):
                candidates.append(clean_name)

        candidates.sort()
        
        # Validation: Verify which models actually respond to a minimal call
        # We test the top plausible ones (Flash and Pro 1.5/2.0) to avoid spamming the API
        verified_models = []
        _logger.info("Purple AI: Starting verification for %d candidate models", len(candidates))
        
        # Prioritize 1.5 models as they are currently the most stable across all API key types
        priority_models = [m for m in candidates if '1.5' in m]
        other_models = [m for m in candidates if '1.5' not in m]
        check_list = priority_models + other_models

        for model_name in check_list[:12]: # Limit to top 12 to save time/rate limits
            try:
                # Minimal test call (1 token output)
                client.models.generate_content(
                    model=model_name,
                    contents="Hi",
                    config={'max_output_tokens': 1}
                )
                verified_models.append(model_name)
                _logger.info("Purple AI: Model %s verified", model_name)
            except Exception as e:
                _logger.warning("Purple AI: Model %s rejected (failed check): %s", model_name, str(e))

        if not verified_models:
            # Fallback: if verification failed for all (maybe temporary network?), keep the candidates but log it
            _logger.error("Purple AI: All model verifications failed! Falling back to unverified list.")
            verified_models = candidates[:15]

        verified_models.sort()
        models_str = '\n'.join(verified_models)
        
        self.env['ir.config_parameter'].sudo().set_param(
            'tender_ai.available_models_cache', models_str
        )

        # Auto-select default if currently empty or invalid
        current_model = self.env['ir.config_parameter'].sudo().get_param(
            'tender_ai.default_model', ''
        )
        if not current_model or current_model not in verified_models:
            # Pick best default: prefer gemini-1.5-flash or 2.0-flash
            preferred = [m for m in verified_models if 'flash' in m]
            best = preferred[0] if preferred else (verified_models[0] if verified_models else '')
            if best:
                self.env['ir.config_parameter'].sudo().set_param(
                    'tender_ai.default_model', best
                )

        # Invalidate cache in gemini_service
        try:
            from ..services.gemini_service import _invalidate_model_cache
            _invalidate_model_cache()
        except Exception:
            pass

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('✅ Models Loaded'),
                'message': _(
                    '%d models available for your API key. '
                    'Select your preferred model from the dropdown.'
                ) % len(verified_models),
                'type': 'success',
                'sticky': False,
            },
        }

    def action_test_model(self):
        """Send a simple test prompt to verify the model works."""
        self.ensure_one()
        model = self.tender_ai_default_model or 'gemini-2.0-flash'
        try:
            from ..services.gemini_service import generate_with_gemini
            result = generate_with_gemini(
                contents='Say "Purple AI connected!" in one sentence.',
                model=model,
                env=self.env,
                )
            text = result.get('text', '').strip() if isinstance(result, dict) else str(result)
            usage = result.get('usage', {}) if isinstance(result, dict) else {}
            msg = f'Model: {model}\nResponse: {text}\nTokens used: {usage.get("totalTokens", "?")}'
        except Exception as e:
            raise UserError(_('Model test failed: %s') % str(e))

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('✅ Model Test Successful'),
                'message': msg,
                'type': 'success',
                'sticky': True,
            },
        }

    # ── Mistral AI ─────────────────────────────────────────────────────────────
    mistral_api_key = fields.Char(
        string='Mistral API Key',
        config_parameter='tender_ai.mistral_api_key',
        help='Your Mistral AI API key. Get one at https://console.mistral.ai/',
    )
    mistral_default_model = fields.Selection(
        selection=[
            ('mistral-large-latest', 'Mistral Large (Latest)'),
            ('mistral-medium-latest', 'Mistral Medium (Latest)'),
            ('mistral-small-latest', 'Mistral Small (Latest)'),
            ('open-mistral-7b', 'Open Mistral 7B'),
            ('open-mixtral-8x7b', 'Open Mixtral 8x7B'),
            ('open-mixtral-8x22b', 'Open Mixtral 8x22B'),
            ('codestral-latest', 'Codestral (Latest)'),
        ],
        string='Default Mistral Model',
        config_parameter='tender_ai.mistral_default_model',
        default='mistral-large-latest',
        help='The Mistral model to use for AI operations.',
    )
    mistral_ocr_url = fields.Char(
        string='Mistral OCR URL',
        config_parameter='tender_ai.mistral_ocr_url',
        default='https://api.mistral.ai/v1/ocr',
        help='The URL for the Mistral OCR API. Default is https://api.mistral.ai/v1/ocr',
    )

    def action_test_mistral_connection(self):
        """Send a simple test prompt to verify the Mistral API key and model."""
        self.ensure_one()
        api_key = self.mistral_api_key
        if not api_key:
            raise UserError(_('Please enter your Mistral API Key first.'))
        model = self.mistral_default_model or 'mistral-large-latest'
        try:
            import requests
            response = requests.post(
                'https://api.mistral.ai/v1/chat/completions',
                headers={
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': 'application/json',
                },
                json={
                    'model': model,
                    'messages': [{'role': 'user', 'content': 'Say "Purple AI connected via Mistral!" in one sentence.'}],
                    'max_tokens': 30,
                },
                timeout=15,
            )
            if response.status_code == 200:
                data = response.json()
                text = data['choices'][0]['message']['content'].strip()
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('✅ Mistral Connection Successful'),
                        'message': _('Model: %s\nResponse: %s') % (model, text),
                        'type': 'success',
                        'sticky': True,
                    },
                }
            else:
                raise UserError(_('Mistral API returned error %s: %s') % (response.status_code, response.text))
        except Exception as e:
            raise UserError(_('Mistral connection test failed: %s') % str(e))

    # ── Microsoft Azure Cloud Foundry ──────────────────────────────────────────
    azure_endpoint = fields.Char(
        string='Azure Endpoint URL',
        config_parameter='tender_ai.azure_endpoint',
        help='Your Azure Cloud Foundry endpoint URL, e.g. https://<resource>.openai.azure.com/',
    )
    azure_api_key = fields.Char(
        string='Azure API Key',
        config_parameter='tender_ai.azure_api_key',
        help='Your Microsoft Azure Cloud Foundry API key.',
    )
    azure_deployment_name = fields.Char(
        string='Deployment / Model Name',
        config_parameter='tender_ai.azure_deployment_name',
        help='The name of the Azure AI model deployment (e.g. gpt-4o, phi-3-mini, etc.).',
    )
    azure_api_version = fields.Selection(
        selection=[
            ('2024-12-01-preview', '2024-12-01-preview'),
            ('2024-10-01-preview', '2024-10-01-preview'),
            ('2024-08-01-preview', '2024-08-01-preview'),
            ('2024-05-01-preview', '2024-05-01-preview'),
        ],
        string='API Version',
        config_parameter='tender_ai.azure_api_version',
        default='2024-12-01-preview',
        help='The Azure OpenAI REST API version to use.',
    )

    def action_test_azure_connection(self):
        """Send a test prompt to verify the Azure Cloud Foundry credentials."""
        self.ensure_one()
        endpoint = (self.azure_endpoint or '').strip().rstrip('/')
        api_key = self.azure_api_key
        deployment = self.azure_deployment_name
        api_version = self.azure_api_version or '2024-12-01-preview'
        if not endpoint:
            raise UserError(_('Please enter your Azure Endpoint URL.'))
        if not api_key:
            raise UserError(_('Please enter your Azure API Key.'))
        if not deployment:
            raise UserError(_('Please enter the Deployment / Model Name.'))
        url = f"{endpoint}/openai/deployments/{deployment}/chat/completions?api-version={api_version}"
        try:
            import requests
            response = requests.post(
                url,
                headers={
                    'api-key': api_key,
                    'Content-Type': 'application/json',
                },
                json={
                    'messages': [{'role': 'user', 'content': 'Say "Purple AI connected via Azure!" in one sentence.'}],
                    'max_completion_tokens': 30,
                },
                timeout=15,
            )
            if response.status_code == 200:
                data = response.json()
                text = data['choices'][0]['message']['content'].strip()
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('✅ Azure Connection Successful'),
                        'message': _('Deployment: %s\nResponse: %s') % (deployment, text),
                        'type': 'success',
                        'sticky': True,
                    },
                }
            else:
                raise UserError(_('Azure API returned error %s: %s') % (response.status_code, response.text))
        except Exception as e:
            raise UserError(_('Azure connection test failed: %s') % str(e))

    # ── OpenAI GPT ─────────────────────────────────────────────────────────────
    openai_api_key = fields.Char(
        string='OpenAI API Key',
        config_parameter='tender_ai.openai_api_key',
        help='Your OpenAI API key. Get one at https://platform.openai.com/api-keys',
    )
    openai_default_model = fields.Selection(
        selection=[
            ('gpt-4o', 'GPT-4o (Most Capable)'),
            ('gpt-4o-mini', 'GPT-4o Mini (Fast & Affordable)'),
            ('gpt-4-turbo', 'GPT-4 Turbo'),
            ('gpt-4', 'GPT-4'),
            ('gpt-3.5-turbo', 'GPT-3.5 Turbo (Fastest)'),
        ],
        string='Default OpenAI Model',
        config_parameter='tender_ai.openai_default_model',
        default='gpt-4o-mini',
        help='The OpenAI GPT model to use for AI operations.',
    )

    def action_test_openai_connection(self):
        """Send a test prompt to verify the OpenAI API key and model."""
        self.ensure_one()
        api_key = self.openai_api_key
        if not api_key:
            raise UserError(_('Please enter your OpenAI API Key first.'))
        model = self.openai_default_model or 'gpt-4o-mini'
        try:
            import requests
            response = requests.post(
                'https://api.openai.com/v1/chat/completions',
                headers={
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': 'application/json',
                },
                json={
                    'model': model,
                    'messages': [{'role': 'user', 'content': 'Say "Purple AI connected via OpenAI!" in one sentence.'}],
                    'max_completion_tokens': 30,
                },
                timeout=15,
            )
            if response.status_code == 200:
                data = response.json()
                text = data['choices'][0]['message']['content'].strip()
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('✅ OpenAI Connection Successful'),
                        'message': _('Model: %s\nResponse: %s') % (model, text),
                        'type': 'success',
                        'sticky': True,
                    },
                }
            else:
                raise UserError(_('OpenAI API returned error %s: %s') % (response.status_code, response.text))
        except Exception as e:
            raise UserError(_('OpenAI connection test failed: %s') % str(e))

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
