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
    test_file_ids = fields.One2many('tende_ai.extraction_test_file', 'master_id', string='Test Files')
    test_pdf_file = fields.Binary(string='Test PDF File (Single)')
    test_pdf_filename = fields.Char(string='Test PDF Filename')
    test_pdf_highlighted = fields.Binary(string='Highlighted PDF', readonly=True)
    test_result_ids = fields.One2many('tende_ai.extraction_test_result', 'master_id', string='Test Results')

    # Knowledge Base & Chat
    kb_text = fields.Html(string='Full Document Text (KB)', help="Automatically extracted text stored locally for chat")
    kb_state = fields.Selection([('empty', 'Empty'), ('indexed', 'Indexed')], default='empty', string="KB State")
    
    chat_question = fields.Char(string="Ask a Question about the Document")
    chat_answer = fields.Text(string="AI Answer", readonly=True)
    chat_message_ids = fields.One2many('tende_ai.extraction_master_chat_message', 'master_id', string='Chat History')

    def action_run_test_extraction(self):
        self.ensure_one()
        
        # Get all files (new relation + legacy single field)
        files_to_test = []
        if self.test_pdf_file:
            files_to_test.append({
                'content': self.test_pdf_file,
                'name': self.test_pdf_filename or 'test.pdf'
            })
        for f in self.test_file_ids:
            files_to_test.append({
                'content': f.file,
                'name': f.filename or 'test.pdf'
            })

        if not files_to_test:
            from odoo.exceptions import UserError
            raise UserError(_("Please upload at least one PDF file to test."))

        import base64
        import tempfile
        import os
        from ..services.company_parser import _extract_from_single_pdf
        from ..services.gemini_service import get_configured_model

        # Clear old results
        self.test_result_ids.unlink()

        import fitz
        import logging
        import unicodedata
        _logger = logging.getLogger(__name__)

        all_results = []
        active_fields = self.field_ids.filtered(lambda f: f.active)
        if not active_fields and not files_to_test:
            return

        prompts = []
        for f in active_fields:
            prompts.append(f"- key: {f.field_key}, label: {f.name}, instruction: {f.instruction}")
        custom_fields_prompt = "\n".join(prompts)
        model = get_configured_model(self.env)

        merged_doc = fitz.open()
        global_page_offset = 0
        total_kb_html = []
        
        for file_info in files_to_test:
            # Create temp file
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
                content_bytes = base64.b64decode(file_info['content'])
                tmp.write(content_bytes)
                tmp_path = tmp.name

            try:
                # Call extraction service for this PDF
                res = _extract_from_single_pdf(
                    company_name="Test Extraction",
                    pdf_path=tmp_path,
                    model=model,
                    env=self.env,
                    custom_fields_prompt=custom_fields_prompt
                )

                results = res.get("customExtractions") or []
                for r in results:
                    field = active_fields.filtered(lambda f: f.field_key == r.get('fieldKey'))
                    if field:
                        all_results.append((0, 0, {
                            'field_id': field[0].id,
                            'value': r.get('value'),
                            'page': r.get('page'),
                            'paragraph': r.get('paragraph'),
                        }))

                # KB Text Extraction for this file
                doc = fitz.open(stream=content_bytes, filetype="pdf")
                file_text = []
                for page in doc:
                    file_text.append(page.get_text())
                
                extracted_text = "\n".join(file_text).strip()
                # Fallback for scanned
                if len(extracted_text) < 150:
                    from ..services.gemini_service import generate_with_gemini, upload_file_to_gemini, get_configured_model
                    ocr_prompt = "Transcribe all text from this PDF exactly."
                    uploaded = upload_file_to_gemini(tmp_path, env=self.env)
                    ocr_res = generate_with_gemini([ocr_prompt, uploaded], model=model, env=self.env)
                    extracted_text = (ocr_res.get('text') if isinstance(ocr_res, dict) else str(ocr_res)).strip()
                
                if extracted_text:
                    safe_text = extracted_text.replace("<", "&lt;").replace(">", "&gt;")
                    total_kb_html.append(
                        f"<div class='kb_section' style='margin-bottom: 20px; border: 1px solid #dee2e6; border-radius: 4px; overflow: hidden;'>"
                        f"  <div style='background: #e9ecef; padding: 8px 12px; border-bottom: 1px solid #dee2e6; font-weight: bold; color: #495057;'>"
                        f"    <i class='fa fa-file-pdf-o'></i> SOURCE: {file_info['name']}"
                        f"  </div>"
                        f"  <div style='padding: 15px; background: #fff; font-family: \"Courier New\", Courier, monospace; white-space: pre-wrap; font-size: 13px; line-height: 1.5; color: #333;'>"
                        f"    {safe_text}"
                        f"  </div>"
                        f"</div>"
                    )

                # Merge into main display PDF and apply highlights
                current_file_page_count = doc.page_count
                merged_doc.insert_pdf(doc)
                
                # Highlight logic for this file on the correct global pages
                for r in results:
                    page_str = r.get('page')
                    if page_str and str(page_str).isdigit():
                        rel_page_idx = int(page_str) - 1
                        if 0 <= rel_page_idx < current_file_page_count:
                            # Load page from merged doc using offset
                            abs_page_idx = global_page_offset + rel_page_idx
                            page = merged_doc.load_page(abs_page_idx)
                            val = r.get('value')
                            if val and len(str(val)) > 1:
                                search_val = unicodedata.normalize('NFKC', str(val)).strip()
                                rects = page.search_for(search_val)
                                if not rects and " " in search_val:
                                    for word in search_val.split():
                                        if len(word) > 2: rects.extend(page.search_for(word))
                                for rect in rects[:20]:
                                    try: page.add_highlight_annot(rect)
                                    except Exception: pass
                
                global_page_offset += current_file_page_count

            except Exception as e:
                _logger.warning("Processing test file failed: %s", str(e))
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)

        # Finalize results
        write_vals = {
            'test_result_ids': all_results,
            'kb_text': "".join(total_kb_html),
            'kb_state': 'indexed' if total_kb_html else 'empty'
        }
        if merged_doc.page_count > 0:
            write_vals['test_pdf_highlighted'] = base64.b64encode(merged_doc.tobytes(garbage=4, deflate=True))
        
        self.write(write_vals)

    def action_doc_chat(self):
        self.ensure_one()
        if not self.chat_question:
            return
        if not self.kb_text:
            self.chat_answer = _("Knowledge Base is empty. Please run a test extraction first to index the document.")
            return

        from ..services.gemini_service import generate_with_gemini, get_configured_model
        
        # Build history string
        history = []
        for msg in self.chat_message_ids[-10:]:
            history.append(f"{msg.role.upper()}: {msg.content}")
        history_text = "\n".join(history) if history else "No history yet."

        from odoo.tools import html2plaintext
        
        system_prompt = (
            "You are a helpful document assistant. "
            "Below is the FULL TEXT of a tender document stored in Odoo. "
            "Use ONLY this text to answer the question. "
            "If you don't know the answer, say you couldn't find it in the document. "
            "Maintain a professional and conversational tone."
        )
        
        # Convert HTML to plaintext for AI
        plain_kb = html2plaintext(self.kb_text)
        
        prompt = (
            f"{system_prompt}\n\n"
            f"DOCUMENT CONTENT (CONTEXT):\n{plain_kb[:30000]}\n\n"
            f"PREVIOUS CHAT HISTORY:\n{history_text}\n\n"
            f"USER FOLLOW-UP QUESTION: {self.chat_question}"
        )
        
        try:
            model = get_configured_model(self.env)
            res = generate_with_gemini(
                contents=prompt,
                model=model,
                temperature=0.3,
                env=self.env
            )
            answer = res.get('text') if isinstance(res, dict) else res
            
            # Save to history
            self.write({
                'chat_message_ids': [
                    (0, 0, {'role': 'user', 'content': self.chat_question}),
                    (0, 0, {'role': 'assistant', 'content': answer})
                ],
                'chat_answer': answer, # Keep for the main view result
                'chat_question': False # Clear input for next question
            })
        except Exception as e:
            self.chat_answer = _("Chat error: %s") % str(e)

    def action_clear_chat(self):
        self.chat_message_ids.unlink()
        self.chat_answer = False
        self.chat_question = False

    def action_clear_kb(self):
        self.write({
            'kb_text': False,
            'kb_state': 'empty',
            'chat_question': False,
            'chat_answer': False,
            'test_pdf_highlighted': False,
            'test_result_ids': [(5, 0, 0)],
            'chat_message_ids': [(5, 0, 0)]
        })

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

class ExtractionMasterChatMessage(models.Model):
    _name = 'tende_ai.extraction_master_chat_message'
    _description = 'Extraction Master Chat History'
    _order = 'create_date asc'

    master_id = fields.Many2one('tende_ai.extraction_master', string='Master', required=True, ondelete='cascade')
    role = fields.Selection([('user', 'User'), ('assistant', 'AI')], string="Role", required=True)
    content = fields.Text(string="Message content", required=True)

class ExtractionTestFile(models.Model):
    _name = 'tende_ai.extraction_test_file'
    _description = 'Extraction Test File'

    master_id = fields.Many2one('tende_ai.extraction_master', string='Master')
    file = fields.Binary(string='PDF File', required=True)
    filename = fields.Char(string='Filename')
