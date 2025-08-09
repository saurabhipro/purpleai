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
    
    priority = fields.Selection([
        ('1', 'Low'),
        ('2', 'Medium'),
        ('3', 'High')
    ], string='Priority', default='2', tracking=True)

    # Global workflow status (auto-computed from section statuses)
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

    conceptual_design_section_status = fields.Selection([
        ('new', 'NEW'),
        ('pending', 'PENDING'),
        ('approved', 'APPROVED'),
        ('rejected', 'REJECTED')
    ], string='Conceptual Design Section Status', default='new', tracking=True)

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

    # Key dates
    lease_commencement = fields.Date(string='Lease commencement')
    lease_expiry = fields.Date(string='Lease expiry')
    fitout_commencement = fields.Date(string='Fitout commencement')
    trading_commencement = fields.Date(string='Trading commencement')

    # Critical Path Section Fields (Design Activities)
    kickoff_meeting_days = fields.Integer(string='Kickoff Meeting (Days)')
    kickoff_meeting_date = fields.Date(string='Kickoff Meeting Date')
    concept_design_days = fields.Integer(string='Concept Design (Days)')
    concept_design_date = fields.Date(string='Concept Design Date')
    arch_detailed_design_days = fields.Integer(string='Arch Detailed Design (Days)')
    arch_detailed_design_date = fields.Date(string='Arch Detailed Design Date')
    mep_design_days = fields.Integer(string='MEP Design (Days)')
    mep_design_date = fields.Date(string='MEP Design Date')

    # Authority Activities
    civil_defence_days = fields.Integer(string='Civil Defence (Days)')
    civil_defence_date = fields.Date(string='Civil Defence Date')
    municipality_days = fields.Integer(string='Municipality (Days)')
    municipality_date = fields.Date(string='Municipality Date')
    sewa_approval_days = fields.Integer(string='SEWA Approval (Days)')
    sewa_approval_date = fields.Date(string='SEWA Approval Date')

    # Execution Activities
    site_mobilization_days = fields.Integer(string='Site Mobilization (Days)')
    site_mobilization_date = fields.Date(string='Site Mobilization Date')
    fitout_works_days = fields.Integer(string='Fitout Works (Days)')
    fitout_works_date = fields.Date(string='Fitout Works Date')
    final_inspection_days = fields.Integer(string='Final Inspection (Days)')
    final_inspection_date = fields.Date(string='Final Inspection Date')
    snag_completion_days = fields.Integer(string='Snag Completion (Days)')
    snag_completion_date = fields.Date(string='Snag Completion Date')
    handover_approvals_days = fields.Integer(string='Handover Approvals (Days)')
    handover_approvals_date = fields.Date(string='Handover Approvals Date')
    trading_days = fields.Integer(string='Trading (Days)')
    trade_date_date = fields.Date(string='Trade Date')

    # Financial
    late_opening_penalty = fields.Monetary(string='Late Opening Penalty', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)

    # Comments
    comments = fields.Text(string='Comments')

    # Tenant Appointment Fields
    tenant_permit_submission_days = fields.Integer(string='Tenant Permit Submission (Days)')
    tenant_permit_submission_date = fields.Date(string='Tenant Permit Submission Date')
    tenant_approval_days = fields.Integer(string='Tenant Approval (Days)')
    tenant_approval_date = fields.Date(string='Tenant Approval Date')
    tenant_noc_days = fields.Integer(string='Tenant NOC (Days)')
    tenant_noc_date = fields.Date(string='Tenant NOC Date')
    tenant_final_inspection_days = fields.Integer(string='Tenant Final Inspection (Days)')
    tenant_final_inspection_date = fields.Date(string='Tenant Final Inspection Date')

    # Conceptual Design Fields
    concept_briefing_days = fields.Integer(string='Concept Briefing (Days)')
    concept_briefing_date = fields.Date(string='Concept Briefing Date')
    concept_presentation_days = fields.Integer(string='Concept Presentation (Days)')
    concept_presentation_date = fields.Date(string='Concept Presentation Date')
    concept_approval_days = fields.Integer(string='Concept Approval (Days)')
    concept_approval_date = fields.Date(string='Concept Approval Date')
    concept_revision_days = fields.Integer(string='Concept Revision (Days)')
    concept_revision_date = fields.Date(string='Concept Revision Date')

    @api.depends('unit_no', 'development')
    def _compute_form_name(self):
        for record in self:
            if record.unit_no and record.development:
                record.form_name = f"PTL - {record.development} - {record.unit_no}"
            else:
                record.form_name = "New PTL Form"

    @api.depends('ptl_section_status', 'critical_path_section_status', 'tenant_appointment_section_status', 'conceptual_design_section_status')
    def _compute_global_status(self):
        for record in self:
            # Auto-compute global status based on section approvals
            if record.conceptual_design_section_status == 'approved':
                record.global_status = 'handover'
            elif record.tenant_appointment_section_status == 'approved':
                record.global_status = 'site_inspection_submission'
            elif record.critical_path_section_status == 'approved':
                record.global_status = 'noc'
            elif record.ptl_section_status == 'approved':
                record.global_status = 'form_verification'
            else:
                record.global_status = 'ptl'

    def action_approve_ptl_section(self):
        return self._show_approval_wizard('PTL Section', 'approve')

    def action_reject_ptl_section(self):
        return self._show_approval_wizard('PTL Section', 'reject')

    def action_approve_critical_path_section(self):
        return self._show_approval_wizard('Critical Path Section', 'approve')

    def action_reject_critical_path_section(self):
        return self._show_approval_wizard('Critical Path Section', 'reject')

    def action_approve_tenant_appointment_section(self):
        return self._show_approval_wizard('Tenant Appointment Section', 'approve')

    def action_reject_tenant_appointment_section(self):
        return self._show_approval_wizard('Tenant Appointment Section', 'reject')

    def action_approve_conceptual_design_section(self):
        return self._show_approval_wizard('Conceptual Design Section', 'approve')

    def action_reject_conceptual_design_section(self):
        return self._show_approval_wizard('Conceptual Design Section', 'reject')

    # Document View Actions for Conceptual Design Tab
    def action_view_drawing_pdf(self):
        """View 1 set of all drawings - softcopy in PDF format"""
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Document Viewer'),
                'message': _('Opening drawings PDF document...'),
                'type': 'info',
            }
        }

    def action_view_tvr_form(self):
        """View Tenant Variation Request (TVR – Form 09)"""
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Document Viewer'),
                'message': _('Opening TVR Form 09 document...'),
                'type': 'info',
            }
        }

    def action_view_furniture_layout(self):
        """View Furniture layout plan-with merchandising and services"""
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Document Viewer'),
                'message': _('Opening furniture layout plan document...'),
                'type': 'info',
            }
        }

    def action_view_shopfront_3d(self):
        """View Shop front -with signage-3D Image-in colour"""
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Document Viewer'),
                'message': _('Opening shop front 3D image document...'),
                'type': 'info',
            }
        }

    def action_view_shopfront_elevation(self):
        """View Shop front Elevation- with SIGNAGE"""
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Document Viewer'),
                'message': _('Opening shop front elevation document...'),
                'type': 'info',
            }
        }

    def action_view_3d_interior(self):
        """View 3D Image in colored - interior*"""
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Document Viewer'),
                'message': _('Opening 3D interior image document...'),
                'type': 'info',
            }
        }

    def action_view_concept_photos(self):
        """View Photos of previous shops or anything that helps explain the concept"""
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Document Viewer'),
                'message': _('Opening concept photos document...'),
                'type': 'info',
            }
        }

    def _show_approval_wizard(self, section_name, action_type):
        return {
            'type': 'ir.actions.act_window',
            'name': f'{action_type.title()} {section_name}',
            'res_model': 'ptl.approval.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_ptl_form_id': self.id,
                'default_section_name': section_name,
                'default_action_type': action_type,
            }
        }

    @api.model_create_multi
    def create(self, vals_list):
        return super().create(vals_list)


class PTLApprovalWizard(models.TransientModel):
    _name = 'ptl.approval.wizard'
    _description = 'PTL Approval/Rejection Wizard'

    ptl_form_id = fields.Many2one('ptl.form', string='PTL Form', required=True)
    section_name = fields.Char(string='Section Name', required=True)
    action_type = fields.Selection([
        ('approve', 'Approve'),
        ('reject', 'Reject')
    ], string='Action Type', required=True)
    comments = fields.Text(string='Comments', required=True)

    def action_confirm(self):
        self.ensure_one()
        
        # Map section names to field names
        section_field_map = {
            'PTL Section': 'ptl_section_status',
            'Critical Path Section': 'critical_path_section_status',
            'Tenant Appointment Section': 'tenant_appointment_section_status',
            'Conceptual Design Section': 'conceptual_design_section_status',
        }
        
        field_name = section_field_map.get(self.section_name)
        if field_name:
            new_status = 'approved' if self.action_type == 'approve' else 'rejected'
            self.ptl_form_id.write({field_name: new_status})
            
            # Log the action in chatter
            message = f"{self.section_name} {self.action_type}d with comments: {self.comments}"
            self.ptl_form_id.message_post(body=message, message_type='comment')
        
        return {'type': 'ir.actions.act_window_close'} 