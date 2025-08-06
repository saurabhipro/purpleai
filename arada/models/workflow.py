from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class Workflow(models.Model):
    _name = 'arada_workflow'
    _description = 'Arada Workflow'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    name = fields.Char(string='Workflow Name', required=True, tracking=True)
    description = fields.Text(string='Description', required=True, tracking=True)
    status = fields.Boolean(string='Active', default=True, tracking=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    workflow_type = fields.Selection([
        ('tenant_approval', 'Tenant Approval Workflow'),
        ('design_approval', 'Design Approval Workflow'),
        ('construction_approval', 'Construction Approval Workflow'),
        ('inspection_workflow', 'Inspection Workflow'),
        ('custom', 'Custom Workflow')
    ], string='Workflow Type', required=True, tracking=True)

class WorkflowState(models.Model):
    _name = 'arada_workflow_state'
    _description = 'Workflow State'
    _order = 'sequence'
    
    workflow_id = fields.Many2one('arada_workflow', string='Workflow', required=True, ondelete='cascade')
    state_name = fields.Char(string='State Name', required=True)
    state_enum = fields.Selection([
        ('draft', 'Draft'),
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('under_review', 'Under Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled')
    ], string='State Enum', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    is_initial = fields.Boolean(string='Initial State', default=False)
    is_final = fields.Boolean(string='Final State', default=False)

class WorkflowAction(models.Model):
    _name = 'arada_workflow_action'
    _description = 'Workflow Action'
    
    action_name = fields.Char(string='Action Name', required=True)
    action_type = fields.Selection([
        ('approve', 'Approve'),
        ('reject', 'Reject'),
        ('submit', 'Submit'),
        ('review', 'Review'),
        ('return', 'Return for Revision'),
        ('complete', 'Complete'),
        ('cancel', 'Cancel'),
        ('custom', 'Custom Action')
    ], string='Action Type', required=True)
    phase = fields.Selection([
        ('submission', 'Submission Phase'),
        ('review', 'Review Phase'),
        ('approval', 'Approval Phase'),
        ('execution', 'Execution Phase'),
        ('completion', 'Completion Phase')
    ], string='Phase')
    description = fields.Text(string='Description')

class WorkflowStateTransition(models.Model):
    _name = 'arada_workflow_state_transition'
    _description = 'Workflow State Transition'
    
    workflow_id = fields.Many2one('arada_workflow', string='Workflow', required=True, ondelete='cascade')
    current_state_id = fields.Many2one('arada_workflow_state', string='Current State', required=True, ondelete='cascade')
    action_id = fields.Many2one('arada_workflow_action', string='Action', required=True, ondelete='cascade')
    next_state_id = fields.Many2one('arada_workflow_state', string='Next State', ondelete='cascade')
    additional_condition = fields.Text(string='Additional Condition')
    action_owner = fields.Selection([
        ('tenant', 'Tenant'),
        ('contractor', 'Contractor'),
        ('rdd', 'RDD Team'),
        ('mep', 'MEP Team'),
        ('management', 'Management'),
        ('system', 'System')
    ], string='Action Owner', required=True)