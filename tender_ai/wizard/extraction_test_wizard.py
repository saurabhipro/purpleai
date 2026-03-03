# -*- coding: utf-8 -*-

import base64
import os
import tempfile
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from ..services.company_parser import _extract_from_single_pdf
from ..services.gemini_service import get_configured_model

class ExtractionTestWizard(models.TransientModel):
    _name = 'tende_ai.extraction_test_wizard'
    _description = 'Test Custom Extraction'

    field_id = fields.Many2one('tende_ai.extraction_field', string='Field to Test', required=True)
    pdf_file = fields.Binary(string='PDF File', required=True)
    pdf_filename = fields.Char(string='PDF Filename')
    
    result_value = fields.Text(string='Extracted Value', readonly=True)
    result_page = fields.Char(string='Page', readonly=True)
    result_para = fields.Text(string='Source Paragraph', readonly=True)
    
    state = fields.Selection([('draft', 'Draft'), ('done', 'Done')], default='draft')

    def action_test(self):
        self.ensure_one()
        if not self.pdf_filename or not self.pdf_filename.lower().endswith('.pdf'):
            raise ValidationError(_("Please upload a PDF file."))

        # Create a temporary file
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            tmp.write(base64.b64decode(self.pdf_file))
            tmp_path = tmp.name

        try:
            custom_fields_prompt = f"- key: {self.field_id.field_key}, label: {self.field_id.name}, instruction: {self.field_id.instruction}"
            model = get_configured_model(self.env)
            
            # Call extraction service
            res = _extract_from_single_pdf(
                company_name="Test Company",
                pdf_path=tmp_path,
                model=model,
                env=self.env,
                custom_fields_prompt=custom_fields_prompt
            )
            
            custom_ext = res.get("customExtractions") or []
            found = False
            for ce in custom_ext:
                if ce.get('fieldKey') == self.field_id.field_key:
                    self.write({
                        'result_value': ce.get('value'),
                        'result_page': ce.get('page'),
                        'result_para': ce.get('paragraph'),
                        'state': 'done'
                    })
                    found = True
                    break
            
            if not found:
                self.write({
                    'result_value': _("Field not found in document."),
                    'state': 'done'
                })

        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
