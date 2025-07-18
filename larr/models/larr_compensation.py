from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


class LARRCompensation(models.Model):
    _name = 'larr.compensation'
    _description = 'Compensation Management'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char('Compensation Reference', required=True, copy=False, readonly=True, 
                      default=lambda self: _('New'))
    acquisition_id = fields.Many2one('larr.land.acquisition', 'Land Acquisition', required=True, tracking=True)
    beneficiary_id = fields.Many2one('res.partner', 'Beneficiary', required=True, tracking=True)
    
    # Compensation Details
    compensation_type = fields.Selection([
        ('land', 'Land Compensation'),
        ('structure', 'Structure Compensation'),
        ('crop', 'Crop Compensation'),
        ('livelihood', 'Livelihood Compensation'),
        ('other', 'Other')
    ], required=True, tracking=True)
    
    amount = fields.Monetary('Amount', currency_field='currency_id', required=True, tracking=True)
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)
    
    # Payment Details
    payment_method = fields.Selection([
        ('bank_transfer', 'Bank Transfer'),
        ('cheque', 'Cheque'),
        ('cash', 'Cash'),
        ('other', 'Other')
    ], tracking=True)
    
    payment_date = fields.Date('Payment Date', tracking=True)
    payment_reference = fields.Char('Payment Reference', tracking=True)
    
    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('paid', 'Paid'),
        ('cancelled', 'Cancelled')
    ], default='draft', tracking=True)
    
    # Documents
    document_ids = fields.Many2many('ir.attachment', string='Documents')
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('larr.compensation') or _('New')
        return super().create(vals_list)
    
    def action_submit(self):
        self.write({'state': 'submitted'})
    
    def action_approve(self):
        self.write({'state': 'approved'})
    
    def action_pay(self):
        self.write({'state': 'paid'})
    
    def action_cancel(self):
        self.write({'state': 'cancelled'}) 