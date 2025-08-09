from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime

class CriticalPath(models.Model):
    _name = 'critical.path'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Critical Path Form'
    _rec_name = 'name'

    # Basic Information
    name = fields.Char(string='Name', compute='_compute_name', store=True)
    ptl_form_id = fields.Many2one('ptl.form', string='Related PTL Form', required=True, ondelete='cascade')
    
    # Status
    status = fields.Selection([
        ('draft', 'Draft'),
        ('in_progress', 'In Progress'),
        ('approved', 'Approved'),
        ('completed', 'Completed')
    ], string='Status', default='draft', tracking=True)

    # Design Section
    design_section = fields.Text(string='Design Section Description', default='Design')
    
    # Design Activities with Days and Dates
    kickoff_meeting_days = fields.Integer(string='Kick-Off meeting / Project handover Days', default=0)
    kickoff_meeting_date = fields.Date(string='Kick-Off meeting / Project handover Date')
    
    concept_design_days = fields.Integer(string='Concept design submissions Days', default=0)
    concept_design_date = fields.Date(string='Concept design submissions Date')
    
    arch_detailed_design_days = fields.Integer(string='Arch detailed design submission Days', default=0)
    arch_detailed_design_date = fields.Date(string='Arch detailed design submission Date')
    
    mep_design_days = fields.Integer(string='MEP design submission Days', default=0)
    mep_design_date = fields.Date(string='MEP design submission Date')

    # Authority Section
    authority_section = fields.Text(string='Authority Section Description', default='Authority')
    
    # Authority Activities
    civil_defence_days = fields.Integer(string='Civil defence approval Days', default=0)
    civil_defence_date = fields.Date(string='Civil defence approval Date')
    
    municipality_days = fields.Integer(string='Municipality fit-out permit/Authority submissions Days', default=0)
    municipality_date = fields.Date(string='Municipality fit-out permit/Authority submissions Date')
    
    sewa_approval_days = fields.Integer(string='SEWA / Water & power approval Days', default=0)
    sewa_approval_date = fields.Date(string='SEWA / Water & power approval Date')

    # Execution Section
    execution_section = fields.Text(string='Execution Section Description', default='Execution')
    
    # Execution Activities
    site_mobilization_days = fields.Integer(string='Site mobilization Days', default=0)
    site_mobilization_date = fields.Date(string='Site mobilization Date')
    
    fitout_works_days = fields.Integer(string='Fitout works Days', default=0)
    fitout_works_date = fields.Date(string='Fitout works Date')
    
    final_inspection_days = fields.Integer(string='Final inspection Days', default=0)
    final_inspection_date = fields.Date(string='Final inspection Date')
    
    snag_completion_days = fields.Integer(string='Snag completion Days', default=0)
    snag_completion_date = fields.Date(string='Snag completion Date')
    
    handover_approvals_days = fields.Integer(string='Handover of all approvals Days', default=0)
    handover_approvals_date = fields.Date(string='Handover of all approvals Date')
    
    merchandising_start_days = fields.Integer(string='Merchandising start Days', default=0)
    merchandising_start_date = fields.Date(string='Merchandising start Date')
    
    trade_date_days = fields.Integer(string='Trade date Days', default=0)
    trade_date_date = fields.Date(string='Trade date Date')

    # Financial Information
    late_opening_penalty = fields.Float(string='Late opening penalty (LOP) AED per calendar day', default=0.0)
    
    # Comments
    comments = fields.Text(string='Comments', placeholder='Comments...')

    @api.depends('ptl_form_id')
    def _compute_name(self):
        for record in self:
            if record.ptl_form_id:
                record.name = f"Critical Path - {record.ptl_form_id.tenant_name} - Unit {record.ptl_form_id.unit_no}"
            else:
                record.name = "New Critical Path"

    def action_start_progress(self):
        """Start Progress"""
        self.ensure_one()
        self.status = 'in_progress'
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Critical Path moved to In Progress.'),
                'type': 'info',
                'sticky': False,
            }
        }

    def action_approve(self):
        """Approve Critical Path"""
        self.ensure_one()
        self.status = 'approved'
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Critical Path approved successfully.'),
                'type': 'success',
                'sticky': False,
            }
        }

    def action_complete(self):
        """Complete Critical Path"""
        self.ensure_one()
        self.status = 'completed'
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Critical Path completed successfully.'),
                'type': 'success',
                'sticky': False,
            }
        }

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
    
    # Updated Status with new workflow states
    status = fields.Selection([
        ('new', 'New'),
        ('in_progress', 'In progress'),
        ('approved', 'Approved'),
        ('completed', 'Completed'),
        ('returned', 'Returned')
    ], string='Status', default='new', tracking=True)

    # Critical Path Fields (embedded in PTL form)
    critical_path_created = fields.Boolean(string='Critical Path Created', default=False)
    
    # Design Section
    design_section = fields.Text(string='Design Section Description', default='Design')
    
    # Design Activities with Days and Dates
    kickoff_meeting_days = fields.Integer(string='Kick-Off meeting / Project handover Days', default=0)
    kickoff_meeting_date = fields.Date(string='Kick-Off meeting / Project handover Date')
    
    concept_design_days = fields.Integer(string='Concept design submissions Days', default=0)
    concept_design_date = fields.Date(string='Concept design submissions Date')
    
    arch_detailed_design_days = fields.Integer(string='Arch detailed design submission Days', default=0)
    arch_detailed_design_date = fields.Date(string='Arch detailed design submission Date')
    
    mep_design_days = fields.Integer(string='MEP design submission Days', default=0)
    mep_design_date = fields.Date(string='MEP design submission Date')

    # Authority Section
    authority_section = fields.Text(string='Authority Section Description', default='Authority')
    
    # Authority Activities
    civil_defence_days = fields.Integer(string='Civil defence approval Days', default=0)
    civil_defence_date = fields.Date(string='Civil defence approval Date')
    
    municipality_days = fields.Integer(string='Municipality fit-out permit/Authority submissions Days', default=0)
    municipality_date = fields.Date(string='Municipality fit-out permit/Authority submissions Date')
    
    sewa_approval_days = fields.Integer(string='SEWA / Water & power approval Days', default=0)
    sewa_approval_date = fields.Date(string='SEWA / Water & power approval Date')

    # Execution Section
    execution_section = fields.Text(string='Execution Section Description', default='Execution')
    
    # Execution Activities
    site_mobilization_days = fields.Integer(string='Site mobilization Days', default=0)
    site_mobilization_date = fields.Date(string='Site mobilization Date')
    
    fitout_works_days = fields.Integer(string='Fitout works Days', default=0)
    fitout_works_date = fields.Date(string='Fitout works Date')
    
    final_inspection_days = fields.Integer(string='Final inspection Days', default=0)
    final_inspection_date = fields.Date(string='Final inspection Date')
    
    snag_completion_days = fields.Integer(string='Snag completion Days', default=0)
    snag_completion_date = fields.Date(string='Snag completion Date')
    
    handover_approvals_days = fields.Integer(string='Handover of all approvals Days', default=0)
    handover_approvals_date = fields.Date(string='Handover of all approvals Date')
    
    merchandising_start_days = fields.Integer(string='Merchandising start Days', default=0)
    merchandising_start_date = fields.Date(string='Merchandising start Date')
    
    trade_date_days = fields.Integer(string='Trade date Days', default=0)
    trade_date_date = fields.Date(string='Trade date Date')

    # Critical Path Comments
    critical_path_comments = fields.Text(string='Critical Path Comments', placeholder='Comments...')

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
    critical_path_late_penalty = fields.Float(string='Critical Path Late opening penalty (LOP) AED per calendar day', default=0.0)
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

    def action_start_progress(self):
        """Move to In Progress"""
        self.ensure_one()
        self.status = 'in_progress'
        # Return action to refresh the view
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'ptl.form',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_approve(self):
        """Approve the PTL form and activate Critical Path tab"""
        self.ensure_one()
        self.status = 'approved'
        
        # Activate Critical Path
        if not self.critical_path_created:
            self.critical_path_created = True
        
        # Return action to refresh the view and show Critical Path tab
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'ptl.form',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_complete(self):
        """Complete the PTL form"""
        self.ensure_one()
        self.status = 'completed'
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'ptl.form',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def action_return(self):
        """Return the PTL form"""
        self.ensure_one()
        self.status = 'returned'
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'ptl.form',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_reset_to_new(self):
        """Reset to New status"""
        self.ensure_one()
        self.status = 'new'
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'ptl.form',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        } 