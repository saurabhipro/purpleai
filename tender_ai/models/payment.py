# -*- coding: utf-8 -*-

from odoo import models, fields, api


class Payment(models.Model):
    _name = 'tende_ai.payment'
    _description = 'Payment Record'
    _order = 'transaction_date desc'

    bidder_id = fields.Many2one('tende_ai.bidder', string='Bidder', required=True, ondelete='cascade', readonly=True)
    job_id = fields.Many2one(
        'tende_ai.job',
        string='Job',
        related='bidder_id.job_id',
        readonly=True,
        store=True,
        index=True,
    )
    
    # Related fields for easier display
    company_name = fields.Char(string='Company Name', related='bidder_id.vendor_company_name', readonly=True, store=True)
    
    # NOTE: do not use field parameter "tracking" unless the model inherits mail.thread
    vendor = fields.Char(string='Vendor')
    payment_mode = fields.Char(string='Payment Mode')
    bank_name = fields.Char(string='Bank Name')
    transaction_id = fields.Char(string='Transaction ID', index=True)
    amount_inr = fields.Char(string='Amount (INR)')
    transaction_date = fields.Char(string='Transaction Date')
    status = fields.Char(string='Status')

