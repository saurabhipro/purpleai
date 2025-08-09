from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime

class PTLForm(models.Model):
    _name = 'ptl.form'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'PTL Form - Initial Notification Confirmed Offer'
    _rec_name = 'form_name'

    # Basic Information
    form_name = fields.Char(string='Form Name', compute='_compute_form_name', store=True)
    unit_no = fields.Char(string='Unit no.*', required=True, tracking=True)
    development = fields.Char(string='Development*', required=True, tracking=True)
    tenant_name = fields.Char(string='Tenant name*', required=True, tracking=True)
    approve_form_name = fields.Char(string='Approve form name', tracking=True)
    submitted_date = fields.Date(string='Submitted date', default=fields.Date.today, tracking=True)
    
    # Status
    status = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    ], string='Status', default='draft', tracking=True)

    # Tenancy location and details
    ground_floor = fields.Char(string='Ground floor*', required=True, tracking=True)
    mezzanine_floor = fields.Char(string='Mezzanine floor*', required=True, tracking=True)
    outdoor_area_gf = fields.Char(string='Outdoor area - GF*', required=True, tracking=True)
    outdoor_area_mezz = fields.Char(string='Outdoor area - Mezz*', required=True, tracking=True)

    # Tenant contact details
    proposed_shop_name = fields.Char(string='Proposed shop name*', required=True, tracking=True)
    permitted_use = fields.Char(string='Permitted use*', required=True, tracking=True)
    lease_term = fields.Integer(string='Lease term*', required=True, default=0, tracking=True)
    contact_person_name = fields.Char(string='Contact person name*', required=True, tracking=True)
    designation = fields.Char(string='Designation*', required=True, tracking=True)
    company_name = fields.Char(string='Company name*', required=True, tracking=True)
    address = fields.Text(string='Address (Physical address)*', required=True, tracking=True)
    
    # Contact information
    telephone = fields.Char(string='Telephone*', required=True, default="+971 55 223 3444", tracking=True)
    mobile = fields.Char(string='Mobile*', required=True, default="+971 55 223 3444", tracking=True)
    email = fields.Char(string='Email*', required=True, tracking=True)
    
    # Key dates as per offer letter
    fit_out_commencement_date = fields.Date(string='Fit out commencement date*', required=True, tracking=True)
    fit_out_period = fields.Date(string='Fit-out period*', required=True, tracking=True)
    concept_design_submission_date = fields.Date(string='Concept design submission date*', required=True, tracking=True)
    detail_design_submission_date = fields.Date(string='Detail design submission date*', required=True, tracking=True)
    trade_start_date = fields.Date(string='Trade start date*', required=True, tracking=True)
    
    # Financial details
    late_opening_penalty = fields.Float(string='Late opening penalty (LOP)*', default=0.0, tracking=True)
    notes = fields.Text(string='Note*', tracking=True)
    
    # Special requirements
    special_requirements = fields.Text(string='Special requirements', tracking=True)
    
    # Simple Attachment - Single file upload
    ptl_attachment = fields.Binary(string='Attachment', tracking=True)
    ptl_attachment_filename = fields.Char(string='Attachment Filename')

    @api.depends('tenant_name', 'unit_no')
    def _compute_form_name(self):
        for record in self:
            if record.tenant_name and record.unit_no:
                record.form_name = f"PTL - {record.tenant_name} - Unit {record.unit_no}"
            else:
                record.form_name = "New PTL Form"

    def action_submit(self):
        """Submit the PTL form"""
        self.ensure_one()
        self.status = 'submitted'
        self.submitted_date = fields.Date.today()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('PTL Form submitted successfully.'),
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_approve(self):
        """Approve the PTL form"""
        self.ensure_one()
        self.status = 'approved'
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('PTL Form approved successfully.'),
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_reject(self):
        """Reject the PTL form"""
        self.ensure_one()
        self.status = 'rejected'
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('PTL Form rejected.'),
                'type': 'warning',
                'sticky': False,
            }
        } 