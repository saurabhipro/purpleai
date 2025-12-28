from odoo import models, fields, api

class LoadSettingsWizard(models.TransientModel):
    _name = 'my.ai.load.settings.wizard'
    _description = 'Load MyAI Settings'

    def action_load_settings(self):
        """Load or create settings record"""
        settings = self.env['my.ai.settings'].get_settings()
        return {
            'type': 'ir.actions.act_window',
            'name': 'MyAI Settings',
            'res_model': 'my.ai.settings',
            'res_id': settings.id,
            'view_mode': 'form',
            'target': 'current',
        }

