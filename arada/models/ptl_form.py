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

    tenant_appointment_section_status = fields.Selection([
        ('new', 'NEW'),
        ('pending', 'PENDING'),
        ('approved', 'APPROVED'),
        ('rejected', 'REJECTED')
    ], string='Tenant Appointment Section Status', default='new', tracking=True)

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

    # Critical Path Fields
    # Design Activities
    kickoff_meeting_days = fields.Integer(string='Kick-Off meeting / Project handover Days')
    kickoff_meeting_date = fields.Date(string='Kick-Off meeting / Project handover Date')
    concept_design_days = fields.Integer(string='Concept design submissions Days')
    concept_design_date = fields.Date(string='Concept design submissions Date')
    arch_detailed_design_days = fields.Integer(string='Arch detailed design submission Days')
    arch_detailed_design_date = fields.Date(string='Arch detailed design submission Date')
    mep_design_days = fields.Integer(string='MEP design submission Days')
    mep_design_date = fields.Date(string='MEP design submission Date')

    # Authority Activities
    civil_defence_days = fields.Integer(string='Civil defence approval submission Days')
    civil_defence_date = fields.Date(string='Civil defence approval submission Date')
    municipality_days = fields.Integer(string='Municipality approval submission Days')
    municipality_date = fields.Date(string='Municipality approval submission Date')
    sewa_approval_days = fields.Integer(string='SEWA approval submission Days')
    sewa_approval_date = fields.Date(string='SEWA approval submission Date')

    # Execution Activities
    site_mobilization_days = fields.Integer(string='Site mobilization Days')
    site_mobilization_date = fields.Date(string='Site mobilization Date')
    fitout_works_days = fields.Integer(string='Fit-out works completion Days')
    fitout_works_date = fields.Date(string='Fit-out works completion Date')
    final_inspection_days = fields.Integer(string='Final inspection Days')
    final_inspection_date = fields.Date(string='Final inspection Date')
    snag_completion_days = fields.Integer(string='Snag completion Days')
    snag_completion_date = fields.Date(string='Snag completion Date')
    handover_approvals_days = fields.Integer(string='Handover & approvals Days')
    handover_approvals_date = fields.Date(string='Handover & approvals Date')
    trading_days = fields.Integer(string='Trading commencement Days')
    trade_date_date = fields.Date(string='Trade date Date')

    # Comments
    comments = fields.Text(string='Comments', placeholder='Comments...')

    # Tenant Appointment Fields
    # TAR Details
    tar_approval_required = fields.Boolean(string='TAR Approval Required', default=True)
    
    # Primary Contact
    primary_contact_name = fields.Char(string='Primary Contact Name')
    primary_contact_designation = fields.Char(string='Primary Contact Designation')
    primary_contact_company = fields.Char(string='Primary Contact Company')
    primary_contact_telephone = fields.Char(string='Primary Contact Telephone')
    primary_contact_mobile = fields.Char(string='Primary Contact Mobile')
    primary_contact_email = fields.Char(string='Primary Contact Email')
    primary_contact_experience = fields.Text(string='Primary Contact Experience')
    
    # Secondary Contact
    secondary_contact_name = fields.Char(string='Secondary Contact Name')
    secondary_contact_designation = fields.Char(string='Secondary Contact Designation') 
    secondary_contact_company = fields.Char(string='Secondary Contact Company')
    secondary_contact_telephone = fields.Char(string='Secondary Contact Telephone')
    secondary_contact_mobile = fields.Char(string='Secondary Contact Mobile')
    secondary_contact_email = fields.Char(string='Secondary Contact Email')
    secondary_contact_experience = fields.Text(string='Secondary Contact Experience')
    
    # Tenant Designer
    tenant_designer_name = fields.Char(string='Tenant Designer Name')
    tenant_designer_company = fields.Char(string='Tenant Designer Company')
    tenant_designer_contact = fields.Char(string='Tenant Designer Contact Number')
    tenant_designer_email = fields.Char(string='Tenant Designer Email')
    tenant_designer_work_history = fields.Text(string='Tenant Designer Work History')
    
    # Tenant Contractor
    tenant_contractor_name = fields.Char(string='Tenant Contractor Name')
    tenant_contractor_company = fields.Char(string='Tenant Contractor Company Name')
    tenant_contractor_contact = fields.Char(string='Tenant Contractor Contact Number')
    tenant_contractor_email = fields.Char(string='Tenant Contractor Email')
    tenant_contractor_work_history = fields.Text(string='Tenant Contractor Work History')
    tenant_contractor_trade_license = fields.Char(string='Tenant Contractor Trade License')
    tenant_contractor_company_profile = fields.Text(string='Tenant Contractor Company Profile')
    tenant_contractor_comments = fields.Text(string='Tenant Contractor Comments')
    
    # Overall Status & Attachment
    tenant_appointment_overall_status = fields.Selection([
        ('no_objection', 'No Objection'),
        ('pending_review', 'Pending Review'),
        ('rejected', 'Rejected')
    ], string='Overall Status', default='pending_review')
    
    tenant_appointment_attachment = fields.Binary(string='Tenant Appointment Attachment')
    tenant_appointment_attachment_name = fields.Char(string='Tenant Appointment Attachment Name')
    tenant_appointment_comments = fields.Text(string='Tenant Appointment Comments')

    @api.depends('unit_no', 'development')
    def _compute_form_name(self):
        for record in self:
            if record.unit_no and record.development:
                record.form_name = f"PTL - {record.development} - {record.unit_no}"
            else:
                record.form_name = "New PTL Form"

    @api.depends('ptl_section_status', 'critical_path_section_status', 'tenant_appointment_section_status')
    def _compute_global_status(self):
        """Auto-update global status based on section statuses"""
        for record in self:
            if (record.ptl_section_status == 'approved' and 
                record.critical_path_section_status == 'approved' and 
                record.tenant_appointment_section_status == 'approved'):
                record.global_status = 'handover'
            elif record.tenant_appointment_section_status == 'approved':
                record.global_status = 'site_inspection_submission'
            elif record.critical_path_section_status == 'approved':
                record.global_status = 'rdd_review'
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

    # Tenant Appointment Section Actions with Comments
    def action_approve_tenant_appointment_section(self):
        """Approve Tenant Appointment Section with comment popup"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Approve Tenant Appointment Section',
            'res_model': 'ptl.approval.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_ptl_form_id': self.id,
                'default_action_type': 'approve_tenant_appointment',
                'default_section_name': 'Tenant Appointment Section'
            }
        }

    def action_reject_tenant_appointment_section(self):
        """Reject Tenant Appointment Section with comment popup"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Reject Tenant Appointment Section',
            'res_model': 'ptl.approval.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_ptl_form_id': self.id,
                'default_action_type': 'reject_tenant_appointment',
                'default_section_name': 'Tenant Appointment Section'
            }
        }

    def action_set_tenant_appointment_pending(self):
        """Set Tenant Appointment Section to Pending"""
        self.ensure_one()
        self.tenant_appointment_section_status = 'pending'
        self.message_post(body=f"Tenant Appointment Section status changed to Pending by {self.env.user.name}")
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

        elif self.action_type == 'approve_tenant_appointment':
            ptl_form.tenant_appointment_section_status = 'approved'
            message = f"✅ Tenant Appointment Section APPROVED by {self.env.user.name}\n\nComments: {self.comments}"
            
        elif self.action_type == 'reject_tenant_appointment':
            ptl_form.tenant_appointment_section_status = 'rejected'
            message = f"❌ Tenant Appointment Section REJECTED by {self.env.user.name}\n\nComments: {self.comments}"
        
        # Post message to chatter
        ptl_form.message_post(
            body=message,
            message_type='comment',
            subtype_xmlid='mail.mt_comment'
        )
        
        return {'type': 'ir.actions.act_window_close'} 