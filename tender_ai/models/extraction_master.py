# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class ExtractionMaster(models.Model):
    _name = 'tende_ai.extraction_master'
    _description = 'Custom Extraction Group'
    _order = 'name'

    name = fields.Char(string='Document Group Name', required=True, help="e.g. Financial Documents, Technical Bid")
    document_type = fields.Selection([
        ('tender', 'Tender Document (tender.pdf)'),
        ('bidder', 'Bidder Documents (Company folders)')
    ], string='Applies To', default='bidder', required=True)
    
    field_ids = fields.One2many('tende_ai.extraction_field', 'master_id', string='Extraction Fields')
    active = fields.Boolean(default=True)

    # Test Fields
    test_pdf_file = fields.Binary(string='Test PDF File')
    test_pdf_filename = fields.Char(string='Test PDF Filename')
    test_pdf_highlighted = fields.Binary(string='Highlighted PDF', readonly=True)
    test_result_ids = fields.One2many('tende_ai.extraction_test_result', 'master_id', string='Test Results')

    def action_run_test_extraction(self):
        self.ensure_one()
        if not self.test_pdf_file:
            from odoo.exceptions import UserError
            raise UserError(_("Please upload a PDF file to test."))

        import base64
        import tempfile
        import os
        from ..services.company_parser import _extract_from_single_pdf

        # Clear old results
        self.test_result_ids.unlink()

        # Create temp file
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            tmp.write(base64.b64decode(self.test_pdf_file))
            tmp_path = tmp.name

        try:
            # Build custom fields prompt for all active fields
            active_fields = self.field_ids.filtered(lambda f: f.active)
            if not active_fields:
                return

            prompts = []
            for f in active_fields:
                prompts.append(f"- key: {f.field_key}, label: {f.name}, instruction: {f.instruction}")
            
            custom_fields_prompt = "\n".join(prompts)
            model = "gemini-3-flash-preview"

            # Call service
            res = _extract_from_single_pdf(
                company_name="Test Extraction",
                pdf_path=tmp_path,
                model=model,
                env=self.env,
                custom_fields_prompt=custom_fields_prompt
            )

            results = res.get("customExtractions") or []
            test_vals = []
            for r in results:
                # Find field_id by key
                field = active_fields.filtered(lambda f: f.field_key == r.get('fieldKey'))
                if field:
                    test_vals.append((0, 0, {
                        'field_id': field[0].id,
                        'value': r.get('value'),
                        'page': r.get('page'),
                        'paragraph': r.get('paragraph'),
                    }))
            
            if test_vals:
                self.write({'test_result_ids': test_vals})

                # Highlight PDF results
                try:
                    import fitz
                    import logging
                    import unicodedata
                    _logger = logging.getLogger(__name__)

                    pdf_data = base64.b64decode(self.test_pdf_file)
                    doc = fitz.open(stream=pdf_data, filetype="pdf")
                    
                    found_any = False
                    for r in results:
                        page_str = r.get('page')
                        if page_str and str(page_str).isdigit():
                            page_idx = int(page_str) - 1
                            if 0 <= page_idx < doc.page_count:
                                page = doc.load_page(page_idx)
                                
                                # 1. Try to find and highlight the value
                                val = r.get('value')
                                if val and len(str(val)) > 1:
                                    search_val = unicodedata.normalize('NFKC', str(val)).strip()
                                    rects = page.search_for(search_val)
                                    
                                    # If multi-word search failed, try words individually
                                    if not rects and " " in search_val:
                                        for word in search_val.split():
                                            if len(word) > 2:
                                                rects.extend(page.search_for(word))
                                    
                                    for rect in rects[:20]:
                                        try:
                                            page.add_highlight_annot(rect)
                                            found_any = True
                                        except Exception:
                                            pass
                                
                                # 2. Also try paragraph fragment for context
                                paragraph = r.get('paragraph')
                                if paragraph and len(str(paragraph)) > 10:
                                    # Try a few fragments of the paragraph
                                    para_clean = unicodedata.normalize('NFKC', str(paragraph)).strip()
                                    # Get first 40 chars, skipping common small words if possible
                                    fragment = para_clean[:40]
                                    rects = page.search_for(fragment)
                                    
                                    # If first fragment failed, try moving a bit forward
                                    if not rects and len(para_clean) > 80:
                                        fragment2 = para_clean[40:80]
                                        rects = page.search_for(fragment2)
                                        
                                    for rect in rects[:10]:
                                        try:
                                            page.add_highlight_annot(rect)
                                            found_any = True
                                        except Exception:
                                            pass
                    
                    if found_any:
                        out_pdf = doc.tobytes(garbage=4, deflate=True)
                        self.test_pdf_highlighted = base64.b64encode(out_pdf)
                        _logger.info("AI Extraction: PDF highlighted successfully (%d hits)", found_any)
                    else:
                        self.test_pdf_highlighted = self.test_pdf_file
                        _logger.warning("AI Extraction: No matches found in PDF for highlighting")
                except ImportError:
                    import logging
                    logging.getLogger(__name__).error("PDF Highlighting failed: 'fitz' (PyMuPDF) not installed in Odoo environment.")
                    self.test_pdf_highlighted = self.test_pdf_file
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).warning("PDF Highlighting failed: %s", str(e))
                    self.test_pdf_highlighted = self.test_pdf_file

        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

class ExtractionField(models.Model):
    _name = 'tende_ai.extraction_field'
    _description = 'Custom Extraction Field'
    _order = 'sequence, id'

    master_id = fields.Many2one('tende_ai.extraction_master', string='Master', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    name = fields.Char(string='Field Label', required=True)
    field_key = fields.Char(string='Field Key (JSON)', required=True, help="Unique technical name for AI extraction")
    instruction = fields.Text(string='Extraction Instruction', required=True, help="AI prompt instruction on how to find this data")
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('field_key_unique', 'unique(field_key)', 'The field key must be unique!')
    ]

class ExtractionTestResult(models.Model):
    _name = 'tende_ai.extraction_test_result'
    _description = 'Extraction Test Result'
    _order = 'id'

    master_id = fields.Many2one('tende_ai.extraction_master', string='Master', required=True, ondelete='cascade')
    field_id = fields.Many2one('tende_ai.extraction_field', string='Field')
    field_name = fields.Char(related='field_id.name', string='Field Name')
    value = fields.Text(string='Extracted Value')
    page = fields.Char(string='Page')
    paragraph = fields.Text(string='Source Context')
