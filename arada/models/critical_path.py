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