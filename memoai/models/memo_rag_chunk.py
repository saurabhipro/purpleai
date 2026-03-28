# -*- coding: utf-8 -*-
from odoo import models, fields, api
import logging
import json

_logger = logging.getLogger(__name__)

class MemoRagChunk(models.Model):
    """
    Holds individual chunks of text extracted from RAG Documents.
    This model utilizes PostgreSQL's native pgvector extension for high-performance
    Cosine Similarity retrieval.
    """
    _name = 'memo_ai.rag_chunk'
    _description = 'Memo AI RAG Vector Chunk'

    document_id = fields.Many2one('memo_ai.rag_document', string='Source Document', ondelete='cascade', required=True)
    subject_id = fields.Many2one('memo_ai.subject', related='document_id.subject_id', store=True, index=True)
    rag_type = fields.Selection(related='document_id.rag_type', store=True, index=True)
    content = fields.Text('Chunk Text', required=True)
    
    # Python-level field tracker (the actual db column is a generic pgvector)
    # We leave this unbound in Odoo ORM to prevent schema sync errors,
    # and instead handle it raw in _auto_init and custom SQL.

    @api.model
    def _auto_init(self):
        """
        Force PostgreSQL to load the vector extension and add the embedding vector column
        bypassing Odoo's standard ORM which does not natively support VECTOR types.
        """
        # Ensure extension exists on the database
        self.env.cr.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        
        # Run standard Odoo table creation
        super(MemoRagChunk, self)._auto_init()
        
        # Inject the pgvector column natively if it doesn't already exist
        self.env.cr.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name='memo_ai_rag_chunk' AND column_name='embedding'
        """)
        if not self.env.cr.fetchone():
            _logger.info("Initializing pgvector embedding column on memo_ai_rag_chunk...")
            # We use generic 'vector' type without dimensions to flexibly support 
            # both Gemini (768) and OpenAI (1536) embedding arrays dynamically.
            self.env.cr.execute('ALTER TABLE memo_ai_rag_chunk ADD COLUMN embedding vector;')
            # Add an exact k-NN index or HNSW depending on PG version.
            # Without an index on small sets (<100k rows), exact k-NN scan is blazingly fast anyway.
