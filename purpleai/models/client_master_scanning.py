# -*- coding: utf-8 -*-
import os
import logging
from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)

class ClientMaster(models.Model):
    _inherit = 'purple_ai.client'

    def cron_scan_client_folders(self):
        """Cron entry point to scan all active client folders."""
        clients = self.search([('active', '=', True)])
        _logger.info("Cron: Scanning %d clients", len(clients))
        for client in clients:
            try:
                client.action_scan_folder()
            except Exception as e:
                _logger.error("Cron: Failed to scan client %s: %s", client.name, str(e))
                self.env.cr.rollback()

    def _update_scan_progress(self, vals):
        """Write scan progress fields in an isolated cursor to avoid serialization conflicts."""
        allowed = {'scan_status', 'scan_total', 'scan_count', 'scan_current_file', 'last_scan'}
        vals = {k: v for k, v in vals.items() if k in allowed}
        if not vals:
            return
        try:
            with self.pool.cursor() as cr:
                set_clause = ', '.join('"{}" = %s'.format(k) for k in vals)
                cr.execute(
                    'UPDATE purple_ai_client SET {} WHERE id = %s'.format(set_clause),
                    list(vals.values()) + [self.id]
                )
        except Exception as e:
            _logger.warning("Could not update scan progress for client %s: %s", self.id, str(e))

    def action_scan_folder(self):
        """Scans the client folder for new PDF files and processes them."""
        self.ensure_one()
        folder_path = (self.folder_path or '').strip()
        if not folder_path or not os.path.exists(folder_path):
            _logger.warning("Folder path %s not found for client %s", folder_path, self.name)
            return

        files = [f for f in os.listdir(folder_path) if f.lower().endswith('.pdf')]

        Result = self.env['purple_ai.extraction_result']
        files_to_process = []
        for filename in files:
            existing = Result.search([('client_id', '=', self.id), ('filename', '=', filename)], limit=1)
            if not existing:
                files_to_process.append(filename)

        if not files_to_process:
            _logger.info("Nothing to scan for client %s", self.name)
            return

        _logger.info("Scanning client %s folder [%s]: found %d new PDFs", self.name, folder_path, len(files_to_process))

        self._update_scan_progress({
            'scan_status': 'scanning',
            'scan_total': len(files_to_process),
            'scan_count': 0,
            'scan_current_file': 'Starting...',
        })
        self._send_scan_notification()

        from odoo.addons.purpleai.services import document_processing_service
        for i, filename in enumerate(files_to_process):
            self._update_scan_progress({
                'scan_count': i + 1,
                'scan_current_file': filename,
            })
            self._send_scan_notification()

            file_path = os.path.join(self.folder_path, filename)
            try:
                document_processing_service.process_document(self.env, self, file_path, filename)
            except Exception as e:
                _logger.error("Failed to process file %s for client %s: %s", filename, self.name, str(e))

        self._update_scan_progress({
            'scan_status': 'idle',
            'scan_count': len(files_to_process),
            'scan_current_file': 'Scanning Completed',
            'last_scan': fields.Datetime.now(),
        })
        self.env['purple_ai.client'].invalidate_model(['scan_status', 'scan_count', 'scan_current_file', 'last_scan'])
        self._send_scan_notification()

    def _send_scan_notification(self):
        """Sends a bus notification to update the UI."""
        self.ensure_one()
        msg = {
            'type': 'purple_ai_scan_progress',
            'client_id': self.id,
            'progress': self.scan_progress,
            'current_file': self.scan_current_file,
            'status': self.scan_status
        }
        self.env['bus.bus']._sendone(self.env.user.partner_id, 'purple_ai_notification', msg)
