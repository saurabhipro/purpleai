from odoo import fields, models, api, _

class Company(models.Model):
    _inherit = "res.company"

    plaid_client = fields.Char(string="Plaid Client ID", readonly=False)
    plaid_secret = fields.Char(string="Plaid Secret", readonly=False)

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    plaid_client = fields.Char(string="Plaid Client ID", readonly=False, related='company_id.plaid_client')
    plaid_secret = fields.Char(string="Plaid Secret", readonly=False, related='company_id.plaid_secret')
    plaid_account_setting = fields.Selection(
        [('sandbox', 'Sandbox'), ('development', 'Development'), ('production', 'Production')],
        string="Plaid Environment", default='production')

    @api.model
    def set_values(self):
        super(ResConfigSettings, self).set_values()
        self.env['ir.config_parameter'].set_param('plaid_sync.plaid_account_setting', self.plaid_account_setting)
    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        plaid_account = self.env['ir.config_parameter'].get_param('plaid_sync.plaid_account_setting', self.plaid_account_setting)
        res.update(
            plaid_account_setting=plaid_account
        )
        return res
