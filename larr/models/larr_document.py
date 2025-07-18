from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


class LARRDocument(models.Model):
    _name = 'larr.document'
    _description = 'LARR Document Management'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char('Document Name', required=True, tracking=True)
    document_type = fields.Selection([
        ('land_record', 'Land Record'),
        ('ownership_deed', 'Ownership Deed'),
        ('survey_report', 'Survey Report'),
        ('compensation_agreement', 'Compensation Agreement'),
        ('rehabilitation_plan', 'Rehabilitation Plan'),
        ('government_order', 'Government Order'),
        ('legal_document', 'Legal Document'),
        ('other', 'Other')
    ], required=True, tracking=True)
    
    # Related Records
    project_id = fields.Many2one('larr.project', 'Project', tracking=True)
    acquisition_id = fields.Many2one('larr.land.acquisition', 'Land Acquisition', tracking=True)
    rehabilitation_id = fields.Many2one('larr.rehabilitation', 'Rehabilitation', tracking=True)
    compensation_id = fields.Many2one('larr.compensation', 'Compensation', tracking=True)
    stakeholder_id = fields.Many2one('larr.stakeholder', 'Stakeholder', tracking=True)
    
    # Document Details
    document_number = fields.Char('Document Number', tracking=True)
    issue_date = fields.Date('Issue Date', tracking=True)
    expiry_date = fields.Date('Expiry Date', tracking=True)
    description = fields.Text('Description')
    
    # File Attachment
    attachment_ids = fields.Many2many('ir.attachment', string='Document Files', tracking=True)
    
    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('verified', 'Verified'),
        ('approved', 'Approved'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled')
    ], default='draft', tracking=True)
    
    # Verification
    verified_by = fields.Many2one('hr.employee', 'Verified By', tracking=True)
    verified_date = fields.Date('Verified Date', tracking=True)
    verification_notes = fields.Text('Verification Notes')
    
    # Approval
    approved_by = fields.Many2one('hr.employee', 'Approved By', tracking=True)
    approved_date = fields.Date('Approved Date', tracking=True)
    approval_notes = fields.Text('Approval Notes')
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name'):
                vals['name'] = _('New Document')
        return super().create(vals_list)
    
    def action_submit(self):
        self.write({'state': 'submitted'})
    
    def action_verify(self):
        self.write({
            'state': 'verified',
            'verified_by': self.env.user.employee_id.id,
            'verified_date': fields.Date.today()
        })
    
    def action_approve(self):
        self.write({
            'state': 'approved',
            'approved_by': self.env.user.employee_id.id,
            'approved_date': fields.Date.today()
        })
    
    def action_cancel(self):
        self.write({'state': 'cancelled'}) 