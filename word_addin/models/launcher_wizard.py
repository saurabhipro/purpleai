# -*- coding: utf-8 -*-
from odoo import models, fields, _

class WordAddinLauncherWizard(models.TransientModel):
    _name = 'word_addin.launcher_wizard'
    _description = 'Word Add-in Launcher'

    manifest_url = fields.Char(string='Manifest URL', readonly=True)
    step_num = fields.Char(string='Step Number', readonly=True)
    session_id = fields.Integer(string='Session ID', readonly=True)

    def action_download_manifest(self):
        """Build and return the manifest download URL."""
        return {
            'type': 'ir.actions.act_url',
            'url': f'/word_addin/manifest.xml?session_id={self.session_id}&step_num={self.step_num}',
            'target': 'self',
        }
