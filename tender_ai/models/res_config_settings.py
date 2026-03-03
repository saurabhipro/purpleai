# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class TendeAIResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

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
            ('gemini-2.5-flash-preview-04-17', 'gemini-2.5-flash-preview-04-17'),
            ('gemini-2.0-flash', 'gemini-2.0-flash'),
            ('gemini-1.5-flash', 'gemini-1.5-flash'),
            ('gemini-1.5-pro', 'gemini-1.5-pro'),
        ]

    # Available model names (stored as newline-separated value for the selection)
    tender_ai_available_models_json = fields.Char(
        string='Available Models (cache)',
        config_parameter='tender_ai.available_models_cache',
    )

    # ── Cost / Pricing ─────────────────────────────────────────────────────────
    tender_ai_input_cost = fields.Float(
        string='Input Cost (₹ per 1M tokens)',
        config_parameter='tender_ai.cost_per_million_input_tokens_inr',
        digits=(10, 4),
        help='Cost per 1 million INPUT (prompt) tokens in Indian Rupees.',
    )
    tender_ai_output_cost = fields.Float(
        string='Output Cost (₹ per 1M tokens)',
        config_parameter='tender_ai.cost_per_million_output_tokens_inr',
        digits=(10, 4),
        help='Cost per 1 million OUTPUT tokens in Indian Rupees.',
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
            
            # Strict filtering: Only standard Gemini models, exclude experimental/vision-only/tuned/legacy
            if not clean_name.startswith('gemini-'):
                continue
            if any(x in clean_name for x in ('-exp', 'vision', 'bison', 'embedding', 'aqa', 'search', 'tuned')):
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
        model = self.tender_ai_default_model or 'gemini-2.5-flash-preview-04-17'
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
