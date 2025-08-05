from odoo import models, fields, api, _
from odoo.exceptions import UserError

class AradaWorkflow(models.Model):
    _name = 'arada.workflow'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'ARADA Workflow'

    approval_for = fields.Selection([
        ('ptl','PTL'),
        ('cp','Critical Path'),
        ('ta','Tenant Appointment'),
        ('cd','Conceptual Design'),
        ('ad','Arch Design'),
        ('md','MEP Design'),
        ('sa','Sample Approval'),
        ('pm','Pre Mob'),
    ], string="Approval for")
    user_id = fields.Many2one('res.users', string='User')