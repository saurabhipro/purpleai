from odoo import models, fields, _, api
from odoo.exceptions import ValidationError
from plaid.model.transactions_get_request import TransactionsGetRequest
from plaid.model.transactions_get_request_options import TransactionsGetRequestOptions
from datetime import datetime
import pandas as pd

class PlaidTransactionWizard(models.TransientModel):
    _name = 'plaid.transaction.wizard'
    _description = 'Plaid Transaction Wizard'

    journal_id = fields.Many2one('account.journal', string="Journal")
    plaid_id = fields.Many2one('online.sync.plaid')
    plaid_line_id = fields.Many2one('online.sync.plaid.lines')
    from_date = fields.Date(string='Date From')
    to_date = fields.Date(string='Date To')


    @api.onchange('journal_id', 'plaid_id')
    def onchange_method(self):
        return {
            'domain': {'plaid_id': [('bank_journal_id', '=', self.journal_id.id)],
                       'plaid_line_id': [('plaid_sync_id', '=', self.plaid_id.id)]}
        }

    def get_transactions_from_plaid(self):
        plaid_sync_rec = self.env['online.sync.plaid'].search([('bank_journal_id', '=', self.journal_id.id)])
        if not plaid_sync_rec:
            raise ValidationError(_('Please connect the bank journal to Plaid first!'))
        if plaid_sync_rec.state == 'unlinked':
            raise ValidationError(_('Your request for Plaid connection for this bank journal is not done yet!'))
        p_access_token = plaid_sync_rec.plaid_access_token
        client = self.env.company.plaid_client
        secret = self.env.company.plaid_secret
        client = self.env['online.sync.plaid'].get_plaid_client(client, secret)
        account_id = self.plaid_line_id.account_id
        create_request = TransactionsGetRequest(
            access_token=p_access_token,
            start_date=self.from_date,
            end_date=self.to_date,
            options=TransactionsGetRequestOptions(account_ids=[account_id], count=500)
        )
        tr_response = client.transactions_get(create_request)
        tr_df = pd.DataFrame([x.to_dict() for x in tr_response.get('transactions')])
        limited_df = tr_df[['amount', 'name', 'date']].copy()
        limited_df.columns = ['amount', 'payment_ref', 'date']
        # limited_df['date'] = limited_df['date'].apply(lambda x: datetime.strftime(x, '%Y-%m-%d'))
        statements_list = limited_df.to_dict('records')
        statements_list.reverse()
        for statement in statements_list:
            statement['amount'] = statement['amount'] * -1
        active_id = self._context.get('active_id')
        bank_statement = self.env['account.bank.statement'].browse(active_id)
        statement_lines = [(0, 0, statement) for statement in statements_list]
        if bank_statement.line_ids:
            bank_statement.line_ids.unlink()
        bank_statement.line_ids = statement_lines
        return {
            'view_mode': 'form',
            'res_model': 'account.bank.statement',
            'type': 'ir.actions.act_window',
            'target': 'current',
            'res_id': bank_statement.id
        }

