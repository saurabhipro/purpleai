from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime

class PTLForm(models.Model):
    _name = 'ptl.form'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'PTL Form - Complete Workflow'
    _rec_name = 'form_name'

    def _valid_field_parameter(self, field, name):
        return name == 'placeholder' or super()._valid_field_parameter(field, name)

    # Basic Information
    form_name = fields.Char(string='Form Name', compute='_compute_form_name', store=True)
    unit_no = fields.Char(string='Unit no.*', required=True, tracking=True)
    development = fields.Char(string='Development*', required=True, tracking=True)
    tenant_name = fields.Char(string='Tenant name*', required=True, tracking=True)
    approve_form_name = fields.Char(string='Approve form name', tracking=True)
    submitted_date = fields.Date(string='Submitted date', default=fields.Date.today, tracking=True)
    
    # Priority field
    priority = fields.Selection([
        ('1', 'Low'),
        ('2', 'Medium'),
        ('3', 'High')
    ], string='Priority', default='2', tracking=True)
    
    # Detailed Global Workflow Status (auto-computed)
    global_status = fields.Selection([
        ('ptl', 'PTL'),
        ('form_verification', 'Form Verification'),
        ('kick_off_meeting', 'Kick Off Meeting'),
        ('pending_with_rdd', 'Pending With RDD'),
        ('pending_with_tenant', 'Pending With Tenant'),
        ('rdd_review', 'RDD Review'),
        ('noc', 'NOC'),
        ('site_inspection_submission', 'Site Inspection Submission'),
        ('handover', 'Handover')
    ], string='Global Status', default='ptl', tracking=True, compute='_compute_global_status', store=True)

    # Section-specific statuses (NEW, PENDING, APPROVED, REJECTED)
    ptl_section_status = fields.Selection([
        ('new', 'NEW'),
        ('pending', 'PENDING'), 
        ('approved', 'APPROVED'),
        ('rejected', 'REJECTED')
    ], string='PTL Section Status', default='new', tracking=True)
    
    critical_path_section_status = fields.Selection([
        ('new', 'NEW'),
        ('pending', 'PENDING'),
        ('approved', 'APPROVED'),
        ('rejected', 'REJECTED')
    ], string='Critical Path Section Status', default='new', tracking=True)

    # PTL Section Fields (from your image)
    # Tenancy location and details
    ground_floor = fields.Char(string='Ground Floor')
    outdoor_area_gf = fields.Char(string='Outdoor area - GF')
    outdoor_area_mezz = fields.Char(string='Outdoor area - Mezz')
    
    # Tenant contact details
    tenant = fields.Char(string='Tenant')
    proposed_shop = fields.Char(string='Proposed shop')
    permitted_use = fields.Char(string='Permitted use')
    lease_term = fields.Char(string='Lease term')
    contact_person = fields.Char(string='Contact person')
    designation = fields.Char(string='Designation')
    address = fields.Text(string='Address (Physical address)')
    telephone = fields.Char(string='Telephone')
    mobile = fields.Char(string='Mobile')
    email = fields.Char(string='Email')
    
    # Key dates as per offer letter
    pit_out_commencement_date = fields.Date(string='Pit out commencement date')
    fit_out_period = fields.Date(string='Fit-out period')
    concept_design_submission_date = fields.Date(string='Concept design submission date')
    detail_design_submission_date = fields.Date(string='Detail design submission date')
    trade_start_date = fields.Date(string='Trade start date')
    late_opening_penalty = fields.Float(string='Late opening penalty (LOP)')
    note = fields.Text(string='Note')
    
    # Special requirements
    special_requirements = fields.Text(string='Special requirements')
    
    # Attach
    attachment = fields.Binary(string='Attach')
    attachment_name = fields.Char(string='Attachment Name')

    # Critical Path Section Fields (moved from PTL)
    # Design Activities with Days and Dates
    kickoff_meeting_days = fields.Integer(string='Kick-Off meeting / Project handover Days', default=0)
    kickoff_meeting_date = fields.Date(string='Kick-Off meeting / Project handover Date')
    
    concept_design_days = fields.Integer(string='Concept design submissions Days', default=0)
    concept_design_date = fields.Date(string='Concept design submissions Date')
    
    arch_detailed_design_days = fields.Integer(string='Arch detailed design submission Days', default=0)
    arch_detailed_design_date = fields.Date(string='Arch detailed design submission Date')
    
    mep_design_days = fields.Integer(string='MEP design submission Days', default=0)
    mep_design_date = fields.Date(string='MEP design submission Date')

    # Authority Activities
    civil_defence_days = fields.Integer(string='Civil defence approval Days', default=0)
    civil_defence_date = fields.Date(string='Civil defence approval Date')
    
    municipality_days = fields.Integer(string='Municipality fit-out permit/Authority submissions Days', default=0)
    municipality_date = fields.Date(string='Municipality fit-out permit/Authority submissions Date')
    
    sewa_approval_days = fields.Integer(string='SEWA / Water & power approval Days', default=0)
    sewa_approval_date = fields.Date(string='SEWA / Water & power approval Date')

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
    
    trading_days = fields.Integer(string='Trading Days', default=0)
    trade_date_date = fields.Date(string='Trade date Date')

    # Comments
    comments = fields.Text(string='Comments', placeholder='Comments...')

    @api.depends('unit_no', 'development')
    def _compute_form_name(self):
        for record in self:
            if record.unit_no and record.development:
                record.form_name = f"PTL - {record.development} - {record.unit_no}"
            else:
                record.form_name = "New PTL Form"

    @api.depends('ptl_section_status', 'critical_path_section_status')
    def _compute_global_status(self):
        """Auto-update global status based on section statuses"""
        for record in self:
            if record.ptl_section_status == 'approved' and record.critical_path_section_status == 'approved':
                record.global_status = 'handover'
            elif record.ptl_section_status == 'approved' and record.critical_path_section_status in ['pending', 'approved']:
                record.global_status = 'site_inspection_submission'
            elif record.ptl_section_status == 'approved':
                record.global_status = 'kick_off_meeting'
            elif record.ptl_section_status == 'pending':
                record.global_status = 'form_verification'
            else:
                record.global_status = 'ptl'

    # PTL Section Actions with Comments
    def action_approve_ptl_section(self):
        """Approve PTL Section with comment popup"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Approve PTL Section',
            'res_model': 'ptl.approval.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_ptl_form_id': self.id,
                'default_action_type': 'approve_ptl',
                'default_section_name': 'PTL Section'
            }
        }

    def action_reject_ptl_section(self):
        """Reject PTL Section with comment popup"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Reject PTL Section',
            'res_model': 'ptl.approval.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_ptl_form_id': self.id,
                'default_action_type': 'reject_ptl',
                'default_section_name': 'PTL Section'
            }
        }

    def action_set_ptl_pending(self):
        """Set PTL Section to Pending"""
        self.ensure_one()
        self.ptl_section_status = 'pending'
        self.message_post(body=f"PTL Section status changed to Pending by {self.env.user.name}")
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    # Critical Path Section Actions with Comments
    def action_approve_critical_path_section(self):
        """Approve Critical Path Section with comment popup"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Approve Critical Path Section',
            'res_model': 'ptl.approval.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_ptl_form_id': self.id,
                'default_action_type': 'approve_critical_path',
                'default_section_name': 'Critical Path Section'
            }
        }

    def action_reject_critical_path_section(self):
        """Reject Critical Path Section with comment popup"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Reject Critical Path Section',
            'res_model': 'ptl.approval.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_ptl_form_id': self.id,
                'default_action_type': 'reject_critical_path',
                'default_section_name': 'Critical Path Section'
            }
        }

    def action_set_critical_path_pending(self):
        """Set Critical Path Section to Pending"""
        self.ensure_one()
        self.critical_path_section_status = 'pending'
        self.message_post(body=f"Critical Path Section status changed to Pending by {self.env.user.name}")
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    @api.model_create_multi
    def create(self, vals_list):
        return super().create(vals_list)


class PTLApprovalWizard(models.TransientModel):
    _name = 'ptl.approval.wizard'
    _description = 'PTL Approval/Rejection Wizard'

    ptl_form_id = fields.Many2one('ptl.form', string='PTL Form', required=True)
    action_type = fields.Char(string='Action Type', required=True)
    section_name = fields.Char(string='Section Name', required=True)
    comments = fields.Text(string='Comments', required=True, placeholder='Please provide your comments for this approval/rejection...')

    def action_confirm(self):
        """Process the approval/rejection with comments"""
        self.ensure_one()
        ptl_form = self.ptl_form_id
        
        if self.action_type == 'approve_ptl':
            ptl_form.ptl_section_status = 'approved'
            message = f"✅ PTL Section APPROVED by {self.env.user.name}\n\nComments: {self.comments}"
            
        elif self.action_type == 'reject_ptl':
            ptl_form.ptl_section_status = 'rejected'
            message = f"❌ PTL Section REJECTED by {self.env.user.name}\n\nComments: {self.comments}"
            
        elif self.action_type == 'approve_critical_path':
            ptl_form.critical_path_section_status = 'approved'
            message = f"✅ Critical Path Section APPROVED by {self.env.user.name}\n\nComments: {self.comments}"
            
        elif self.action_type == 'reject_critical_path':
            ptl_form.critical_path_section_status = 'rejected'
            message = f"❌ Critical Path Section REJECTED by {self.env.user.name}\n\nComments: {self.comments}"
        
        # Post message to chatter
        ptl_form.message_post(
            body=message,
            message_type='comment',
            subtype_xmlid='mail.mt_comment'
        )
        
        return {'type': 'ir.actions.act_window_close'} 