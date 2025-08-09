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

    # Conceptual Design Fields
    concept_briefing_days = fields.Integer(string='Concept Briefing (Days)')
    concept_briefing_date = fields.Date(string='Concept Briefing Date')
    concept_presentation_days = fields.Integer(string='Concept Presentation (Days)')
    concept_presentation_date = fields.Date(string='Concept Presentation Date')
    concept_approval_days = fields.Integer(string='Concept Approval (Days)')
    concept_approval_date = fields.Date(string='Concept Approval Date')
    concept_revision_days = fields.Integer(string='Concept Revision (Days)')
    concept_revision_date = fields.Date(string='Concept Revision Date')

    # TAR Details Fields (To be approved by lease signatory)
    # TAR Approval Required
    tar_approval_required = fields.Boolean(string='TAR Approval Required', default=False)

    # Primary Contact
    tar_primary_name = fields.Char(string='Primary Contact Name')
    tar_primary_designation = fields.Char(string='Primary Contact Designation')
    tar_primary_company = fields.Char(string='Primary Contact Company')
    tar_primary_telephone = fields.Char(string='Primary Contact Telephone')
    tar_primary_mobile = fields.Char(string='Primary Contact Mobile')
    tar_primary_email = fields.Char(string='Primary Contact Email')
    tar_primary_experience = fields.Text(string='Primary Contact Experience')

    # Secondary Contact
    tar_secondary_name = fields.Char(string='Secondary Contact Name')
    tar_secondary_designation = fields.Char(string='Secondary Contact Designation')
    tar_secondary_company = fields.Char(string='Secondary Contact Company')
    tar_secondary_telephone = fields.Char(string='Secondary Contact Telephone')
    tar_secondary_mobile = fields.Char(string='Secondary Contact Mobile')
    tar_secondary_email = fields.Char(string='Secondary Contact Email')
    tar_secondary_experience = fields.Text(string='Secondary Contact Experience')

    # TAR Confirmation Text
    tar_confirmation_text = fields.Text(string='TAR Confirmation', default="""We confirm that we have appointed the above person(s) to represent the tenant within the above discipline, who we confirm to have read and understood the tenant manual, logistic positions as well as any information as the lease related to the fit-out. We confirm our responsibility towards the quality of work on site of our appointed project teams as well as all agents and subcontractors. We shall ensure that they all comply with the rules and regulations, procedures of Arada and the local authorities - and that they execute work only in accordance with landlord approved drawings. Kindly direct all correspondence related to the fit out to the defined project representatives and grant them access to the site.""")

    # Tenant Designer
    tenant_designer_name = fields.Char(string='Tenant Designer Name')
    tenant_designer_company = fields.Char(string='Tenant Designer Company')
    tenant_designer_contact = fields.Char(string='Tenant Designer Contact Number')
    tenant_designer_email = fields.Char(string='Tenant Designer Email')
    tenant_designer_work_history = fields.Text(string='Tenant Designer Work History')

    # Tenant Contractor
    tenant_contractor_name = fields.Char(string='Tenant Contractor Name')
    tenant_contractor_company = fields.Char(string='Tenant Contractor Company')
    tenant_contractor_contact = fields.Char(string='Tenant Contractor Contact Number')
    tenant_contractor_email = fields.Char(string='Tenant Contractor Email')
    tenant_contractor_work_history = fields.Text(string='Tenant Contractor Work History')
    tenant_contractor_trade_license = fields.Binary(string='Trade License')
    tenant_contractor_trade_license_filename = fields.Char(string='Trade License Filename')
    tenant_contractor_company_profile = fields.Binary(string='Company Profile')
    tenant_contractor_company_profile_filename = fields.Char(string='Company Profile Filename')
    tenant_contractor_comments = fields.Text(string='Contractor Comments')

    # Contractor Disclaimer
    contractor_disclaimer_text = fields.Text(string='Contractor Disclaimer', default="""Appointed designers or contractors is solely a Tenant nomination. However, Arada reserves the right to reject a contractor on the bad historical performance. The appointment of any Tenant consultant and contractor remains tenants' responsibility at all times with no liability to Arada.""")

    # Conceptual Design Attachment Fields
    drawing_pdf_attachment = fields.Binary(string='Drawings PDF Attachment')
    drawing_pdf_filename = fields.Char(string='Drawings PDF Filename')
    drawing_pdf_status = fields.Selection([
        ('no_objection', 'No objection'),
        ('pending_review', 'Pending Review'),
        ('rejected', 'Rejected'),
        ('approved', 'Approved')
    ], string='Drawings PDF Status', default='no_objection')

    tvr_form_attachment = fields.Binary(string='TVR Form Attachment')
    tvr_form_filename = fields.Char(string='TVR Form Filename')
    tvr_form_status = fields.Selection([
        ('no_objection', 'No objection'),
        ('pending_review', 'Pending Review'),
        ('rejected', 'Rejected'),
        ('approved', 'Approved')
    ], string='TVR Form Status', default='no_objection')

    furniture_layout_attachment = fields.Binary(string='Furniture Layout Attachment')
    furniture_layout_filename = fields.Char(string='Furniture Layout Filename')
    furniture_layout_status = fields.Selection([
        ('no_objection', 'No objection'),
        ('pending_review', 'Pending Review'),
        ('rejected', 'Rejected'),
        ('approved', 'Approved')
    ], string='Furniture Layout Status', default='no_objection')

    shopfront_3d_attachment = fields.Binary(string='Shop Front 3D Attachment')
    shopfront_3d_filename = fields.Char(string='Shop Front 3D Filename')
    shopfront_3d_status = fields.Selection([
        ('no_objection', 'No objection'),
        ('pending_review', 'Pending Review'),
        ('rejected', 'Rejected'),
        ('approved', 'Approved')
    ], string='Shop Front 3D Status', default='no_objection')

    shopfront_elevation_attachment = fields.Binary(string='Shop Front Elevation Attachment')
    shopfront_elevation_filename = fields.Char(string='Shop Front Elevation Filename')
    shopfront_elevation_status = fields.Selection([
        ('no_objection', 'No objection'),
        ('pending_review', 'Pending Review'),
        ('rejected', 'Rejected'),
        ('approved', 'Approved')
    ], string='Shop Front Elevation Status', default='no_objection')

    interior_3d_attachment = fields.Binary(string='3D Interior Attachment')
    interior_3d_filename = fields.Char(string='3D Interior Filename')
    interior_3d_status = fields.Selection([
        ('no_objection', 'No objection'),
        ('pending_review', 'Pending Review'),
        ('rejected', 'Rejected'),
        ('approved', 'Approved')
    ], string='3D Interior Status', default='no_objection')

    concept_photos_attachment = fields.Binary(string='Concept Photos Attachment')
    concept_photos_filename = fields.Char(string='Concept Photos Filename')
    concept_photos_status = fields.Selection([
        ('no_objection', 'No objection'),
        ('pending_review', 'Pending Review'),
        ('rejected', 'Rejected'),
        ('approved', 'Approved')
    ], string='Concept Photos Status', default='no_objection')

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
        if self.drawing_pdf_attachment:
            return {
                'type': 'ir.actions.act_url',
                'url': f'/web/content/ptl.form/{self.id}/drawing_pdf_attachment/{self.drawing_pdf_filename or "drawing.pdf"}',
                'target': 'new',
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No Document'),
                    'message': _('No drawing PDF document has been uploaded yet.'),
                    'type': 'warning',
                }
            }

    def action_view_tvr_form(self):
        """View Tenant Variation Request (TVR – Form 09)"""
        self.ensure_one()
        if self.tvr_form_attachment:
            return {
                'type': 'ir.actions.act_url',
                'url': f'/web/content/ptl.form/{self.id}/tvr_form_attachment/{self.tvr_form_filename or "tvr_form.pdf"}',
                'target': 'new',
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No Document'),
                    'message': _('No TVR form document has been uploaded yet.'),
                    'type': 'warning',
                }
            }

    def action_view_furniture_layout(self):
        """View Furniture layout plan-with merchandising and services"""
        self.ensure_one()
        if self.furniture_layout_attachment:
            return {
                'type': 'ir.actions.act_url',
                'url': f'/web/content/ptl.form/{self.id}/furniture_layout_attachment/{self.furniture_layout_filename or "furniture_layout.pdf"}',
                'target': 'new',
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No Document'),
                    'message': _('No furniture layout document has been uploaded yet.'),
                    'type': 'warning',
                }
            }

    def action_view_shopfront_3d(self):
        """View Shop front -with signage-3D Image-in colour"""
        self.ensure_one()
        if self.shopfront_3d_attachment:
            return {
                'type': 'ir.actions.act_url',
                'url': f'/web/content/ptl.form/{self.id}/shopfront_3d_attachment/{self.shopfront_3d_filename or "shopfront_3d.pdf"}',
                'target': 'new',
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No Document'),
                    'message': _('No shop front 3D document has been uploaded yet.'),
                    'type': 'warning',
                }
            }

    def action_view_shopfront_elevation(self):
        """View Shop front Elevation- with SIGNAGE"""
        self.ensure_one()
        if self.shopfront_elevation_attachment:
            return {
                'type': 'ir.actions.act_url',
                'url': f'/web/content/ptl.form/{self.id}/shopfront_elevation_attachment/{self.shopfront_elevation_filename or "shopfront_elevation.pdf"}',
                'target': 'new',
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No Document'),
                    'message': _('No shop front elevation document has been uploaded yet.'),
                    'type': 'warning',
                }
            }

    def action_view_3d_interior(self):
        """View 3D Image in colored - interior*"""
        self.ensure_one()
        if self.interior_3d_attachment:
            return {
                'type': 'ir.actions.act_url',
                'url': f'/web/content/ptl.form/{self.id}/interior_3d_attachment/{self.interior_3d_filename or "interior_3d.pdf"}',
                'target': 'new',
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No Document'),
                    'message': _('No 3D interior document has been uploaded yet.'),
                    'type': 'warning',
                }
            }

    def action_view_concept_photos(self):
        """View Photos of previous shops or anything that helps explain the concept"""
        self.ensure_one()
        if self.concept_photos_attachment:
            return {
                'type': 'ir.actions.act_url',
                'url': f'/web/content/ptl.form/{self.id}/concept_photos_attachment/{self.concept_photos_filename or "concept_photos.pdf"}',
                'target': 'new',
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No Document'),
                    'message': _('No concept photos document has been uploaded yet.'),
                    'type': 'warning',
                }
            }

    def action_view_trade_license(self):
        """View Trade License Document"""
        self.ensure_one()
        if self.tenant_contractor_trade_license:
            return {
                'type': 'ir.actions.act_url',
                'url': f'/web/content/ptl.form/{self.id}/tenant_contractor_trade_license/{self.tenant_contractor_trade_license_filename or "trade_license.pdf"}',
                'target': 'new',
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No Document'),
                    'message': _('No trade license document has been uploaded yet.'),
                    'type': 'warning',
                }
            }

    def action_view_company_profile(self):
        """View Company Profile Document"""
        self.ensure_one()
        if self.tenant_contractor_company_profile:
            return {
                'type': 'ir.actions.act_url',
                'url': f'/web/content/ptl.form/{self.id}/tenant_contractor_company_profile/{self.tenant_contractor_company_profile_filename or "company_profile.pdf"}',
                'target': 'new',
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No Document'),
                    'message': _('No company profile document has been uploaded yet.'),
                    'type': 'warning',
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