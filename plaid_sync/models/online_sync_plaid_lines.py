from odoo import models, fields, _

class OnlineSyncPlaidLines(models.Model):
    _name = 'online.sync.plaid.lines'
    _description = 'Accounts associated with the item'

    _rec_name = 'account_name'
    account_id = fields.Char(invisible=True)
    account_name = fields.Char(string="Name")
    account_type = fields.Char(string='Type')
    account_subtype = fields.Char(string='Subtype')
    plaid_sync_id = fields.Many2one('online.sync.plaid')
