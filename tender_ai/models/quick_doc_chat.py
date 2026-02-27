# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
import base64
import logging

_logger = logging.getLogger(__name__)

class QuickDocChat(models.Model):
    _name = 'tende_ai.quick_doc_chat'
    _description = 'Quick Document Chat'
    _order = 'create_date desc'

    name = fields.Char(string='Chat Topic', required=True, default="New Chat")
    file = fields.Binary(string='Upload Document', attachment=True)
    filename = fields.Char(string='Filename')
    
    kb_text = fields.Text(string='Extracted Text')
    kb_state = fields.Selection([('empty', 'Empty'), ('processed', 'Processed')], default='empty')
    
    chat_question = fields.Char(string="Message")
    chat_message_ids = fields.One2many('tende_ai.quick_doc_chat_message', 'chat_id', string='History')

    @api.onchange('file')
    def _onchange_file(self):
        if self.file and self.filename:
            self.name = self.filename.split('.')[0]
            # Automatically process when file is uploaded
            self.action_process_document()

    def action_process_document(self):
        self.ensure_one()
        if not self.file:
            return
        
        try:
            import fitz
            doc = fitz.open(stream=base64.b64decode(self.file), filetype="pdf")
            text = "\n".join([page.get_text() for page in doc]).strip()
            
            if len(text) < 150:
                # OCR Fallback
                from ..services.gemini_service import generate_with_gemini, upload_file_to_gemini
                import tempfile
                import os
                
                with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
                    tmp.write(base64.b64decode(self.file))
                    tmp_path = tmp.name
                
                try:
                    uploaded = upload_file_to_gemini(tmp_path, env=self.env)
                    res = generate_with_gemini(["Transcribe this PDF exactly."], model="gemini-1.5-flash", env=self.env)
                    text = (res.get('text') if isinstance(res, dict) else str(res)).strip()
                finally:
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)

            self.write({
                'kb_text': text,
                'kb_state': 'processed' if text else 'empty'
            })
        except Exception as e:
            _logger.error("Quick Chat Processing Error: %s", str(e))

    def action_send_message(self):
        self.ensure_one()
        if not self.chat_question:
            return
        
        from ..services.gemini_service import generate_with_gemini
        
        history = []
        for m in self.chat_message_ids[-15:]:
            history.append(f"{m.role.upper()}: {m.content}")
        history_text = "\n".join(history)

        if not self.kb_text:
            self.write({
                'chat_message_ids': [
                    (0, 0, {'role': 'assistant', 'content': _("Document text is missing. Please make sure the PDF has extracted text or try re-processing.")})
                ]
            })
            return

        prompt = (
            "You are a helpful Document Assistant. Use the context below to answer.\n\n"
            f"CONTEXT:\n{(self.kb_text or '')[:30000]}\n\n"
            f"HISTORY:\n{history_text}\n\n"
            f"USER: {self.chat_question}"
        )

        try:
            res = generate_with_gemini(prompt, model="gemini-3-flash-preview", temperature=0.3, env=self.env)
            answer = res.get('text') if isinstance(res, dict) else str(res)
            
            self.write({
                'chat_message_ids': [
                    (0, 0, {'role': 'user', 'content': self.chat_question}),
                    (0, 0, {'role': 'assistant', 'content': answer})
                ],
                'chat_question': False
            })
        except Exception as e:
            _logger.error("Chat Error: %s", str(e))

    def action_clear_chat(self):
        self.chat_message_ids.unlink()

class QuickDocChatMessage(models.Model):
    _name = 'tende_ai.quick_doc_chat_message'
    _description = 'Quick Chat History'
    _order = 'create_date asc'

    chat_id = fields.Many2one('tende_ai.quick_doc_chat', ondelete='cascade')
    role = fields.Selection([('user', 'User'), ('assistant', 'Assistant')], required=True)
    content = fields.Text(required=True)
