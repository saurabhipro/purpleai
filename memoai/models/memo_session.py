# -*- coding: utf-8 -*-
import base64
import io
import json
import logging
from datetime import datetime
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class MemoSession(models.Model):
    """
    Analysis Session — the main workflow record.
    Tracks the user's 5-step AI analysis journey for a selected subject.
    """
    _name = 'memo_ai.session'
    _description = 'Memo AI Analysis Session'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(string='Session Reference', readonly=True, copy=False, default='New')
    subject_id = fields.Many2one('memo_ai.subject', string='Subject', required=True,
                                 tracking=True, ondelete='restrict')
    company_id = fields.Many2one('res.company', default=lambda s: s.env.company)
    user_id = fields.Many2one('res.users', string='Analyst', default=lambda s: s.env.user, tracking=True)
    create_date = fields.Datetime(string='Created On', readonly=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('step1_done', 'Step 1 Done'),
        ('step2_done', 'Step 2 Done'),
        ('step3_done', 'Step 3 Done'),
        ('step4_done', 'Step 4 Done'),
        ('done', 'Complete'),
    ], default='draft', string='Status', tracking=True)

    # ── Uploaded Documents ──────────────────────────────────────────────────────
    document_ids = fields.Many2many(
        'ir.attachment', 'memo_session_attachment_rel',
        'session_id', 'attachment_id',
        string='Source Documents',
        help="Upload PDFs or scanned documents for analysis."
    )

    # ── Step 1: Summary ─────────────────────────────────────────────────────────
    step1_output = fields.Html(string='Step 1 — Summary', sanitize=False)
    step1_processing = fields.Boolean(default=False)

    # ── Step 2: Issue Identification ────────────────────────────────────────────
    step2_output = fields.Html(string='Step 2 — Applicable Issues', sanitize=False)
    step2_processing = fields.Boolean(default=False)

    # ── Step 3: Regulatory Guidelines ──────────────────────────────────────────
    step3_output = fields.Html(string='Step 3 — Regulatory Guidelines', sanitize=False)
    step3_processing = fields.Boolean(default=False)

    # ── Step 4: Analysis ────────────────────────────────────────────────────────
    step4_output = fields.Html(string='Step 4 — Analysis', sanitize=False)
    step4_processing = fields.Boolean(default=False)

    # ── Tracking & Analytics ────────────────────────────────────────────────────
    total_time_seconds = fields.Float(string='Time Taken (s)', default=0.0,
                                      help="Total execution time for all AI calls in this session.")
    total_cost = fields.Float(string='API Cost ($)', digits=(10, 4), default=0.0,
                              help="Estimated USD cost based on token consumption.")

    # ── Step 5: Word Export ─────────────────────────────────────────────────────
    word_attachment_id = fields.Many2one('ir.attachment', string='Word Document', readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('memo_ai.session') or 'New'
        return super().create(vals_list)

    # ───────────────────────────────────────────────────────────────────────────
    # Step 1: Extract & Summarize
    # ───────────────────────────────────────────────────────────────────────────
    def action_run_step1(self):
        """Extract text from all uploaded documents and summarize using AI."""
        self.ensure_one()
        if not self.document_ids:
            raise UserError(_("Please upload at least one document before running Step 1."))
        subject = self.subject_id
        if not subject.summarization_prompt:
            raise UserError(_("The subject '%s' has no Summarization Prompt configured.") % subject.name)

        # Extract text from all uploaded PDFs
        all_text_parts = []
        for attachment in self.document_ids:
            try:
                file_data = base64.b64decode(attachment.datas)
                rag_doc = self.env['memo_ai.rag_document'].new({})
                text = rag_doc._extract_pdf_text(file_data, attachment.name)
                all_text_parts.append(f"=== {attachment.name} ===\n{text}")
            except Exception as e:
                _logger.warning("Could not extract text from %s: %s", attachment.name, str(e))
                all_text_parts.append(f"=== {attachment.name} ===\n[Could not extract text: {e}]")

        combined_text = "\n\n".join(all_text_parts)

        # Build prompt
        prompt = subject.summarization_prompt.replace('{document_text}', combined_text)

        # Call AI
        ai_response = self._call_ai(prompt)

        self.write({
            'step1_output': ai_response,
            'state': 'step1_done',
        })
        self.message_post(body=_("✅ Step 1 (Summary) completed by AI."))
        return True

    # ───────────────────────────────────────────────────────────────────────────
    # Step 2: Issue Identification via RAG
    # ───────────────────────────────────────────────────────────────────────────
    def action_run_step2(self):
        """Search issue list RAG and identify applicable issues."""
        self.ensure_one()
        if self.state not in ('step1_done', 'step2_done', 'step3_done'):
            raise UserError(_("Please complete Step 1 first."))
        if not self.step1_output:
            raise UserError(_("Step 1 output is empty. Please run Step 1."))

        subject = self.subject_id
        if not subject.issue_extraction_prompt:
            raise UserError(_("The subject '%s' has no Issue Extraction Prompt configured.") % subject.name)

        # Retrieve RAG context from issue list documents
        rag_context = self.env['memo_ai.rag_document'].get_rag_context_for_subject(
            self.env, subject.id, 'issue_list', self.step1_output, top_k=8
        )

        prompt = subject.issue_extraction_prompt\
            .replace('{summary}', self.step1_output)\
            .replace('{rag_context}', rag_context or "No issue list RAG documents found.")

        ai_response = self._call_ai(prompt)

        self.write({
            'step2_output': ai_response,
            'state': 'step2_done',
        })
        self.message_post(body=_("✅ Step 2 (Issue Identification) completed by AI."))
        return True

    # ───────────────────────────────────────────────────────────────────────────
    # Step 3: Regulatory Guidelines
    # ───────────────────────────────────────────────────────────────────────────
    def action_run_step3(self):
        """Find applicable regulatory guidelines using guideline RAG."""
        self.ensure_one()
        if self.state not in ('step2_done', 'step3_done'):
            raise UserError(_("Please complete Step 2 first."))

        subject = self.subject_id
        if not subject.regulatory_extraction_prompt:
            raise UserError(_("The subject '%s' has no Regulatory Extraction Prompt configured.") % subject.name)

        query = (self.step2_output or "") + " " + (self.step1_output or "")
        rag_context = self.env['memo_ai.rag_document'].get_rag_context_for_subject(
            self.env, subject.id, 'guideline', query, top_k=8
        )

        prompt = subject.regulatory_extraction_prompt\
            .replace('{summary}', self.step1_output or "")\
            .replace('{issues}', self.step2_output or "")\
            .replace('{rag_context}', rag_context or "No guideline RAG documents found.")

        ai_response = self._call_ai(prompt)

        self.write({
            'step3_output': ai_response,
            'state': 'step3_done',
        })
        self.message_post(body=_("✅ Step 3 (Regulatory Guidelines) completed by AI."))
        return True

    # ───────────────────────────────────────────────────────────────────────────
    # Step 4: Final Analysis
    # ───────────────────────────────────────────────────────────────────────────
    def action_run_step4(self):
        """Run analysis combining all previous steps + Analysis RAG."""
        self.ensure_one()
        if self.state not in ('step3_done', 'step4_done'):
            raise UserError(_("Please complete Step 3 first."))

        subject = self.subject_id
        if not subject.analysis_prompt:
            raise UserError(_("The subject '%s' has no Analysis Prompt configured.") % subject.name)

        query = " ".join(filter(None, [self.step1_output, self.step2_output, self.step3_output]))
        rag_context = self.env['memo_ai.rag_document'].get_rag_context_for_subject(
            self.env, subject.id, 'analysis', query, top_k=8
        )

        prompt = subject.analysis_prompt\
            .replace('{summary}', self.step1_output or "")\
            .replace('{issues}', self.step2_output or "")\
            .replace('{regulatory}', self.step3_output or "")\
            .replace('{rag_context}', rag_context or "No analysis RAG documents found.")

        ai_response = self._call_ai(prompt)

        self.write({
            'step4_output': ai_response,
            'state': 'step4_done',
        })
        self.message_post(body=_("✅ Step 4 (Analysis) completed by AI."))
        return True

    # ───────────────────────────────────────────────────────────────────────────
    # Step 5: Export to Word
    # ───────────────────────────────────────────────────────────────────────────
    def action_export_word(self):
        """Generate a Word (.docx) document from all step outputs."""
        self.ensure_one()
        try:
            from docx import Document
            from docx.shared import Pt, RGBColor
            from docx.enum.text import WD_ALIGN_PARAGRAPH
        except ImportError:
            raise UserError(_(
                "python-docx is not installed. Please run: pip install python-docx"
            ))

        doc = Document()

        # Title
        title = doc.add_heading(f"Analysis Memo — {self.subject_id.name}", 0)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER

        # Metadata
        doc.add_paragraph(f"Reference: {self.name}")
        doc.add_paragraph(f"Analyst: {self.user_id.name}")
        doc.add_paragraph(f"Date: {datetime.now().strftime('%d %B %Y')}")
        doc.add_paragraph()

        sections = [
            ("1. Summary", self.step1_output),
            ("2. Applicable Issues", self.step2_output),
            ("3. Regulatory Guidelines", self.step3_output),
            ("4. Analysis", self.step4_output),
        ]
        from odoo.tools import html2plaintext
        for heading, content in sections:
            if content:
                doc.add_heading(heading, level=1)
                doc.add_paragraph(html2plaintext(content))
                doc.add_paragraph()

        # Save to bytes
        buffer = io.BytesIO()
        doc.save(buffer)
        buffer.seek(0)
        file_data = base64.b64encode(buffer.read()).decode('utf-8')

        attachment = self.env['ir.attachment'].create({
            'name': f"MemoAI_{self.name}_{self.subject_id.name}.docx",
            'type': 'binary',
            'datas': file_data,
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        })

        self.write({
            'word_attachment_id': attachment.id,
            'state': 'done',
        })
        self.message_post(body=_("✅ Word document generated."), attachment_ids=[attachment.id])

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }

    # ───────────────────────────────────────────────────────────────────────────
    # ── AI Call Helper ──────────────────────────────────────────────────────────
    # ───────────────────────────────────────────────────────────────────────────
    def _call_ai(self, prompt):
        """
        Call the configured AI provider and automatically log time and cost.
        Reads from memo_ai.* config parameters — fully independent of purpleai.
        """
        import time
        try:
            from ..services.memo_ai_service import call_ai
            
            start_t = time.time()
            ai_data = call_ai(self.env, prompt)
            elapsed = time.time() - start_t
            
            # Since we updated the service to return a dict with text and cost metrics
            if isinstance(ai_data, dict):
                text = ai_data.get('text', '')
                cost = ai_data.get('cost', 0.0)
                
                self.write({
                    'total_time_seconds': self.total_time_seconds + elapsed,
                    'total_cost': self.total_cost + cost,
                })
                return text
            else:
                self.write({
                    'total_time_seconds': self.total_time_seconds + elapsed,
                })
                return ai_data
            
        except Exception as e:
            _logger.error("AI call failed: %s", str(e))
            raise UserError(_(f"AI processing failed: {e}\n\nCheck Memo AI → Configuration → Settings."))

    def action_reset_to_draft(self):
        """Reset session to draft (clears all step outputs)."""
        self.write({
            'state': 'draft',
            'step1_output': False,
            'step2_output': False,
            'step3_output': False,
            'step4_output': False,
            'total_cost': 0.0,
            'total_time_seconds': 0.0,
        })

    @api.model
    def get_dashboard_stats(self, date_from=None, date_to=None):
        """Native RPC method to fetch data for the AI Analytics Dashboard Component."""
        domain = []
        if date_from:
            domain.append(('create_date', '>=', date_from))
        if date_to:
            domain.append(('create_date', '<=', date_to))
            
        sessions = self.search(domain)
        
        # Aggregate Top KPIs
        total_requests = len(sessions)
        passes = len(sessions.filtered(lambda s: s.state == 'done'))
        # Considered failed/in process if not done and not draft
        in_process = len(sessions.filtered(lambda s: s.state not in ('done', 'draft')))
        total_time = sum(sessions.mapped('total_time_seconds'))
        total_cost = sum(sessions.mapped('total_cost'))
        
        # Aggregate Chart Data for Bar Chart: cost and time group by date
        chart_dict = {}
        for s in sessions:
            if not s.create_date:
                continue
            day_str = s.create_date.strftime('%Y-%m-%d')
            if day_str not in chart_dict:
                chart_dict[day_str] = {'cost': 0.0, 'time': 0.0}
            chart_dict[day_str]['cost'] += s.total_cost
            chart_dict[day_str]['time'] += s.total_time_seconds
            
        labels = sorted(list(chart_dict.keys()))
        cost_data = [chart_dict[l]['cost'] for l in labels]
        time_data = [chart_dict[l]['time'] for l in labels]
            
        return {
            'total_requests': total_requests,
            'passes': passes,
            'in_process': in_process,
            'total_time': round(total_time, 2),
            'total_cost': round(total_cost, 4),
            'chart': {
                'labels': labels,
                'cost_data': cost_data,
                'time_data': time_data
            }
        }
