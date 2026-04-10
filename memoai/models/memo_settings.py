# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class MemoAIResConfigSettings(models.TransientModel):
    """
    Memo AI own settings — fully independent of purpleai.
    All AI provider credentials stored under 'memo_ai.*' config parameters.
    """
    _inherit = 'res.config.settings'

    # ── AI Provider Selection ──────────────────────────────────────────────────
    memo_ai_provider = fields.Selection(
        selection=[
            ('openai', 'OpenAI GPT'),
            ('gemini', 'Google Gemini'),
            ('azure', 'Microsoft Azure OpenAI'),
        ],
        string='AI Provider',
        config_parameter='memo_ai.ai_provider',
        default='openai',
        help='Select the AI provider to use for all Memo AI operations.',
    )

    # ── OpenAI ─────────────────────────────────────────────────────────────────
    memo_ai_openai_api_key = fields.Char(
        string='OpenAI API Key',
        config_parameter='memo_ai.openai_api_key',
        help='Your OpenAI API key. Get one at https://platform.openai.com/api-keys',
    )
    memo_ai_openai_model = fields.Selection(
        selection=[
            ('gpt-4o', 'GPT-4o (Most Capable)'),
            ('gpt-4o-mini', 'GPT-4o Mini (Fast & Affordable)'),
            ('gpt-4-turbo', 'GPT-4 Turbo'),
            ('gpt-4', 'GPT-4'),
            ('gpt-3.5-turbo', 'GPT-3.5 Turbo'),
        ],
        string='OpenAI Model',
        config_parameter='memo_ai.openai_model',
        default='gpt-4o',
        help='The OpenAI GPT model to use for Memo AI analysis.',
    )

    # ── Google Gemini ──────────────────────────────────────────────────────────
    memo_ai_gemini_api_key = fields.Char(
        string='Gemini API Key',
        config_parameter='memo_ai.gemini_api_key',
        help='Your Google Gemini API key. Get one at https://aistudio.google.com/app/apikey',
    )
    memo_ai_gemini_model = fields.Selection(
        selection=[
            ('gemini-2.5-flash', 'Gemini 2.5 Flash (Fastest)'),
            ('gemini-2.5-pro', 'Gemini 2.5 Pro (Most Capable)'),
            ('gemini-2.5-flash-lite', 'Gemini 2.5 Flash Lite'),
            ('gemini-2.0-flash', 'Gemini 2.0 Flash (Fastest)'),
            ('gemini-1.5-flash', 'Gemini 1.5 Flash (legacy)'),
            ('gemini-1.5-pro', 'Gemini 1.5 Pro (legacy)'),
            ('gemini-2.0-pro-exp-02-05', 'Gemini 2.0 Pro Exp (legacy)'),
        ],
        string='Gemini Model',
        config_parameter='memo_ai.gemini_model',
        default='gemini-2.5-flash',
        help='The Gemini model to use for Memo AI analysis.',
    )

    # ── Azure OpenAI ───────────────────────────────────────────────────────────
    memo_ai_azure_endpoint = fields.Char(
        string='Azure Endpoint URL',
        config_parameter='memo_ai.azure_endpoint',
        help='Your Azure OpenAI endpoint, e.g. https://<resource>.openai.azure.com/',
    )
    memo_ai_azure_api_key = fields.Char(
        string='Azure API Key',
        config_parameter='memo_ai.azure_api_key',
        help='Your Microsoft Azure OpenAI API key.',
    )
    memo_ai_azure_deployment = fields.Char(
        string='Azure Deployment Name',
        config_parameter='memo_ai.azure_deployment',
        help='The Azure AI model deployment name (e.g. gpt-4o, gpt-35-turbo).',
    )
    memo_ai_azure_embedding_deployment = fields.Char(
        string='Azure Embedding Deployment',
        config_parameter='memo_ai.azure_embedding_deployment',
        default='text-embedding-3-small',
        help='Azure deployment name for embeddings (must be an embedding model deployment).',
    )
    memo_ai_use_local_embeddings = fields.Boolean(
        string='Use Local Embeddings',
        config_parameter='memo_ai.use_local_embeddings',
        default=False,
        help='If enabled, RAG embeddings are generated locally (SentenceTransformers) instead of cloud embedding APIs.',
    )
    memo_ai_local_embedding_model = fields.Char(
        string='Local Embedding Model',
        config_parameter='memo_ai.local_embedding_model',
        default='sentence-transformers/all-MiniLM-L6-v2',
        help='HuggingFace model id for local embeddings.',
    )
    memo_ai_azure_api_version = fields.Selection(
        selection=[
            ('2024-12-01-preview', '2024-12-01-preview'),
            ('2024-10-01-preview', '2024-10-01-preview'),
            ('2024-08-01-preview', '2024-08-01-preview'),
            ('2024-05-01-preview', '2024-05-01-preview'),
            ('2024-02-01', '2024-02-01'),
        ],
        string='Azure API Version',
        config_parameter='memo_ai.azure_api_version',
        default='2024-12-01-preview',
    )

    # ── Advanced Config (Constants) ────────────────────────────────────────────
    memo_ai_temperature = fields.Float(
        string='Temperature',
        config_parameter='memo_ai.temperature',
        default=0.3,
        help="AI sampling temperature (e.g., 0.3 for focused extraction).",
    )
    memo_ai_max_tokens = fields.Integer(
        string='Max Context / Completion Tokens',
        config_parameter='memo_ai.max_tokens',
        default=4096,
    )
    memo_ai_prompt_cost = fields.Float(
        string='Prompt Cost per 1M (INR)',
        config_parameter='memo_ai.prompt_cost',
        digits=(10, 4),
        default=12.5,
        help="Used to compute execution cost. Default is approx 12.5 INR (GPT-4o-Mini).",
    )
    memo_ai_completion_cost = fields.Float(
        string='Completion Cost per 1M (INR)',
        config_parameter='memo_ai.completion_cost',
        digits=(10, 4),
        default=50.0,
        help="Used to compute execution cost. Default is approx 50.0 INR (GPT-4o-Mini).",
    )


    # ── Test Connection Actions ─────────────────────────────────────────────────
    def action_test_memo_openai(self):
        self.ensure_one()
        api_key = self.memo_ai_openai_api_key
        if not api_key:
            raise UserError(_('Please enter your OpenAI API Key first.'))
        model = self.memo_ai_openai_model or 'gpt-4o'
        try:
            import requests
            response = requests.post(
                'https://api.openai.com/v1/chat/completions',
                headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
                json={
                    'model': model,
                    'messages': [{'role': 'user', 'content': 'Say "Memo AI connected!" in one sentence.'}],
                    'max_completion_tokens': 20,
                },
                timeout=15,
            )
            if response.status_code == 200:
                text = response.json()['choices'][0]['message']['content'].strip()
                return self._notify_success(_('OpenAI Connected'), f'Model: {model}\n{text}')
            raise UserError(_('OpenAI returned %s: %s') % (response.status_code, response.text))
        except UserError:
            raise
        except Exception as e:
            raise UserError(_('OpenAI test failed: %s') % str(e))

    def action_test_memo_gemini(self):
        self.ensure_one()
        api_key = self.memo_ai_gemini_api_key
        if not api_key:
            raise UserError(_('Please enter your Gemini API Key first.'))
        try:
            import requests
            model_name = (self.memo_ai_gemini_model or 'gemini-2.5-flash').strip()
            clean_model = model_name if not model_name.startswith('models/') else model_name.replace('models/', '')
            
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{clean_model}:generateContent?key={api_key.strip()}"
            data = {
                "contents": [{"parts": [{"text": 'Say "Memo AI connected!" in one sentence.'}]}],
                "generationConfig": {"temperature": 0.1}
            }
            response = requests.post(url, headers={'Content-Type': 'application/json'}, json=data, timeout=15)
            
            if response.status_code == 200:
                answer = response.json().get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', '')
                return self._notify_success(_('Gemini Connected'), f'Model: {clean_model}\n{answer.strip()}')
            else:
                raise UserError(_('API Error %s: %s') % (response.status_code, response.text))
        except UserError:
            raise
        except Exception as e:
            raise UserError(_('Gemini test failed: %s') % str(e))

    def action_test_memo_azure(self):
        self.ensure_one()
        endpoint = (self.memo_ai_azure_endpoint or '').strip().rstrip('/')
        api_key = self.memo_ai_azure_api_key
        deployment = self.memo_ai_azure_deployment
        api_version = self.memo_ai_azure_api_version or '2024-12-01-preview'
        if not endpoint or not api_key or not deployment:
            raise UserError(_('Please fill in Endpoint, API Key, and Deployment Name.'))
        url = f"{endpoint}/openai/deployments/{deployment}/chat/completions?api-version={api_version}"
        try:
            import requests
            response = requests.post(
                url,
                headers={'api-key': api_key, 'Content-Type': 'application/json'},
                json={
                    'messages': [{'role': 'user', 'content': 'Say "Memo AI connected!" in one sentence.'}],
                    'max_completion_tokens': 20,
                },
                timeout=15,
            )
            if response.status_code == 200:
                text = response.json()['choices'][0]['message']['content'].strip()
                return self._notify_success(_('Azure Connected'), f'Deployment: {deployment}\n{text}')
            raise UserError(_('Azure returned %s: %s') % (response.status_code, response.text))
        except UserError:
            raise
        except Exception as e:
            raise UserError(_('Azure test failed: %s') % str(e))

    def _notify_success(self, title, message):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'title': f'✅ {title}', 'message': message, 'type': 'success', 'sticky': True},
        }
