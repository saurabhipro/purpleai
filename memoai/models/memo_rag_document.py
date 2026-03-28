# -*- coding: utf-8 -*-
import base64
import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class MemoRagDocument(models.Model):
    """
    RAG Document — a PDF or text file uploaded against a subject for a specific RAG role.
    Extracted text is stored in chunks for context injection into AI prompts.
    """
    _name = 'memo_ai.rag_document'
    _description = 'Memo AI RAG Document'
    _order = 'subject_id, rag_type, name'

    name = fields.Char(string='Document Name', required=True)
    subject_id = fields.Many2one('memo_ai.subject', string='Subject', required=True, ondelete='cascade')
    rag_type = fields.Selection([
        ('issue_list', 'Issue List'),
        ('guideline', 'Guideline'),
        ('analysis', 'Analysis'),
    ], string='RAG Type', required=True)

    # File storage
    attachment_id = fields.Many2one(
        'ir.attachment', string='PDF / Document',
        help="Upload the source PDF or text file for this RAG document."
    )
    file_name = fields.Char(string='File Name')

    # Extracted content (stored as text for RAG retrieval)
    extracted_text = fields.Text(string='Extracted Text', readonly=True,
                                 help="Auto-extracted text from the uploaded document.")
    chunk_count = fields.Integer(string='Chunks', compute='_compute_chunk_count', store=True)
    state = fields.Selection([
        ('draft', 'Not Processed'),
        ('processed', 'Processed'),
        ('error', 'Error'),
    ], default='draft', string='Status')
    error_message = fields.Text(string='Processing Error', readonly=True)

    @api.depends('extracted_text')
    def _compute_chunk_count(self):
        for rec in self:
            if rec.extracted_text:
                chunks = rec._split_into_chunks(rec.extracted_text)
                rec.chunk_count = len(chunks)
            else:
                rec.chunk_count = 0

    def action_extract_text(self):
        """Extract text from the attached PDF using purpleai's document processing."""
        for rec in self:
            if not rec.attachment_id:
                raise UserError(_("Please attach a document first."))
            try:
                attachment = rec.attachment_id
                file_data = base64.b64decode(attachment.datas)
                # Use purpleai's PDF extraction
                doc_service = rec.env['purple_ai.document_processing'] if hasattr(
                    rec.env, 'purple_ai.document_processing') else None

                # Fallback: use PyPDF2 / pdfplumber directly
                extracted = rec._extract_pdf_text(file_data, attachment.name)
                rec.write({
                    'extracted_text': extracted,
                    'state': 'processed',
                    'error_message': False,
                })
            except Exception as e:
                _logger.error("RAG document extraction failed: %s", str(e))
                rec.write({'state': 'error', 'error_message': str(e)})

    def _extract_pdf_text(self, file_data, filename):
        """Extract plain text from a PDF binary."""
        import io
        try:
            import pdfplumber
            with pdfplumber.open(io.BytesIO(file_data)) as pdf:
                pages = []
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        pages.append(text)
                return "\n\n".join(pages)
        except ImportError:
            pass

        try:
            import PyPDF2
            reader = PyPDF2.PdfReader(io.BytesIO(file_data))
            pages = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    pages.append(text)
            return "\n\n".join(pages)
        except Exception as e:
            raise UserError(_(f"Could not extract text from PDF: {e}"))

    def _split_into_chunks(self, text, chunk_size=1500, overlap=200):
        """Split text into overlapping chunks for RAG retrieval."""
        chunks = []
        words = text.split()
        i = 0
        while i < len(words):
            chunk_words = words[i:i + chunk_size]
            chunks.append(" ".join(chunk_words))
            i += chunk_size - overlap
        return chunks

    def get_relevant_chunks(self, query, top_k=5):
        """
        Simple keyword-based RAG retrieval.
        Returns the top_k most relevant chunks for a given query.
        In Phase 2, this can be replaced with vector embeddings.
        """
        if not self.extracted_text:
            return ""
        chunks = self._split_into_chunks(self.extracted_text)
        query_words = set(query.lower().split())

        scored = []
        for chunk in chunks:
            chunk_words = set(chunk.lower().split())
            score = len(query_words & chunk_words)
            scored.append((score, chunk))

        scored.sort(key=lambda x: x[0], reverse=True)
        top_chunks = [c for _, c in scored[:top_k]]
        return "\n\n---\n\n".join(top_chunks)

    @staticmethod
    def get_rag_context_for_subject(env, subject_id, rag_type, query, top_k=5):
        """Aggregate RAG context from all documents of a given type for a subject."""
        docs = env['memo_ai.rag_document'].search([
            ('subject_id', '=', subject_id),
            ('rag_type', '=', rag_type),
            ('state', '=', 'processed'),
        ])
        all_chunks = []
        for doc in docs:
            chunks = doc._split_into_chunks(doc.extracted_text or "")
            query_words = set(query.lower().split())
            for chunk in chunks:
                chunk_words = set(chunk.lower().split())
                score = len(query_words & chunk_words)
                all_chunks.append((score, chunk))

        all_chunks.sort(key=lambda x: x[0], reverse=True)
        top = [c for _, c in all_chunks[:top_k]]
        return "\n\n---\n\n".join(top)
