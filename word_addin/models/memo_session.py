# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class MemoSession(models.Model):
    _inherit = 'memo_ai.session'

    def action_open_in_word_all(self):
        return self._show_word_modal('all')

    def action_open_in_word_step1(self):
        return self._show_word_modal('1')

    def action_open_in_word_step2(self):
        return self._show_word_modal('2')

    def action_open_in_word_step3(self):
        return self._show_word_modal('3')

    def action_open_in_word_step4(self):
        return self._show_word_modal('4')

    def _show_word_modal(self, step_num):
        """Silently store active session and notify user."""
        from odoo.http import request
        if request:
            # Magic Sync: Store values in our cookie-based Odoo session
            request.session['active_memo_session_id'] = self.id
            request.session['active_memo_session_step'] = step_num
        
        # Instead of opening a popup, we just show a subtle notification
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Magic Sync Active'),
                'message': _('Word is now linked to: %s') % self.name,
                'type': 'success',
                'sticky': False,
            }
        }

    def action_download_manifest_wizard(self):
        """Show the manifest download wizard (Setup)."""
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        manifest_url = f"{base_url}/word_addin/manifest.xml"
        return {
            'name': _('Word Add-in Setup'),
            'type': 'ir.actions.act_window',
            'res_model': 'word_addin.launcher_wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_manifest_url': manifest_url,
                'default_session_id': self.id
            }
        }
