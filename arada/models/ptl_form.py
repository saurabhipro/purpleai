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
    
    # Simplified Global Workflow Status
    global_status = fields.Selection([
        ('ptl', 'PTL'),
        ('in_progress', 'In Progress'), 
        ('completed', 'Completed')
    ], string='Global Status', default='ptl', tracking=True, compute='_compute_global_status', store=True)
    
    # Section-specific statuses (NEW, PENDING, APPROVED)
    ptl_section_status = fields.Selection([
        ('new', 'NEW'),
        ('pending', 'PENDING'), 
        ('approved', 'APPROVED')
    ], string='PTL Section Status', default='new')
    
    critical_path_section_status = fields.Selection([
        ('new', 'NEW'),
        ('pending', 'PENDING'),
        ('approved', 'APPROVED')
    ], string='Critical Path Section Status', default='new')

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

    @api.depends('ptl_section_status', 'critical_path_section_status')
    def _compute_global_status(self):
        """Auto-update global status based on section statuses"""
        for record in self:
            if record.ptl_section_status == 'approved' and record.critical_path_section_status == 'approved':
                record.global_status = 'completed'
            elif record.ptl_section_status == 'approved' or record.critical_path_section_status in ['pending', 'approved']:
                record.global_status = 'in_progress'
            else:
                record.global_status = 'ptl'

    def action_start_progress(self):
        self.ensure_one()
        self.ptl_section_status = 'pending'
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def action_approve(self):
        self.ensure_one()
        self.ptl_section_status = 'approved'
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def action_complete(self):
        self.ensure_one()
        self.critical_path_section_status = 'approved'
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def action_reset_to_draft(self):
        self.ensure_one()
        self.ptl_section_status = 'new'
        self.critical_path_section_status = 'new'
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def _valid_field_parameter(self, field, name):
        return name == 'placeholder' or super()._valid_field_parameter(field, name)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'ptl_form_id' in vals:
                ptl_form = self.env['ptl.form'].browse(vals['ptl_form_id'])
                ptl_form.critical_path_created = True
        return super().create(vals_list)


class PTLForm(models.Model):
    _name = 'ptl.form'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'PTL Form - Initial Notification Confirmed Offer'
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
    
    # Simplified Global Workflow Status (auto-computed)
    global_status = fields.Selection([
        ('ptl', 'PTL'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed')
    ], string='Global Status', default='ptl', tracking=True, compute='_compute_global_status', store=True)

    # Section-specific statuses (NEW, PENDING, APPROVED)
    ptl_section_status = fields.Selection([
        ('new', 'NEW'),
        ('pending', 'PENDING'), 
        ('approved', 'APPROVED')
    ], string='PTL Section Status', default='new', tracking=True)
    
    critical_path_section_status = fields.Selection([
        ('new', 'NEW'),
        ('pending', 'PENDING'),
        ('approved', 'APPROVED')
    ], string='Critical Path Section Status', default='new', tracking=True)

    # Critical Path Fields
    critical_path_created = fields.Boolean(string='Critical Path Created', default=False)
    
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

    # Financial Information
    late_opening_penalty = fields.Float(string='Late opening penalty (LOP) AED per calendar day', default=0.0)
    
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
                record.global_status = 'completed'
            elif record.ptl_section_status == 'approved' or record.critical_path_section_status in ['pending', 'approved']:
                record.global_status = 'in_progress'
            else:
                record.global_status = 'ptl'

    # Section-specific actions (keep these for tab-level status changes)
    def action_approve_ptl_section(self):
        """Approve PTL Section"""
        self.ensure_one()
        self.ptl_section_status = 'approved'
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def action_approve_critical_path_section(self):
        """Approve Critical Path Section"""
        self.ensure_one()
        self.critical_path_section_status = 'approved'
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def action_set_ptl_pending(self):
        """Set PTL Section to Pending"""
        self.ensure_one()
        self.ptl_section_status = 'pending'
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def action_set_critical_path_pending(self):
        """Set Critical Path Section to Pending"""
        self.ensure_one()
        self.critical_path_section_status = 'pending'
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    @api.model_create_multi
    def create(self, vals_list):
        return super().create(vals_list)

    def create_critical_path(self):
        """Create Critical Path for this PTL"""
        self.ensure_one()
        if not self.critical_path_created:
            critical_path = self.env['critical.path'].create({
                'ptl_form_id': self.id,
            })
            self.critical_path_created = True
            return {
                'type': 'ir.actions.act_window',
                'name': 'Critical Path',
                'res_model': 'critical.path',
                'res_id': critical_path.id,
                'view_mode': 'form',
                'target': 'current',
            }
        else:
            # Open existing critical path
            critical_path = self.env['critical.path'].search([('ptl_form_id', '=', self.id)], limit=1)
            if critical_path:
                return {
                    'type': 'ir.actions.act_window',
                    'name': 'Critical Path',
                    'res_model': 'critical.path',
                    'res_id': critical_path.id,
                    'view_mode': 'form',
                    'target': 'current',
                } 