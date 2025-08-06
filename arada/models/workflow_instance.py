from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class WorkflowInstance(models.Model):
    _name = 'arada_workflow_instance'
    _description = 'Workflow Instance'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'
    
    name = fields.Char(string='Instance Name', required=True, tracking=True)
    workflow_id = fields.Many2one('arada_workflow', string='Workflow', required=True, tracking=True)
    current_state_id = fields.Many2one('arada_workflow_state', string='Current State', tracking=True)
    tenant_details_id = fields.Many2one('tenant.details', string='Related Tenant Details', tracking=True)
    
    status = fields.Selection([
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('suspended', 'Suspended')
    ], string='Status', default='active', tracking=True)
    
    start_date = fields.Datetime(string='Start Date', default=fields.Datetime.now, tracking=True)
    end_date = fields.Datetime(string='End Date', tracking=True)
    last_action_date = fields.Datetime(string='Last Action Date', tracking=True)

class WorkflowInstanceHistory(models.Model):
    _name = 'arada_workflow_instance_history'
    _description = 'Workflow Instance History'
    _order = 'execution_date desc'
    
    instance_id = fields.Many2one('arada_workflow_instance', string='Workflow Instance', required=True, ondelete='cascade')
    from_state_id = fields.Many2one('arada_workflow_state', string='From State')
    to_state_id = fields.Many2one('arada_workflow_state', string='To State')
    action_id = fields.Many2one('arada_workflow_action', string='Action')
    executed_by = fields.Many2one('res.users', string='Executed By')
    execution_date = fields.Datetime(string='Execution Date')
    notes = fields.Text(string='Notes') 