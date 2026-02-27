# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
import base64
import logging
import re
from markupsafe import Markup

_logger = logging.getLogger(__name__)

class DiscussChannel(models.Model):
    _inherit = 'discuss.channel'

    is_ai_kb_enabled = fields.Boolean(string='Enable AI Knowledge Base', default=False, 
                                     help="If enabled, any PDF uploaded here will be indexed and the AI will answer questions about it.")
    kb_text = fields.Text(string='Channel Indexed Text')
    kb_state = fields.Selection([('empty', 'Empty'), ('ready', 'Ready')], default='empty', string="Indexing Status")

    def _message_post_after_hook(self, message, values_list):
        res = super(DiscussChannel, self)._message_post_after_hook(message, values_list)
        
        # 1. Automatic Indexing when a PDF is uploaded to an AI-enabled channel
        if self.is_ai_kb_enabled:
            # Check for PDF in attachments
            pdf_attachments = message.attachment_ids.filtered(lambda a: 'pdf' in (a.mimetype or '').lower() or (a.name or '').lower().endswith('.pdf'))
            if pdf_attachments:
                _logger.info("AI Channel: Detected PDF upload in message %s, indexing...", message.id)
                self._index_pdf_to_channel_kb(pdf_attachments[0])
            
            # 2. Automatic AI Answer if text exists and it's not a bot message
            elif self.kb_state == 'ready' and message.message_type != 'notification':
                bot_partner = self.env.ref('base.partner_root')
                # Don't respond to self or other bots
                if message.author_id.id != bot_partner.id:
                    self._answer_channel_question(message)
        
        return res

    def action_index_latest_attachment(self):
        """Manually find the latest PDF in this channel and index it."""
        self.ensure_one()
        # Find latest message with a PDF attachment in this channel
        attachment = self.env['ir.attachment'].search([
            ('res_model', '=', 'discuss.channel'),
            ('res_id', '=', self.id),
            ('mimetype', 'ilike', 'pdf')
        ], order='create_date desc', limit=1)
        
        if attachment:
            self._index_pdf_to_channel_kb(attachment)
        else:
            return {
                'effect': {
                    'fadeout': 'slow',
                    'message': "No PDF attachments found in this channel.",
                    'type': 'rainbow_man',
                }
            }

    def _index_pdf_to_channel_kb(self, attachment):
        """Extract text from the PDF and store it in the channel."""
        try:
            import fitz
            doc = fitz.open(stream=base64.b64decode(attachment.datas), filetype="pdf")
            text = "\n".join([page.get_text() for page in doc]).strip()
            
            # Fallback for scanned/complex fonts
            if len(text) < 200:
                from ..services.gemini_service import generate_with_gemini, upload_file_to_gemini
                import tempfile
                import os
                
                with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
                    tmp.write(base64.b64decode(attachment.datas))
                    tmp_path = tmp.name
                try:
                    uploaded = upload_file_to_gemini(tmp_path, env=self.env)
                    ocr_res = generate_with_gemini(["Transcribe this document exactly."], model="gemini-3-flash-preview", env=self.env)
                    text = (ocr_res.get('text') if isinstance(ocr_res, dict) else str(ocr_res)).strip()
                finally:
                    if os.path.exists(tmp_path): os.remove(tmp_path)

            self.write({
                'kb_text': text,
                'kb_state': 'ready' if text else 'empty'
            })
            
            # Notify the channel
            if text:
                self.message_post(
                    body=_("📚 **Knowledge Base Updated**: I have indexed '%s'. You can now ask me questions about this document in this channel.") % attachment.name,
                    author_id=self.env.ref('base.partner_root').id,
                    message_type='comment'
                )
        except Exception as e:
            _logger.error("Channel KB Indexing Error: %s", str(e))

    def _answer_channel_question(self, message):
        """Use Gemini to answer questions based on the channel's KB text."""
        if not self.kb_text:
            return

        from ..services.gemini_service import generate_with_gemini
        
        # Clean the message body
        clean_question = re.sub('<[^<]+?>', '', message.body or '').strip()
        if not clean_question or len(clean_question) < 3:
            return

        # Prepare context prompt
        prompt = (
            "You are a helpful Odoo Channel Assistant. "
            "The following is the text content of a document uploaded to this channel. "
            "Use ONLY this content to answer the user's question. "
            "If the answer is not in the document, say you couldn't find it. "
            "Keep your response concise and professional.\n\n"
            f"DOCUMENT CONTENT:\n{self.kb_text[:30000]}\n\n"
            f"USER QUESTION: {clean_question}"
        )

        try:
            res = generate_with_gemini(prompt, model="gemini-3-flash-preview", temperature=0.3, env=self.env)
            answer = (res.get('text') if isinstance(res, dict) else str(res)).strip()
            
            if answer:
                self.message_post(
                    body=answer,
                    author_id=self.env.ref('base.partner_root').id, # Post as System/OdooBot
                    message_type='comment'
                )
        except Exception as e:
            _logger.error("AI Channel Answer Error: %s", str(e))
