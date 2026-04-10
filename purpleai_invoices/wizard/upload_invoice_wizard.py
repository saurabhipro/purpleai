# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import base64
import os
import tempfile
import logging

_logger = logging.getLogger(__name__)

class UploadInvoiceWizard(models.TransientModel):
    _name = 'purple_ai.upload_invoice_wizard'
    _description = 'Upload Invoices for AI Processing'

    # Filter clients that are active
    client_id = fields.Many2one('purple_ai.client', string='Client/Template Group', 
                                 required=True, domain=[('active', '=', True)])
    
    file_ids = fields.One2many('purple_ai.upload_invoice_file', 'wizard_id', string='Documents to Process')

    def action_process(self):
        self.ensure_one()
        if not self.file_ids:
            raise UserError(_("Please upload at least one file."))
        
        processed_count = 0
        for file_rec in self.file_ids:
            if not file_rec.file:
                continue
                
            # Create a real temp file on disk so Gemini can read it
            # The gemini_service expects a file path
            ext = os.path.splitext(file_rec.filename)[1] or '.pdf'
            fd, temp_path = tempfile.mkstemp(suffix=ext)
            
            try:
                with os.fdopen(fd, 'wb') as temp:
                    temp.write(base64.b64decode(file_rec.file))
                
                # Reuse the existing processing logic from ClientMaster
                _logger.info("Wizard: Processing uploaded file %s for client %s", file_rec.filename, self.client_id.name)
                self.client_id._process_one_file(temp_path, file_rec.filename)
                processed_count += 1
                
            except Exception as e:
                _logger.error("Wizard: Error processing file %s: %s", file_rec.filename, str(e))
                # We continue with other files even if one fails
            finally:
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except:
                        pass
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Processing Complete'),
                'message': _('Successfully submitted %d files for AI extraction.') % processed_count,
                'sticky': False,
                'type': 'success',
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }

class UploadInvoiceFile(models.TransientModel):
    _name = 'purple_ai.upload_invoice_file'
    _description = 'Temporary file storage for wizard'

    wizard_id = fields.Many2one('purple_ai.upload_invoice_wizard')
    file = fields.Binary(string='File (PDF)', required=True)
    filename = fields.Char(string='File Name')
