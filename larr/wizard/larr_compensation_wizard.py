from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


class LARRCompensationWizard(models.TransientModel):
    _name = 'larr.compensation.wizard'
    _description = 'LARR Compensation Wizard'

    acquisition_id = fields.Many2one('larr.land.acquisition', 'Land Acquisition', required=True)
    compensation_type = fields.Selection([
        ('land', 'Land Compensation'),
        ('structure', 'Structure Compensation'),
        ('crop', 'Crop Compensation'),
        ('livelihood', 'Livelihood Compensation'),
        ('other', 'Other')
    ], required=True, string='Compensation Type')
    
    amount = fields.Monetary('Amount', currency_field='currency_id', required=True)
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)
    
    payment_method = fields.Selection([
        ('bank_transfer', 'Bank Transfer'),
        ('cheque', 'Cheque'),
        ('cash', 'Cash'),
        ('other', 'Other')
    ], string='Payment Method')
    
    payment_date = fields.Date('Payment Date', default=fields.Date.today)
    payment_reference = fields.Char('Payment Reference')
    
    beneficiary_id = fields.Many2one('res.partner', 'Beneficiary', required=True)
    notes = fields.Text('Notes')
    
    @api.onchange('acquisition_id')
    def _onchange_acquisition_id(self):
        if self.acquisition_id:
            self.beneficiary_id = self.acquisition_id.land_owner_id
    
    def action_create_compensation(self):
        """Create compensation record"""
        compensation_vals = {
            'acquisition_id': self.acquisition_id.id,
            'beneficiary_id': self.beneficiary_id.id,
            'compensation_type': self.compensation_type,
            'amount': self.amount,
            'payment_method': self.payment_method,
            'payment_date': self.payment_date,
            'payment_reference': self.payment_reference,
        }
        
        compensation = self.env['larr.compensation'].create(compensation_vals)
        
        # Update acquisition compensation status
        total_compensation = sum(self.acquisition_id.compensation_ids.mapped('amount'))
        if total_compensation >= self.acquisition_id.compensation_amount:
            self.acquisition_id.write({'compensation_status': 'completed'})
        elif total_compensation > 0:
            self.acquisition_id.write({'compensation_status': 'partial'})
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'larr.compensation',
            'res_id': compensation.id,
            'view_mode': 'form',
            'target': 'current',
        }


class LARRBulkCompensationWizard(models.TransientModel):
    _name = 'larr.bulk.compensation.wizard'
    _description = 'LARR Bulk Compensation Wizard'

    project_id = fields.Many2one('larr.project', 'Project', required=True)
    compensation_type = fields.Selection([
        ('land', 'Land Compensation'),
        ('structure', 'Structure Compensation'),
        ('crop', 'Crop Compensation'),
        ('livelihood', 'Livelihood Compensation'),
        ('other', 'Other')
    ], required=True, string='Compensation Type')
    
    amount_per_acquisition = fields.Monetary('Amount per Acquisition', currency_field='currency_id', required=True)
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)
    
    payment_method = fields.Selection([
        ('bank_transfer', 'Bank Transfer'),
        ('cheque', 'Cheque'),
        ('cash', 'Cash'),
        ('other', 'Other')
    ], string='Payment Method')
    
    payment_date = fields.Date('Payment Date', default=fields.Date.today)
    
    acquisition_ids = fields.Many2many('larr.land.acquisition', string='Selected Acquisitions')
    
    @api.onchange('project_id')
    def _onchange_project_id(self):
        if self.project_id:
            self.acquisition_ids = self.project_id.acquisition_ids.filtered(lambda x: x.state in ['agreement', 'possession', 'completed'])
    
    def action_create_bulk_compensation(self):
        """Create compensation records for multiple acquisitions"""
        compensations = self.env['larr.compensation']
        
        for acquisition in self.acquisition_ids:
            compensation_vals = {
                'acquisition_id': acquisition.id,
                'beneficiary_id': acquisition.land_owner_id.id,
                'compensation_type': self.compensation_type,
                'amount': self.amount_per_acquisition,
                'payment_method': self.payment_method,
                'payment_date': self.payment_date,
            }
            
            compensation = self.env['larr.compensation'].create(compensation_vals)
            compensations |= compensation
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'larr.compensation',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', compensations.ids)],
            'target': 'current',
        } 