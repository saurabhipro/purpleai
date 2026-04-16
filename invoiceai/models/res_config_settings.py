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
