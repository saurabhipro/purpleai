from odoo import models, fields, api

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    audit_reminder_enabled = fields.Boolean(string="Enable Task Reminders", config_parameter='audit_tool.reminder_enabled')
    audit_reminder_frequency = fields.Integer(string="Reminder Frequency (Days)", default=1, config_parameter='audit_tool.reminder_frequency', help="Send reminders every X days to users with pending tasks.")
