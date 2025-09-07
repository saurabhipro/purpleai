# -*- coding: utf-8 -*-

from werkzeug import urls

from odoo import models, fields, api, _
from odoo.addons.payment import utils as payment_utils
# from odoo.addons.payment_stripe.const import PAYMENT_METHOD_TYPES
from odoo.addons.payment_stripe.controllers.main import StripeController


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    stripe_fees = fields.Monetary(
        string="Fees", currency_field='currency_id',
        help="The fees amount; set by the system as it depends on the provider", readonly=True)

    @api.model_create_multi
    def create(self, values_list):
        for values in values_list:
            provider = self.env['payment.provider'].browse(values['provider_id'])
            partner = self.env['res.partner'].browse(values['partner_id'])
            if values.get('operation') == 'validation':
                values['stripe_fees'] = 0
            else:
                currency = self.env['res.currency'].browse(values.get('currency_id')).exists()
                values['stripe_fees'] = provider._compute_fees(
                    values.get('amount', 0), partner.country_id,
                )
        txs = super().create(values_list)
        txs.invalidate_recordset(['amount', 'stripe_fees'])
        return txs

    def _stripe_prepare_payment_intent_payload(self):
        """ Prepare the payload for the creation of a payment intent in Stripe format.

        Note: This method serves as a hook for modules that would fully implement Stripe Connect.
        Note: self.ensure_one()

        :return: The Stripe-formatted payload for the payment intent request
        :rtype: dict
        """

        res = super(PaymentTransaction, self)._stripe_prepare_payment_intent_payload()
        res.update({
            'amount': payment_utils.to_minor_currency_units(
                self.amount + self.stripe_fees, self.currency_id),
        })
        return res
