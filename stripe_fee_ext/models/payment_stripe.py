# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    # Fees fields
    stripe_fees_active = fields.Boolean(string="Add Extra Fees")
    stripe_fees_dom_fixed = fields.Float(string="Fixed domestic fees")
    stripe_fees_dom_var = fields.Float(string="Variable domestic fees (in percents)")
    stripe_fees_int_fixed = fields.Float(string="Fixed international fees")
    stripe_fees_int_var = fields.Float(string="Variable international fees (in percents)")

    @api.constrains('stripe_fees_dom_var', 'stripe_fees_int_var')
    def _check_fee_var_within_boundaries(self):
        """ Check that variable fees are within realistic boundaries.

        Variable fee values should always be positive and below 100% to respectively avoid negative
        and infinite (division by zero) fee amounts.

        :return None
        """
        for provider in self:
            if any(not 0 <= fee < 100 for fee in (provider.stripe_fees_dom_var, provider.stripe_fees_int_var)):
                raise ValidationError(_("Variable fees must always be positive and below 100%."))

    def _compute_fees(self, amount, country):
        self.ensure_one()
        fees = 0.0
        if self.stripe_fees_active:
            if country == self.company_id.country_id:
                fixed = self.stripe_fees_dom_fixed
                variable = self.stripe_fees_dom_var
            else:
                fixed = self.stripe_fees_int_fixed
                variable = self.stripe_fees_int_var
            fees = (amount * variable / 100.0 + fixed) / (1 - variable / 100.0)
        return fees

    def get_fees(self, amount, partner_id):
        fees = 0.0
        if amount and partner_id:
            partner = self.env['res.partner'].browse(partner_id)
            fees = self._compute_fees(amount, partner.country_id)
        return fees
