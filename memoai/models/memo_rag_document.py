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
    upload_file = fields.Binary(
        string='PDF / Document',
        attachment=True,
        help="Drag and drop or upload the source PDF for this RAG document."
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

    # Preview & Linkage
    attachment_id = fields.Many2one('ir.attachment', string='Attachment Link', compute='_compute_attachment_id', store=True)

    @api.depends('upload_file')
    def _compute_attachment_id(self):
        """Find or create the implicit attachment for the binary field to allow PDF preview widgets."""
        for rec in self:
            if not rec.upload_file:
                rec.attachment_id = False
                continue
            
            # Find the attachment Odoo creates for the binary field (attachment=True)
            domain = [
                ('res_model', '=', self._name),
                ('res_id', '=', rec.id),
                ('res_field', '=', 'upload_file')
            ]
            attachment = self.env['ir.attachment'].sudo().search(domain, limit=1)
            rec.attachment_id = attachment.id if attachment else False

    def action_view_pdf(self):
        """Action for the split-screen viewer."""
        self.ensure_one()
        if not self.attachment_id:
            raise UserError(_("Please upload a PDF first to preview."))
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{self.attachment_id.id}?download=false',
            'target': 'new',
        }
    
    # Telemetry
    process_time = fields.Float(string='Time (s)', readonly=True)
    process_cost = fields.Float(string='Cost ($)', readonly=True, digits=(10, 4))
    processed_date = fields.Datetime(string='Processed Date', readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        """Auto-extract vectors when a document is created."""
        records = super(MemoRagDocument, self).create(vals_list)
        for rec in records:
            if rec.upload_file:
                rec.action_extract_text()
        return records

    def write(self, vals):
        """Automatically wipe vectors and re-extract if the PDF is replaced."""
        res = super(MemoRagDocument, self).write(vals)
        if 'upload_file' in vals:
            for rec in self:
                if rec.upload_file:
                    # Wipe stale text immediately
                    rec.write({'state': 'draft', 'extracted_text': False})
                    rec.env['memo_ai.rag_chunk'].search([('document_id', '=', rec.id)]).unlink()
                    # Trigger auto-extraction for the new file
                    rec.action_extract_text()
        return res

    @api.depends('extracted_text')
    def _compute_chunk_count(self):
        for rec in self:
            if rec.extracted_text:
                chunks = rec._split_into_chunks(rec.extracted_text)
                rec.chunk_count = len(chunks)
            else:
                rec.chunk_count = 0

    def action_extract_text(self):
        """Extract text from the attached PDF and generate immutable vector embeddings natively."""
        from ..services.memo_ai_service import get_embedding, _get_ai_settings
        import time
        from odoo import fields
        
        for rec in self:
            if not rec.upload_file:
                # Don't throw UserError if triggered automatically via write/create
                continue
                
            start_time = time.time()
            total_tokens = 0
            
            try:
                file_data = base64.b64decode(rec.upload_file)
                extracted = rec._extract_pdf_text(file_data, rec.file_name or rec.name)
                
                # Wipe existing vector chunks securely
                rec.env['memo_ai.rag_chunk'].search([('document_id', '=', rec.id)]).unlink()
                
                # Split and Embed natively using pgvector
                chunks = rec._split_into_chunks(extracted)
                for chunk_text in chunks:
                    vector = get_embedding(rec.env, chunk_text)
                    vector_str = "[" + ",".join(map(str, vector)) + "]"
                    
                    # Approximate token usage (4 chars ~= 1 token)
                    total_tokens += len(chunk_text) // 4
                    
                    # Allocate ID natively in ORM
                    chunk_record = rec.env['memo_ai.rag_chunk'].create({
                        'document_id': rec.id,
                        'content': chunk_text,
                    })
                    
                    # Inject Vector directly into PostgreSQL column bypassing backend validation
                    rec.env.cr.execute(
                        "UPDATE memo_ai_rag_chunk SET embedding = %s::vector WHERE id = %s",
                        (vector_str, chunk_record.id)
                    )
                
                end_time = time.time()
                elapsed = end_time - start_time
                
                # Simple approximation embedding cost ($0.02 / 1M tokens)
                # Gemini embedding is technically free on many tiers, but we estimate standard logic
                cost = (total_tokens / 1_000_000.0) * 0.02

                rec.write({
                    'extracted_text': extracted,
                    'state': 'processed',
                    'error_message': False,
                    'process_time': elapsed,
                    'process_cost': cost,
                    'processed_date': fields.Datetime.now()
                })
            except Exception as e:
                _logger.error("RAG document vector extraction failed: %s", str(e))
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

    @api.model
    def search_vector_similarity(self, query, limit=5, subject_type=None):
        """
        Native high-performance vector search using pgvector cosine similarity (<=>).
        Returns a list of dicts with {content, document_name}.
        """
        from ..services.memo_ai_service import get_embedding
        if not query or len(query.strip()) < 5:
            return []
            
        try:
            # 1. Transform query to vector
            query_vector = get_embedding(self.env, query)
            vector_str = "[" + ",".join(map(str, query_vector)) + "]"
            
            # 2. Native SQL search across all chunks linked to this subject_type
            # We join with rag_document to filter by type and get document name
            sql = """
                SELECT c.content, d.name
                FROM memo_ai_rag_chunk c
                JOIN memo_ai_rag_document d ON c.document_id = d.id
                WHERE d.rag_type = %s
                ORDER BY c.embedding <=> %s::vector
                LIMIT %s
            """
            self.env.cr.execute(sql, (subject_type, vector_str, limit))
            
            results = []
            for row in self.env.cr.fetchall():
                results.append({
                    'content': row[0],
                    'document_name': row[1]
                })
            return results
            
        except Exception as e:
            _logger.error("Vector Cosine similarity search failed: %s", str(e))
            return []
