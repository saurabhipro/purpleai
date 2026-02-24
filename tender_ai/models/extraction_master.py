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

    # Knowledge Base & Chat
    kb_text = fields.Text(string='Full Document Text (KB)', help="Automatically extracted text stored locally for chat")
    kb_state = fields.Selection([('empty', 'Empty'), ('indexed', 'Indexed')], default='empty', string="KB State")
    
    chat_question = fields.Char(string="Ask a Question about the Document")
    chat_answer = fields.Text(string="AI Answer", readonly=True)
    chat_message_ids = fields.One2many('tende_ai.extraction_master_chat_message', 'master_id', string='Chat History')

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

                # --- 1. Extract Full Text for Knowledge Base (if empty) ---
                try:
                    import fitz
                    pdf_data = base64.b64decode(self.test_pdf_file)
                    doc = fitz.open(stream=pdf_data, filetype="pdf")
                    full_text = []
                    for page in doc:
                        full_text.append(page.get_text())
                    
                    extracted_text = "\n".join(full_text).strip()
                    if len(extracted_text) < 150:
                        # FALLBACK: If PyMuPDF failed (likely scanned or complex font), use Gemini to read it
                        from ..services.gemini_service import generate_with_gemini, upload_file_to_gemini
                        _logger = logging.getLogger(__name__)
                        _logger.info("AI: PyMuPDF returned thin text. Falling back to Gemini Multimodal OCR for KB.")
                        
                        ocr_prompt = (
                            "Carefully read this entire document and transcribe all text content exactly. "
                            "Preserve the structure. If it's in Hindi, transcribe it in Hindi. "
                            "Output ONLY the transcribed text."
                        )
                        uploaded = upload_file_to_gemini(tmp_path, env=self.env)
                        ocr_res = generate_with_gemini(
                            contents=[ocr_prompt, uploaded],
                            model="gemini-1.5-flash",
                            env=self.env
                        )
                        if isinstance(ocr_res, dict):
                            extracted_text = ocr_res.get('text', '').strip()
                        else:
                            extracted_text = str(ocr_res).strip()
                    
                    self.write({
                        'kb_text': extracted_text,
                        'kb_state': 'indexed' if len(extracted_text) > 20 else 'empty'
                    })
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).warning("KB Extraction failed: %s", str(e))

                # --- 2. Highlight PDF results ---
                try:
                   # ... (existing highlighting code)
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
                                    fragment = para_clean[:40]
                                    rects = page.search_for(fragment)
                                    
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
                    else:
                        self.test_pdf_highlighted = self.test_pdf_file
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).warning("PDF Highlighting failed: %s", str(e))
                    self.test_pdf_highlighted = self.test_pdf_file

        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def action_doc_chat(self):
        self.ensure_one()
        if not self.chat_question:
            return
        if not self.kb_text:
            self.chat_answer = _("Knowledge Base is empty. Please run a test extraction first to index the document.")
            return

        from ..services.gemini_service import generate_with_gemini
        
        # Build history string
        history = []
        for msg in self.chat_message_ids[-10:]:
            history.append(f"{msg.role.upper()}: {msg.content}")
        history_text = "\n".join(history) if history else "No history yet."

        system_prompt = (
            "You are a helpful document assistant. "
            "Below is the FULL TEXT of a tender document stored in Odoo. "
            "Use ONLY this text to answer the question. "
            "If you don't know the answer, say you couldn't find it in the document. "
            "Maintain a professional and conversational tone."
        )
        
        prompt = (
            f"{system_prompt}\n\n"
            f"DOCUMENT CONTENT (CONTEXT):\n{self.kb_text[:30000]}\n\n"
            f"PREVIOUS CHAT HISTORY:\n{history_text}\n\n"
            f"USER FOLLOW-UP QUESTION: {self.chat_question}"
        )
        
        try:
            res = generate_with_gemini(
                contents=prompt,
                model="gemini-3-flash-preview",
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
