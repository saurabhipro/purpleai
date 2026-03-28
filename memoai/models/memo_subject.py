# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class MemoSubject(models.Model):
    """
    Subject Master — configured by SME / Admin.
    A subject (e.g. 'Income Tax Depreciation') holds all prompts and RAG references
    that drive the 5-step AI workflow.
    """
    _name = 'memo_ai.subject'
    _description = 'Memo AI Subject'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(string='Subject Name', required=True, help="e.g. Income Tax Depreciation, Debt vs Equity")
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)

    # ── Step 1: Summarization ───────────────────────────────────────────────────
    summarization_prompt = fields.Text(
        string='Summarization Prompt',
        help="[SME] Prompt used by AI to summarize uploaded document(s) in Step 1.\n"
             "Use {document_text} as placeholder for the extracted PDF text."
    )

    # ── Step 2: Issue Extraction ────────────────────────────────────────────────
    issue_extraction_prompt = fields.Text(
        string='Issue Extraction Prompt',
        help="[Admin] Prompt used to identify applicable issues from the Issue List RAG.\n"
             "Use {summary} for Step 1 output and {rag_context} for matched RAG chunks."
    )

    # ── Step 3: Regulatory Literature ──────────────────────────────────────────
    regulatory_extraction_prompt = fields.Text(
        string='Regulatory Literature Extraction Prompt',
        help="[Admin] Prompt to extract applicable regulatory guidelines.\n"
             "Use {issues} for Step 2 output and {rag_context} for matched guideline chunks."
    )

    # ── Step 4: Analysis ────────────────────────────────────────────────────────
    analysis_prompt = fields.Text(
        string='Analysis Prompt',
        help="[Admin] Prompt for the final analysis step.\n"
             "Use {summary}, {issues}, {regulatory}, {rag_context} as placeholders."
    )

    # ── RAG Document Links ──────────────────────────────────────────────────────
    issue_rag_ids = fields.One2many(
        'memo_ai.rag_document', 'subject_id',
        domain=[('rag_type', '=', 'issue_list')],
        string='Issue List RAG Documents'
    )
    guideline_rag_ids = fields.One2many(
        'memo_ai.rag_document', 'subject_id',
        domain=[('rag_type', '=', 'guideline')],
        string='Guideline RAG Documents'
    )
    analysis_rag_ids = fields.One2many(
        'memo_ai.rag_document', 'subject_id',
        domain=[('rag_type', '=', 'analysis')],
        string='Analysis RAG Documents'
    )

    # ── Stats ───────────────────────────────────────────────────────────────────
    session_count = fields.Integer(string='Sessions', compute='_compute_session_count')

    def _compute_session_count(self):
        for rec in self:
            rec.session_count = self.env['memo_ai.session'].search_count([('subject_id', '=', rec.id)])

    def action_view_sessions(self):
        return {
            'type': 'ir.actions.act_window',
            'name': f'Sessions — {self.name}',
            'res_model': 'memo_ai.session',
            'view_mode': 'list,form',
            'domain': [('subject_id', '=', self.id)],
            'context': {'default_subject_id': self.id},
        }
