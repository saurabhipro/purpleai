# -*- coding: utf-8 -*-

import os
import zipfile
import uuid
import threading
import traceback
import time
import logging
import base64
import json
import random
import io
from concurrent.futures import ThreadPoolExecutor, as_completed
from psycopg2.errors import SerializationFailure
import re

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from odoo.api import Environment

from ..services.zip_utils import safe_extract_zip, ZipSecurityError
from ..services.tender_parser import extract_tender_from_pdf_with_gemini
from ..services.company_parser import extract_company_bidder_and_payments
from ..services.eligibility_service import evaluate_bidder_against_criteria

_logger = logging.getLogger(__name__)


class TenderJob(models.Model):
    _name = 'tende_ai.job'
    _description = 'Tender Processing Job'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(string='Job ID', required=True, copy=False, readonly=True, default=lambda self: _('New'))
    state = fields.Selection([
        ('draft', 'Draft'),
        ('extracting', 'Extracting'),
        ('extracted', 'Extracted'),
        ('processing', 'Evaluating'),
        ('completed', 'Processed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True, required=True)

    # Tender Information
    tender_id = fields.Many2one('tende_ai.tender', string='Tender', readonly=True, ondelete='cascade')
    tender_reference = fields.Char(string='Tender Reference', tracking=True)
    tender_description = fields.Text(string='Tender Description (Raw)', tracking=True)

    # Tender fields exposed directly on Job (so General Information tab never shows a hyperlink)
    tender_department_name = fields.Char(related='tender_id.department_name', store=True, readonly=True)
    tender_tender_id = fields.Char(string='Tender ID', related='tender_id.tender_id', store=True, readonly=True)
    tender_ref_no = fields.Char(string='Ref. No.', related='tender_id.ref_no', store=True, readonly=True)
    tender_tender_creator = fields.Char(string='Tender Creator', related='tender_id.tender_creator', store=True, readonly=True)
    tender_procurement_category = fields.Char(string='Category', related='tender_id.procurement_category', store=True, readonly=True)
    tender_tender_type = fields.Char(string='Tender Type', related='tender_id.tender_type', store=True, readonly=True)
    tender_organization_hierarchy = fields.Char(string='Hierarchy', related='tender_id.organization_hierarchy', store=True, readonly=True)
    tender_estimated_value_inr = fields.Char(string='Value (INR)', related='tender_id.estimated_value_inr', store=True, readonly=True)
    tender_tender_currency = fields.Char(string='Currency', related='tender_id.tender_currency', store=True, readonly=True)
    tender_bidding_currency = fields.Char(string='Bidding', related='tender_id.bidding_currency', store=True, readonly=True)
    tender_offer_validity_days = fields.Char(string='Validity (Days)', related='tender_id.offer_validity_days', store=True, readonly=True)
    tender_previous_tender_no = fields.Char(string='Prev Tender', related='tender_id.previous_tender_no', store=True, readonly=True)
    tender_published_on = fields.Char(string='Published', related='tender_id.published_on', store=True, readonly=True)
    tender_bid_submission_start = fields.Char(string='Start Date', related='tender_id.bid_submission_start', store=True, readonly=True)
    tender_bid_submission_end = fields.Char(string='End Date', related='tender_id.bid_submission_end', store=True, readonly=True)
    tender_opened_on = fields.Char(string='Opened On', related='tender_id.tender_opened_on', store=True, readonly=True)
    tender_description_text = fields.Text(string='Tender Description', related='tender_id.description', store=True, readonly=True)
    tender_nit = fields.Text(string='NIT', related='tender_id.nit', store=True, readonly=True)

    tender_pdf_attachment_id = fields.Many2one(
        "ir.attachment",
        string="Tender PDF",
        compute="_compute_tender_pdf_attachment_id",
        store=False,
        readonly=True,
    )

    # File Information
    # Store large ZIPs as attachments to avoid oversized JSON-RPC payloads (413 Request Entity Too Large)
    zip_file = fields.Binary(string='ZIP File', required=True, attachment=True)
    zip_filename = fields.Char(string='ZIP Filename')
    zip_path = fields.Char(string='ZIP Path', readonly=True)
    extract_dir = fields.Char(string='Extract Directory', readonly=True)

    # Processing Information
    companies_detected = fields.Integer(string='Companies Detected', default=0, readonly=True)
    error_message = fields.Text(string='Error Message', readonly=True)

    # Analytics
    analytics = fields.Text(string='Analytics (JSON)', readonly=True)
    analytics_html = fields.Html(string='Analytics Summary', compute='_compute_analytics_html', sanitize=False, readonly=True)

    # Timing (separate extraction vs evaluation)
    extraction_started_on = fields.Datetime(string='Extraction Started On', readonly=True)
    extraction_finished_on = fields.Datetime(string='Extraction Finished On', readonly=True)
    evaluation_started_on = fields.Datetime(string='Evaluation Started On', readonly=True)
    evaluation_finished_on = fields.Datetime(string='Evaluation Finished On', readonly=True)

    extraction_time_minutes = fields.Float(
        string='Extraction Time (min)',
        compute='_compute_extraction_time_minutes',
        store=True,
        readonly=True,
    )
    evaluation_time_minutes = fields.Float(
        string='Evaluation Time (min)',
        compute='_compute_evaluation_time_minutes',
        store=True,
        readonly=True,
    )
    processing_time_minutes = fields.Float(
        string='Total Time (min)',
        compute='_compute_processing_time_minutes',
        store=True,
        readonly=True,
    )

    # Related Records
    bidders = fields.One2many('tende_ai.bidder', 'job_id', string='Bidders', readonly=True)
    detected_company_ids = fields.Many2many(
        'tende_ai.bidder',
        string='Detected Companies',
        compute='_compute_detected_company_ids',
        store=False,
        readonly=True,
    )
    eligibility_criteria = fields.One2many('tende_ai.eligibility_criteria', 'job_id', string='Eligibility Criteria', readonly=True)
    bidder_check_ids = fields.One2many('tende_ai.bidder_check', 'job_id', string='Eligibility Checks', readonly=True)

    @api.depends('bidders')
    def _compute_detected_company_ids(self):
        for job in self:
            job.detected_company_ids = job.bidders

    def _compute_tender_pdf_attachment_id(self):
        Attachment = self.env["ir.attachment"]
        for job in self:
            att = Attachment.search([
                ("res_model", "=", "tende_ai.job"),
                ("res_id", "=", job.id),
                ("mimetype", "=", "application/pdf"),
                ("name", "ilike", "tender.pdf"),
            ], limit=1)
            job.tender_pdf_attachment_id = att.id if att else False

    def _find_tender_pdf_path(self, extract_dir: str):
        if not extract_dir:
            return None
        for root, _, files in os.walk(extract_dir):
            for fn in files:
                if fn.lower() == "tender.pdf":
                    return os.path.join(root, fn)
        return None

    def _ensure_tender_pdf_attachment(self, tender_pdf_path: str, extract_dir: str = None):
        """Attach tender.pdf to this job as an ir.attachment (so it appears in chatter and can be previewed)."""
        self.ensure_one()
        if not tender_pdf_path or not os.path.isfile(tender_pdf_path):
            return False
        Attachment = self.env["ir.attachment"].sudo()

        name = "tender.pdf"
        try:
            if extract_dir:
                rel = os.path.relpath(tender_pdf_path, extract_dir)
                if rel:
                    name = rel
        except Exception:
            pass

        existing = Attachment.search([
            ("res_model", "=", "tende_ai.job"),
            ("res_id", "=", self.id),
            ("mimetype", "=", "application/pdf"),
            ("name", "=", name),
        ], limit=1)
        if existing:
            return existing

        try:
            with open(tender_pdf_path, "rb") as f:
                content = f.read()
        except Exception:
            return False
        if not content:
            return False

        return Attachment.create({
            "name": name,
            "res_model": "tende_ai.job",
            "res_id": self.id,
            "type": "binary",
            "mimetype": "application/pdf",
            "datas": base64.b64encode(content),
        })

    def action_download_tender_pdf(self):
        self.ensure_one()
        att = self.tender_pdf_attachment_id
        if not att and self.extract_dir:
            path = self._find_tender_pdf_path(self.extract_dir)
            att = self._ensure_tender_pdf_attachment(path, extract_dir=self.extract_dir)
        if not att:
            raise ValidationError(_("Tender PDF not found. Please re-extract the ZIP."))
        filename = att.name or "tender.pdf"
        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/ir.attachment/{att.id}/datas/{filename}?download=true",
            "target": "self",
        }

    # Flat tables for Job tabs (no nesting)
    payment_ids = fields.One2many('tende_ai.payment', 'job_id', string='Payments', readonly=True)
    work_experience_ids = fields.One2many('tende_ai.work_experience', 'job_id', string='Work Experience', readonly=True)

    @api.depends('analytics')
    def _compute_analytics_html(self):
        def _esc(v):
            if v is None:
                return ''
            return (str(v)
                    .replace("&", "&amp;")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;"))

        for rec in self:
            data = {}
            try:
                if rec.analytics:
                    data = json.loads(rec.analytics) if isinstance(rec.analytics, str) else (rec.analytics or {})
            except Exception:
                data = {}

            if not isinstance(data, dict) or not data:
                rec.analytics_html = "<div class='text-muted'>No analytics yet.</div>"
                continue

            tokens = data.get("tokensTotal") or {}
            kpi_rows = [
                ("Job", data.get("jobId")),
                ("Companies Detected", data.get("companiesDetected")),
                ("Total PDFs Received", data.get("totalPdfReceived")),
                ("Total Valid PDFs Processed", data.get("totalValidPdfProcessed")),
                ("AI Calls", data.get("geminiCallsTotal")),
                ("Duration (sec)", data.get("durationSeconds")),
                ("Tokens (prompt)", (tokens.get("promptTokens") if isinstance(tokens, dict) else "")),
                ("Tokens (output)", (tokens.get("outputTokens") if isinstance(tokens, dict) else "")),
                ("Tokens (total)", (tokens.get("totalTokens") if isinstance(tokens, dict) else "")),
            ]

            kpi_html = "".join(
                f"<tr><td style='padding:6px 10px; font-weight:600; white-space:nowrap;'>{_esc(k)}</td>"
                f"<td style='padding:6px 10px;'>{_esc(v)}</td></tr>"
                for k, v in kpi_rows
            )

            per_company = data.get("perCompany") or []
            company_rows = ""
            if isinstance(per_company, list) and per_company:
                for c in per_company[:25]:
                    if not isinstance(c, dict):
                        continue
                    ct = c.get("tokens") or {}
                    company_rows += (
                        "<tr>"
                        f"<td style='padding:6px 10px;'>{_esc(c.get('companyName'))}</td>"
                        f"<td style='padding:6px 10px; text-align:right;'>{_esc(c.get('pdfCountReceived'))}</td>"
                        f"<td style='padding:6px 10px; text-align:right;'>{_esc(c.get('validPdfCount'))}</td>"
                        f"<td style='padding:6px 10px; text-align:right;'>{_esc(c.get('geminiCalls'))}</td>"
                        f"<td style='padding:6px 10px; text-align:right;'>{_esc(c.get('durationSeconds'))}</td>"
                        f"<td style='padding:6px 10px; text-align:right;'>{_esc(ct.get('totalTokens') if isinstance(ct, dict) else '')}</td>"
                        "</tr>"
                    )

            company_table = ""
            if company_rows:
                company_table = (
                    "<div style='margin-top:16px;'>"
                    "<div style='font-weight:700; margin-bottom:8px;'>Per-Company Summary</div>"
                    "<table class='table table-sm table-striped' style='width:100%; border:1px solid #ddd;'>"
                    "<thead><tr>"
                    "<th style='padding:6px 10px;'>Company</th>"
                    "<th style='padding:6px 10px; text-align:right;'>PDFs</th>"
                    "<th style='padding:6px 10px; text-align:right;'>Valid</th>"
                    "<th style='padding:6px 10px; text-align:right;'>Calls</th>"
                    "<th style='padding:6px 10px; text-align:right;'>Sec</th>"
                    "<th style='padding:6px 10px; text-align:right;'>Tokens</th>"
                    "</tr></thead>"
                    f"<tbody>{company_rows}</tbody>"
                    "</table>"
                    "</div>"
                )

            rec.analytics_html = (
                "<div>"
                "<table class='table table-sm' style='width:100%; border:1px solid #ddd;'>"
                f"<tbody>{kpi_html}</tbody>"
                "</table>"
                f"{company_table}"
                "</div>"
            )

    @api.depends('extraction_started_on', 'extraction_finished_on')
    def _compute_extraction_time_minutes(self):
        for rec in self:
            minutes = 0.0
            try:
                if rec.extraction_started_on and rec.extraction_finished_on:
                    delta = rec.extraction_finished_on - rec.extraction_started_on
                    seconds = delta.total_seconds()
                    minutes = round(seconds / 60.0, 2) if seconds else 0.0
            except Exception:
                minutes = 0.0
            rec.extraction_time_minutes = minutes

    @api.depends('evaluation_started_on', 'evaluation_finished_on')
    def _compute_evaluation_time_minutes(self):
        for rec in self:
            minutes = 0.0
            try:
                if rec.evaluation_started_on and rec.evaluation_finished_on:
                    delta = rec.evaluation_finished_on - rec.evaluation_started_on
                    seconds = delta.total_seconds()
                    minutes = round(seconds / 60.0, 2) if seconds else 0.0
            except Exception:
                minutes = 0.0
            rec.evaluation_time_minutes = minutes

    @api.depends('analytics', 'extraction_time_minutes', 'evaluation_time_minutes')
    def _compute_processing_time_minutes(self):
        for rec in self:
            # Prefer computed stage durations; fallback to legacy analytics durationSeconds.
            minutes = round((rec.extraction_time_minutes or 0.0) + (rec.evaluation_time_minutes or 0.0), 2)
            if minutes:
                rec.processing_time_minutes = minutes
                continue
            try:
                data = json.loads(rec.analytics) if rec.analytics else {}
                if isinstance(data, dict):
                    seconds = float(data.get('durationSeconds') or 0.0)
                    minutes = round(seconds / 60.0, 2) if seconds else 0.0
            except Exception:
                minutes = 0.0
            rec.processing_time_minutes = minutes

    def _safe_job_write(self, vals, max_retries=5, base_delay=0.15):
        """Write on job with savepoint+retry to survive SerializationFailure."""
        self.ensure_one()
        for attempt in range(max_retries):
            try:
                with self.env.cr.savepoint():
                    self.sudo().with_context(
                        tracking_disable=True,
                        mail_notrack=True,
                        mail_create_nosubscribe=True,
                    ).write(vals)
                return
            except SerializationFailure:
                if attempt >= max_retries - 1:
                    raise
                time.sleep(base_delay * (2 ** attempt))

    def _format_failure_reason(self, e: Exception) -> str:
        """
        Convert exceptions into a clean, user-friendly reason for Error Log.
        Especially helpful for AI client error payloads.
        """
        msg = str(e) or repr(e)

        # The AI client often includes a JSON-like payload in the exception string
        # Example: "API key expired. Please renew the API key."
        if 'API key expired' in msg or 'API_KEY_INVALID' in msg:
            return (
                "AI API key is invalid/expired.\n"
                "Fix: Update the AI API key in odoo.conf [options] and restart Odoo.\n"
                f"Details: {msg}"
            )

        if 'INVALID_ARGUMENT' in msg and 'googleapis.com' in msg:
            return f"AI request rejected (INVALID_ARGUMENT).\nDetails: {msg}"

        # Common Odoo/PG failures
        if 'could not serialize access' in msg.lower():
            return f"Database concurrency issue (serialization failure).\nDetails: {msg}"

        # Try to pull a nested 'message' field if present
        m = re.search(r"'message'\s*:\s*'([^']+)'", msg)
        if m:
            return m.group(1)

        return msg

    def _attach_company_pdfs_to_bidder(self, bidder, pdf_paths, extract_dir=None):
        """Create ir.attachment records for bidder PDFs so they can be previewed/downloaded."""
        if not bidder or not bidder.id or not pdf_paths:
            return 0

        Attachment = self.env['ir.attachment'].sudo()

        # Build deterministic names (keep company folder structure) to avoid collisions
        names = []
        for p in pdf_paths:
            try:
                rel = os.path.relpath(p, extract_dir) if extract_dir else os.path.basename(p)
            except Exception:
                rel = os.path.basename(p)
            names.append(rel)

        existing = set(Attachment.search([
            ('res_model', '=', 'tende_ai.bidder'),
            ('res_id', '=', bidder.id),
            ('name', 'in', names),
        ]).mapped('name'))

        to_create = []
        for p, name in zip(pdf_paths, names):
            if name in existing:
                continue
            try:
                with open(p, 'rb') as f:
                    content = f.read()
            except Exception:
                continue
            if not content:
                continue
            to_create.append({
                'name': name,
                'res_model': 'tende_ai.bidder',
                'res_id': bidder.id,
                'type': 'binary',
                'mimetype': 'application/pdf',
                'datas': base64.b64encode(content),
            })

        if to_create:
            Attachment.create(to_create)
        return len(to_create)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('tende_ai.job') or _('New')
        return super().create(vals_list)

    def action_extract_zip(self):
        """Extract tender + eligibility criteria from the uploaded ZIP (background)."""
        self.ensure_one()
        if self.state != 'draft':
            raise ValidationError(_('Only draft jobs can be extracted'))

        _logger.info("=" * 80)
        _logger.info("TENDER AI: Starting extraction for Job ID: %s (ID: %s)", self.name, self.id)
        _logger.info("=" * 80)

        # IMPORTANT: commit before starting background thread to avoid concurrent
        # updates on the same job row from two different cursors/transactions.
        self.write({
            'state': 'extracting',
            'error_message': '',
            'extraction_started_on': fields.Datetime.now(),
            'extraction_finished_on': False,
            # reset evaluation times for a fresh run
            'evaluation_started_on': False,
            'evaluation_finished_on': False,
        })
        try:
            self.env.cr.commit()
        except Exception:
            # If commit fails, let Odoo handle it; background thread will still retry on serialization issues.
            self.env.cr.rollback()

        # Start background processing with proper Odoo environment
        env = self.env
        job_id = self.id
        
        def _background_extract_with_env():
            # Create new environment for background thread with retry logic
            max_retries = 3
            for attempt in range(max_retries):
                cr = None
                try:
                    cr = env.registry.cursor()
                    env_background = Environment(cr, env.uid, env.context)
                    job = env_background['tende_ai.job'].browse(job_id)
                    job._background_extract()
                    cr.commit()
                    break
                except Exception as e:
                    error_str = str(e).lower()
                    error_type = type(e).__name__
                    
                    is_serialization_error = (
                        'serialize' in error_str or 
                        'concurrent' in error_str or
                        'transaction is aborted' in error_str or
                        'infailedsqltransaction' in error_str or
                        error_type == 'InFailedSqlTransaction' or
                        error_type == 'SerializationFailure'
                    )
                    
                    # Rollback on any error before retrying
                    if cr:
                        try:
                            cr.rollback()
                            _logger.debug("TENDER AI [Job %s]: Rolled back transaction after error", job_id)
                        except Exception as rollback_err:
                            _logger.warning("TENDER AI [Job %s]: Failed to rollback: %s", job_id, str(rollback_err))
                    
                    if is_serialization_error and attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 1.0  # Longer backoff for serialization errors
                        _logger.warning("TENDER AI [Job %s]: Database serialization error, retrying in %.2f seconds (attempt %d/%d)", 
                                      job_id, wait_time, attempt + 1, max_retries)
                        time.sleep(wait_time)
                        continue
                    
                    _logger.error("TENDER AI [Job %s]: Error in background process: %s", job_id, str(e), exc_info=True)
                    # Try to update state to failed
                    try:
                        with env.registry.cursor() as cr2:
                            env2 = Environment(cr2, env.uid, env.context)
                            job2 = env2['tende_ai.job'].browse(job_id)
                            reason = job2._format_failure_reason(e)
                            job2.sudo().write({
                                'state': 'failed',
                                'error_message': f'Background extraction error:\n{reason}',
                            })
                            try:
                                job2.message_post(
                                    body=f"<b>Tender AI extraction failed</b><br/><pre>{reason}</pre>",
                                    subtype_xmlid='mail.mt_note',
                                )
                            except Exception:
                                pass
                            cr2.commit()
                    except:
                        pass
                    break
                finally:
                    if cr:
                        try:
                            cr.close()
                        except Exception:
                            pass

        thread = threading.Thread(target=_background_extract_with_env, daemon=True)
        thread.start()
        _logger.info("TENDER AI [Job %s]: Background extraction thread started", self.name)

        return True

    # Backward compatibility: existing button may still call this.
    def action_process_zip(self):
        """Backward-compatible alias: Extract first."""
        return self.action_extract_zip()

    def action_process_bidders(self):
        """Backward-compatible alias: Evaluate Tender."""
        return self.action_evaluate_tender()

    def action_evaluate_tender(self):
        """Evaluate tender eligibility for all extracted bidders (background)."""
        self.ensure_one()
        if self.state != 'extracted':
            raise ValidationError(_('First run Extraction. Only extracted jobs can be evaluated.'))

        _logger.info("=" * 80)
        _logger.info("TENDER AI: Starting eligibility evaluation for Job ID: %s (ID: %s)", self.name, self.id)
        _logger.info("=" * 80)

        self.write({
            'state': 'processing',
            'error_message': '',
            'evaluation_started_on': fields.Datetime.now(),
            'evaluation_finished_on': False,
        })
        try:
            self.env.cr.commit()
        except Exception:
            self.env.cr.rollback()

        env = self.env
        job_id = self.id

        def _background_eval_with_env():
            max_retries = 3
            for attempt in range(max_retries):
                cr = None
                try:
                    cr = env.registry.cursor()
                    env_background = Environment(cr, env.uid, env.context)
                    job = env_background['tende_ai.job'].browse(job_id)
                    job._background_evaluate_tender()
                    cr.commit()
                    break
                except Exception as e:
                    error_str = str(e).lower()
                    error_type = type(e).__name__
                    is_serialization_error = (
                        'serialize' in error_str or
                        'concurrent' in error_str or
                        'transaction is aborted' in error_str or
                        'infailedsqltransaction' in error_str or
                        error_type == 'InFailedSqlTransaction' or
                        error_type == 'SerializationFailure'
                    )
                    if cr:
                        try:
                            cr.rollback()
                        except Exception:
                            pass
                    if is_serialization_error and attempt < max_retries - 1:
                        time.sleep((attempt + 1) * 1.0)
                        continue
                    try:
                        with env.registry.cursor() as cr2:
                            env2 = Environment(cr2, env.uid, env.context)
                            job2 = env2['tende_ai.job'].browse(job_id)
                            reason = job2._format_failure_reason(e)
                            job2.sudo().write({
                                'state': 'failed',
                                'error_message': f'Background processing error:\n{reason}',
                            })
                            try:
                                job2.message_post(
                                    body=f"<b>Tender AI processing failed</b><br/><pre>{reason}</pre>",
                                    subtype_xmlid='mail.mt_note',
                                )
                            except Exception:
                                pass
                            cr2.commit()
                    except Exception:
                        pass
                    break
                finally:
                    if cr:
                        try:
                            cr.close()
                        except Exception:
                            pass

        thread = threading.Thread(target=_background_eval_with_env, daemon=True)
        thread.start()
        _logger.info("TENDER AI [Job %s]: Background evaluation thread started", self.name)
        return True

    def action_stop_processing(self):
        """Stop the processing of ZIP file"""
        self.ensure_one()
        if self.state not in ('extracting', 'processing'):
            raise ValidationError(_('Only extracting/processing jobs can be stopped'))

        _logger.info("=" * 80)
        _logger.info("TENDER AI: Stopping current work for Job ID: %s (ID: %s)", self.name, self.id)
        _logger.info("=" * 80)

        # Update state to cancelled
        self.sudo().write({
            'state': 'cancelled',
            'error_message': 'Processing stopped by user',
        })
        
        _logger.info("TENDER AI [Job %s]: Processing stop signal sent", self.name)
        _logger.info("TENDER AI [Job %s]: Job state updated to 'cancelled'", self.name)
        _logger.info("=" * 80)

        return True

    def action_reset_and_reprocess(self):
        """Reset job to draft and allow reprocessing"""
        self.ensure_one()
        if self.state not in ('extracted', 'completed', 'failed', 'cancelled'):
            raise ValidationError(_('Can only reset completed, failed, or cancelled jobs'))

        # Delete related records to start fresh
        self.env['tende_ai.tender'].sudo().search([('job_id', '=', self.id)]).unlink()
        self.env['tende_ai.bidder'].sudo().search([('job_id', '=', self.id)]).unlink()
        self.env['tende_ai.eligibility_criteria'].sudo().search([('job_id', '=', self.id)]).unlink()
        self.env['tende_ai.bidder_check'].sudo().search([('job_id', '=', self.id)]).unlink()

        # Reset job to draft
        self.sudo().write({
            'state': 'draft',
            'tender_id': False,
            'tender_reference': '',
            'tender_description': '',
            'companies_detected': 0,
            'error_message': '',
            'analytics': '',
        })

        _logger.info("TENDER AI [Job %s]: Job reset to draft - ready for reprocessing", self.name)
        return True

    def action_open_ai_chat_wizard(self):
        """Open the AI chat wizard for this job (posts Q&A into chatter optionally)."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Ask AI"),
            "res_model": "tende_ai.job.chat.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_job_id": self.id},
        }

    def action_export_excel(self):
        """Export tender data (all functional tabs) to a styled Excel workbook.

        Excludes: Processing Analytics, Error Log.
        """
        self.ensure_one()

        try:
            import xlsxwriter  # type: ignore
        except Exception:
            raise ValidationError(
                _("Excel export requires the Python package 'XlsxWriter' installed in the Odoo environment.")
            )

        def _safe_str(v):
            if v is None:
                return ""
            if isinstance(v, (dict, list)):
                try:
                    return json.dumps(v, ensure_ascii=False)
                except Exception:
                    return str(v)
            return str(v)

        def _add_table(ws, headers, data_rows, tab_color="#2F5597", style="Table Style Medium 9"):
            ws.set_tab_color(tab_color)
            ws.freeze_panes(1, 0)

            if not data_rows:
                ws.write(0, 0, "No data")
                return

            # Ensure rectangular
            cols = len(headers)
            data = []
            for row in data_rows:
                r = list(row or [])
                if len(r) < cols:
                    r += [""] * (cols - len(r))
                data.append([_safe_str(x) for x in r[:cols]])

            ws.add_table(
                0, 0,
                len(data), cols - 1,
                {
                    "data": data,
                    "columns": [{"header": h} for h in headers],
                    "style": style,
                },
            )

            # Column widths (cap to keep nice)
            for c in range(cols):
                mx = len(str(headers[c] or "")) if headers else 10
                for r in data[:2000]:
                    mx = max(mx, len(str(r[c] or "")))
                ws.set_column(c, c, min(max(mx + 2, 12), 55))

        out = io.BytesIO()
        wb = xlsxwriter.Workbook(out, {"in_memory": True})

        fmt_title = wb.add_format({"bold": True, "font_size": 14})
        fmt_label = wb.add_format({"bold": True, "bg_color": "#F2F2F2", "border": 1})
        fmt_value = wb.add_format({"border": 1, "text_wrap": True})

        # Sheet: Tender (key/value)
        ws = wb.add_worksheet("Tender")
        ws.set_tab_color("#1F4E79")
        ws.write(0, 0, "Tender Export", fmt_title)

        tender = self.tender_id
        kv = [
            ("Job ID", self.name),
            ("Tender Reference", self.tender_reference),
            ("Status", self.state),
            ("Created By", self.create_uid.name if self.create_uid else ""),
            ("Created On", _safe_str(self.create_date)),
            ("Companies Detected", _safe_str(self.companies_detected)),
            ("Extraction Time (min)", _safe_str(self.extraction_time_minutes)),
            ("Evaluation Time (min)", _safe_str(self.evaluation_time_minutes)),
            ("Total Time (min)", _safe_str(self.processing_time_minutes)),
        ]

        if tender:
            kv.extend([
                ("Department", tender.department_name),
                ("Tender ID", tender.tender_id),
                ("Ref. No.", tender.ref_no),
                ("Tender Creator", tender.tender_creator),
                ("Category", tender.procurement_category),
                ("Tender Type", tender.tender_type),
                ("Hierarchy", tender.organization_hierarchy),
                ("Estimated Value (INR)", tender.estimated_value_inr),
                ("Tender Currency", tender.tender_currency),
                ("Bidding Currency", tender.bidding_currency),
                ("Offer Validity (Days)", tender.offer_validity_days),
                ("Previous Tender No.", tender.previous_tender_no),
                ("Published On", tender.published_on),
                ("Bid Submission Start", tender.bid_submission_start),
                ("Bid Submission End", tender.bid_submission_end),
                ("Tender Opened On", tender.tender_opened_on),
                ("Description", tender.description),
                ("NIT", tender.nit),
            ])

        row = 2
        for k, v in kv:
            ws.write(row, 0, _safe_str(k), fmt_label)
            ws.write(row, 1, _safe_str(v), fmt_value)
            row += 1
        ws.set_column(0, 0, 28)
        ws.set_column(1, 1, 90)

        # Sheet: Eligibility Criteria
        criteria = self.eligibility_criteria.sudo().sorted(key=lambda r: (r.sl_no or ""))
        _add_table(
            wb.add_worksheet("Eligibility Criteria"),
            ["Sl No", "Criteria", "Supporting Document"],
            [[c.sl_no, c.criteria, c.supporting_document] for c in criteria],
            tab_color="#7030A0",
        )

        # Sheet: Bidders
        bidders = self.bidders.sudo().sorted(key=lambda r: (r.vendor_company_name or ""))
        _add_table(
            wb.add_worksheet("Bidders"),
            [
                "Company Name", "Address", "Email", "Contact Person", "Phone",
                "PAN", "GSTIN", "Registration", "Validity",
            ],
            [[
                b.vendor_company_name, b.company_address, b.email_id, b.contact_person, b.contact_no,
                b.pan, b.gstin, b.place_of_registration, b.offer_validity_days,
            ] for b in bidders],
            tab_color="#00B0F0",
        )

        # Sheet: Payments
        payments = self.payment_ids.sudo().sorted(key=lambda r: ((r.company_name or ""), (r.transaction_date or "")))
        _add_table(
            wb.add_worksheet("Payments"),
            ["Company Name", "Vendor", "Mode", "Bank", "Transaction ID", "Amount (INR)", "Date", "Status"],
            [[
                p.company_name, p.vendor, p.payment_mode, p.bank_name, p.transaction_id,
                p.amount_inr, p.transaction_date, p.status,
            ] for p in payments],
            tab_color="#00B050",
        )

        # Sheet: Work Experience
        work = self.work_experience_ids.sudo().sorted(key=lambda r: ((r.vendor_company_name or ""), (r.date_of_start or "")))
        _add_table(
            wb.add_worksheet("Work Experience"),
            [
                "Vendor", "Name of Work", "Employer", "Location", "Amount",
                "Start", "End", "Certificate", "Attachment",
            ],
            [[
                w.vendor_company_name, w.name_of_work, w.employer, w.location, w.contract_amount_inr,
                w.date_of_start, w.date_of_completion, w.completion_certificate, w.attachment,
            ] for w in work],
            tab_color="#FFC000",
        )

        # Sheet: Eligibility Evaluation (Summary)
        checks = self.bidder_check_ids.sudo().sorted(key=lambda r: (r.bidder_id.vendor_company_name or ""))
        _add_table(
            wb.add_worksheet("Evaluation Summary"),
            ["Bidder", "Overall Result", "Passed", "Failed", "Unknown", "Time (sec)", "Processed On"],
            [[
                c.bidder_id.vendor_company_name if c.bidder_id else "",
                c.overall_result,
                c.passed_criteria,
                c.failed_criteria,
                c.unknown_criteria,
                c.duration_seconds,
                _safe_str(c.processed_on),
            ] for c in checks],
            tab_color="#C00000",
        )

        # Sheet: Eligibility Evaluation (Details per criterion)
        lines = self.env["tende_ai.bidder_check_line"].sudo().search([("job_id", "=", self.id)], order="bidder_id, sl_no, id")
        _add_table(
            wb.add_worksheet("Evaluation Details"),
            ["Bidder", "Sl No", "Result", "Criteria", "Supporting Document", "Reason", "Evidence", "Missing Documents"],
            [[
                ln.bidder_id.vendor_company_name if ln.bidder_id else "",
                ln.sl_no,
                ln.result,
                ln.criteria,
                ln.supporting_document,
                ln.reason,
                ln.evidence,
                ln.missing_documents,
            ] for ln in lines],
            tab_color="#7F0000",
        )

        wb.close()
        out.seek(0)
        data = out.read()

        filename = f"{self.name or 'tender_job'}_export.xlsx"
        att = self.env["ir.attachment"].sudo().create({
            "name": filename,
            "type": "binary",
            "datas": base64.b64encode(data),
            "mimetype": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "res_model": self._name,
            "res_id": self.id,
        })

        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{att.id}?download=true",
            "target": "self",
        }

    def _should_stop(self):
        """Check if processing should be stopped"""
        # Refresh the record to get latest state
        self.invalidate_recordset(['state'])
        # Check state from database
        current_state = self.read(['state'])[0]['state']
        return current_state == 'cancelled'

    def _background_extract(self):
        """Background extraction: unzip + extract tender + criteria + populate extracted bidder data (no eligibility eval)."""
        overall_t0 = time.time()
        _logger.info("TENDER AI [Job %s]: Background extraction started", self.name)

        try:
            # Check if processing was stopped before starting
            if self._should_stop():
                _logger.info("TENDER AI [Job %s]: Processing cancelled before start", self.name)
                self.sudo().write({
                    'state': 'cancelled',
                    'error_message': 'Processing cancelled by user',
                })
                return
            # Save ZIP file to temporary location
            tmp_dir = os.path.join(self.env['ir.config_parameter'].sudo().get_param('tende_ai.tmp_dir', '/tmp/tende_ai'))
            os.makedirs(tmp_dir, exist_ok=True)
            _logger.info("TENDER AI [Job %s]: Using temp directory: %s", self.name, tmp_dir)

            run_id = uuid.uuid4().hex[:10]
            extract_dir = os.path.join(tmp_dir, f"extracted_{run_id}")
            os.makedirs(extract_dir, exist_ok=True)
            _logger.info("TENDER AI [Job %s]: Created extraction directory: %s", self.name, extract_dir)

            zip_path = os.path.join(tmp_dir, f"{run_id}_{self.zip_filename or 'tender.zip'}")

            # Write ZIP file - Binary fields in Odoo are stored as base64 strings in ir.attachment
            _logger.info("TENDER AI [Job %s]: Writing ZIP file to: %s", self.name, zip_path)
            _logger.info("TENDER AI [Job %s]: ZIP file data type: %s", self.name, type(self.zip_file))
            
            # Get the actual binary data from the attachment
            # Odoo Binary fields stored in ir.attachment are always base64 encoded strings
            zip_data = None
            if self.zip_file:
                raw_data = self.zip_file
                _logger.info("TENDER AI [Job %s]: Raw ZIP data type: %s, length: %s", 
                           self.name, type(raw_data), 
                           len(raw_data) if hasattr(raw_data, '__len__') else 'N/A')
                
                # Convert to string if it's bytes (Odoo sometimes returns base64 as bytes)
                if isinstance(raw_data, bytes):
                    try:
                        # Try to decode as UTF-8 first (base64 is ASCII-compatible)
                        raw_data = raw_data.decode('utf-8')
                        _logger.info("TENDER AI [Job %s]: Converted bytes to string", self.name)
                    except UnicodeDecodeError:
                        # If it's not valid UTF-8, check if it's already binary ZIP data
                        # Check for ZIP signature (PK\x03\x04)
                        if raw_data[:2] == b'PK':
                            _logger.info("TENDER AI [Job %s]: Data is already binary ZIP (starts with PK)", self.name)
                            zip_data = raw_data
                        else:
                            # Try to decode as base64 anyway
                            try:
                                raw_data = raw_data.decode('latin-1')
                                _logger.info("TENDER AI [Job %s]: Converted bytes to string using latin-1", self.name)
                            except:
                                _logger.error("TENDER AI [Job %s]: Cannot decode bytes data", self.name)
                                self.sudo().write({
                                    'state': 'failed',
                                    'error_message': 'Cannot decode ZIP file data',
                                })
                                return
                
                # Now decode base64 if we have a string
                if isinstance(raw_data, str):
                    # Check if it looks like base64 (starts with common base64 chars)
                    if raw_data.startswith('UEs') or len(raw_data) > 100:
                        try:
                            # Decode base64 string
                            zip_data = base64.b64decode(raw_data)
                            _logger.info("TENDER AI [Job %s]: Decoded base64 ZIP data (decoded size: %d bytes)", 
                                        self.name, len(zip_data))
                        except Exception as e:
                            _logger.error("TENDER AI [Job %s]: Failed to decode base64: %s", self.name, str(e))
                            self.sudo().write({
                                'state': 'failed',
                                'error_message': f'Failed to decode ZIP file data: {str(e)}',
                            })
                            return
                    else:
                        # Doesn't look like base64, might be binary data as string
                        _logger.warning("TENDER AI [Job %s]: String data doesn't look like base64, treating as binary", self.name)
                        zip_data = raw_data.encode('latin-1')
                elif zip_data is None:
                    # Already set to binary data above
                    pass
            
            if not zip_data:
                _logger.error("TENDER AI [Job %s]: ZIP file data is empty or None", self.name)
                self.sudo().write({
                    'state': 'failed',
                    'error_message': 'ZIP file data is empty',
                })
                return
            
            # Write the binary data to file
            with open(zip_path, 'wb') as f:
                f.write(zip_data)
            
            zip_size = os.path.getsize(zip_path)
            _logger.info("TENDER AI [Job %s]: ZIP file written successfully (Size: %.2f MB, %d bytes)", 
                        self.name, zip_size / (1024 * 1024), zip_size)

            # Validate ZIP file
            if zip_size == 0:
                _logger.error("TENDER AI [Job %s]: Written ZIP file is empty", self.name)
                self.sudo().write({
                    'state': 'failed',
                    'error_message': 'ZIP file is empty after writing',
                })
                return
            
            # Read first few bytes to verify it's a valid ZIP
            with open(zip_path, 'rb') as f:
                first_bytes = f.read(10)
            
            # Check for ZIP signature (PK\x03\x04)
            if first_bytes[:2] != b'PK':
                _logger.error("TENDER AI [Job %s]: File does not have ZIP signature", self.name)
                _logger.error("TENDER AI [Job %s]: File size: %d bytes, First 10 bytes (hex): %s", 
                            self.name, zip_size, first_bytes.hex())
                _logger.error("TENDER AI [Job %s]: First 10 bytes (repr): %s", self.name, repr(first_bytes))
                _logger.error("TENDER AI [Job %s]: Expected ZIP signature: PK (0x504B), got: %s", 
                            self.name, first_bytes[:2].hex())
                
                # If it looks like base64, suggest the issue
                if first_bytes.startswith(b'UEs'):
                    _logger.error("TENDER AI [Job %s]: File appears to be base64 encoded (starts with UEs)", self.name)
                    _logger.error("TENDER AI [Job %s]: This suggests the base64 decoding failed", self.name)
                
                self.sudo().write({
                    'state': 'failed',
                    'error_message': 'Uploaded file is not a valid ZIP file (missing ZIP signature)',
                })
                return
                
            if not zipfile.is_zipfile(zip_path):
                _logger.error("TENDER AI [Job %s]: zipfile.is_zipfile() returned False", self.name)
                _logger.error("TENDER AI [Job %s]: File size: %d bytes, First 10 bytes (hex): %s", 
                            self.name, zip_size, first_bytes.hex())
                self.sudo().write({
                    'state': 'failed',
                    'error_message': 'Uploaded file is not a valid ZIP file',
                })
                return

            # Store paths (only write once)
            self._safe_job_write({
                'zip_path': zip_path,
                'extract_dir': extract_dir,
            })

            # Safe ZIP extract
            _logger.info("TENDER AI [Job %s]: Extracting ZIP file to: %s", self.name, extract_dir)
            try:
                safe_extract_zip(zip_path, extract_dir)
                _logger.info("TENDER AI [Job %s]: ZIP file extracted successfully", self.name)
            except ZipSecurityError as e:
                _logger.error("TENDER AI [Job %s]: ZIP security error: %s", self.name, str(e))
                self.write({
                    'state': 'failed',
                    'error_message': f'Unsafe ZIP: {str(e)}',
                })
                return

            # Locate tender.pdf
            _logger.info("TENDER AI [Job %s]: Searching for tender.pdf in extracted files", self.name)
            tender_pdf_path = None
            for root, _, files in os.walk(extract_dir):
                for fn in files:
                    if fn.lower() == "tender.pdf":
                        tender_pdf_path = os.path.join(root, fn)
                        break
                if tender_pdf_path:
                    break

            if not tender_pdf_path:
                _logger.error("TENDER AI [Job %s]: tender.pdf not found inside zip", self.name)
                self.sudo().write({
                    'state': 'failed',
                    'error_message': 'tender.pdf not found inside zip',
                })
                return
            
            _logger.info("TENDER AI [Job %s]: Found tender.pdf at: %s", self.name, tender_pdf_path)

            # Attach tender.pdf to the job so it appears in chatter and can be previewed/downloaded.
            try:
                self._ensure_tender_pdf_attachment(tender_pdf_path, extract_dir=extract_dir)
            except Exception:
                # Never fail extraction because of attachment UI.
                _logger.debug("TENDER AI [Job %s]: Failed to attach tender.pdf to job", self.name, exc_info=True)

            # Check if processing was stopped
            if self._should_stop():
                _logger.info("TENDER AI [Job %s]: Processing cancelled before tender extraction", self.name)
                self.sudo().write({
                    'state': 'cancelled',
                    'error_message': 'Processing cancelled by user',
                })
                return

            # 1️⃣ Tender extraction
            model = os.getenv("AI_TENDER_MODEL") or os.getenv("GEMINI_TENDER_MODEL") or "gemini-3-flash-preview"
            _logger.info("TENDER AI [Job %s]: Starting tender extraction with AI service", self.name)
            _logger.info("TENDER AI [Job %s]:   - Model: configured", self.name)
            _logger.info("TENDER AI [Job %s]:   - PDF Path: %s", self.name, tender_pdf_path)
            _logger.info("TENDER AI [Job %s]: Calling AI service: tender extraction", self.name)
            tender_start_time = time.time()
            tender_data = extract_tender_from_pdf_with_gemini(tender_pdf_path, model=model, env=self.env) or {}
            tender_duration = time.time() - tender_start_time
            _logger.info("TENDER AI [Job %s]: ✓ AI call completed for tender extraction", self.name)
            _logger.info("TENDER AI [Job %s]:   - Duration: %.2f seconds", self.name, tender_duration)
            
            # Log tender analytics if available
            tender_analytics = tender_data.get("tenderAnalytics") or {}
            if isinstance(tender_analytics, dict):
                tokens = tender_analytics.get("tokens") or {}
                _logger.info("TENDER AI [Job %s]:   - Tokens used: %s", self.name, tokens)

            # Check if processing was stopped after tender extraction
            if self._should_stop():
                _logger.info("TENDER AI [Job %s]: Processing cancelled after tender extraction", self.name)
                self.sudo().write({
                    'state': 'cancelled',
                    'error_message': 'Processing cancelled by user',
                })
                return

            # Create tender record
            tender = self.env['tende_ai.tender'].sudo().create({
                'job_id': self.id,
                'state': 'draft',
                'department_name': tender_data.get('departmentName', ''),
                'tender_id': tender_data.get('tenderId', ''),
                'ref_no': tender_data.get('refNo', ''),
                'tender_creator': tender_data.get('tenderCreator', ''),
                'procurement_category': tender_data.get('procurementCategory', ''),
                'tender_type': tender_data.get('tenderType', ''),
                'organization_hierarchy': tender_data.get('organizationHierarchy', ''),
                'estimated_value_inr': tender_data.get('estimatedValueINR', ''),
                'tender_currency': tender_data.get('tenderCurrency', ''),
                'bidding_currency': tender_data.get('biddingCurrency', ''),
                'offer_validity_days': tender_data.get('offerValidityDays', ''),
                'previous_tender_no': tender_data.get('previousTenderNo', ''),
                'published_on': tender_data.get('publishedOn', ''),
                'bid_submission_start': tender_data.get('bidSubmissionStart', ''),
                'bid_submission_end': tender_data.get('bidSubmissionEnd', ''),
                'tender_opened_on': tender_data.get('tenderOpenedOn', ''),
                'description': tender_data.get('description', ''),
                'nit': tender_data.get('nit', ''),
                'analytics': str(tender_data.get('tenderAnalytics', {})),
                'details_html': tender_data.get('description', '') or '',
            })

            # Batch create eligibility criteria
            criteria_list = tender_data.get('bidderEligibilityCriteria', [])
            if criteria_list:
                criteria_records = []
                for crit in criteria_list:
                    criteria_records.append({
                        'job_id': self.id,
                        'tender_id': tender.id,
                        'sl_no': crit.get('slNo', ''),
                        'criteria': crit.get('criteria', ''),
                        'supporting_document': crit.get('supportingDocument', ''),
                    })
                if criteria_records:
                    self.env['tende_ai.eligibility_criteria'].sudo().create(criteria_records)

            # Update job with tender info
            self._safe_job_write({
                'tender_id': tender.id,
                'tender_reference': tender_data.get('refNo', ''),
                'tender_description': tender_data.get('description', ''),
            })
            # Try to commit so tender info appears immediately in UI (but don't fail if it conflicts)
            try:
                self.env.cr.commit()
                _logger.info("TENDER AI [Job %s]: ✓ Tender information saved and committed - visible in UI", self.name)
            except Exception as commit_err:
                # If commit fails due to serialization, continue - data will be visible on next commit
                _logger.debug("TENDER AI [Job %s]: Commit skipped (will commit later): %s", self.name, str(commit_err))
                self.env.cr.rollback()

            # Precompute company count now (visible before processing)
            try:
                jobs = self._collect_company_jobs(extract_dir)
                self._safe_job_write({'companies_detected': len(jobs)})
            except Exception:
                pass

            # 2️⃣ Populate bidder data into DB (bidders/payments/work/attachments). No eligibility evaluation here.
            parse_metrics = {}
            try:
                parse_metrics = self._background_parse_bidders(extract_dir) or {}
            except Exception as e:
                # If bidder parsing fails, fail extraction (since user expects all models populated after extraction)
                raise e

            # Store extraction analytics (parsing only). Evaluation will append/override later.
            try:
                analytics = {
                    "jobId": self.name,
                    "stage": "extracted",
                    "companiesDetected": int(parse_metrics.get("companiesDetected") or self.companies_detected or 0),
                    "totalPdfReceived": int(parse_metrics.get("totalPdfReceived") or 0),
                    "totalValidPdfProcessed": int(parse_metrics.get("totalValidPdfProcessed") or 0),
                    "apiCallsTotal": int(parse_metrics.get("apiCallsTotal") or 0),
                    "tokensTotal": parse_metrics.get("tokensTotal") or {"promptTokens": 0, "outputTokens": 0, "totalTokens": 0},
                    "perCompany": parse_metrics.get("perCompany") or [],
                }
                self._safe_job_write({'analytics': json.dumps(analytics, ensure_ascii=False)})
            except Exception:
                pass

            # Mark extraction done
            self._safe_job_write({
                'state': 'extracted',
                'extraction_finished_on': fields.Datetime.now(),
            })
            try:
                self.env.cr.commit()
            except Exception:
                self.env.cr.rollback()

            _logger.info("TENDER AI [Job %s]: ✓ Extraction completed (tender + criteria + bidders saved)", self.name)
            return

        except Exception as e:
            reason = self._format_failure_reason(e)
            self.sudo().write({'state': 'failed', 'error_message': reason})
            try:
                self.message_post(body=f"<b>Tender AI extraction failed</b><br/><pre>{reason}</pre>", subtype_xmlid='mail.mt_note')
            except Exception:
                pass
            raise

    def _background_parse_bidders(self, extract_dir: str) -> dict:
        """Populate bidder-related models from extracted ZIP (no eligibility evaluation)."""
        if not extract_dir or not os.path.isdir(extract_dir):
            raise ValidationError('Extract directory not found. Run Extraction again.')

        jobs = self._collect_company_jobs(extract_dir)
        self._safe_job_write({'companies_detected': len(jobs)})

        company_workers = int(os.getenv("COMPANY_WORKERS", "4"))
        pdf_workers = int(os.getenv("PDF_WORKERS_PER_COMPANY", "5"))
        model = os.getenv("AI_COMPANY_MODEL") or os.getenv("GEMINI_COMPANY_MODEL") or "gemini-3-flash-preview"

        total_pdfs_received = 0
        total_valid_pdfs = 0
        total_calls = 0
        total_tokens = {"promptTokens": 0, "outputTokens": 0, "totalTokens": 0}
        per_company_analytics = []

        if jobs:
            for j in jobs:
                total_pdfs_received += len(j.get("pdf_paths") or [])

            with ThreadPoolExecutor(max_workers=company_workers) as ex:
                futures = [ex.submit(self._process_one_company, job, model, pdf_workers) for job in jobs]
                for fut in as_completed(futures):
                    if self._should_stop():
                        for remaining_fut in futures:
                            if not remaining_fut.done():
                                remaining_fut.cancel()
                        self.sudo().write({'state': 'cancelled', 'error_message': 'Processing cancelled by user'})
                        return {}

                    result = fut.result() or {}
                    company_name = result.get("companyName", "Unknown")
                    bidder_data = result.get("bidder") or {}
                    payments = result.get("payments") or []
                    work_exp = result.get("work_experience") or []
                    pdf_paths = result.get("_pdf_paths") or []

                    vendor_company_name = bidder_data.get('vendorCompanyName', '') or company_name
                    existing_bidder = self.env['tende_ai.bidder'].sudo().search([
                        ('job_id', '=', self.id),
                        ('vendor_company_name', '=', vendor_company_name)
                    ], limit=1)

                    if existing_bidder:
                        existing_bidder.write({
                            'company_address': bidder_data.get('companyAddress', '') or existing_bidder.company_address,
                            'email_id': bidder_data.get('emailId', '') or existing_bidder.email_id,
                            'contact_person': bidder_data.get('contactPerson', '') or existing_bidder.contact_person,
                            'contact_no': bidder_data.get('contactNo', '') or existing_bidder.contact_no,
                            'pan': bidder_data.get('pan', '') or existing_bidder.pan,
                            'gstin': bidder_data.get('gstin', '') or existing_bidder.gstin,
                            'place_of_registration': bidder_data.get('placeOfRegistration', '') or existing_bidder.place_of_registration,
                            'offer_validity_days': bidder_data.get('offerValidityDays', '') or existing_bidder.offer_validity_days,
                        })
                        bidder = existing_bidder
                    else:
                        bidder = self.env['tende_ai.bidder'].sudo().create({
                            'job_id': self.id,
                            'vendor_company_name': vendor_company_name,
                            'company_address': bidder_data.get('companyAddress', ''),
                            'email_id': bidder_data.get('emailId', ''),
                            'contact_person': bidder_data.get('contactPerson', ''),
                            'contact_no': bidder_data.get('contactNo', ''),
                            'pan': bidder_data.get('pan', ''),
                            'gstin': bidder_data.get('gstin', ''),
                            'place_of_registration': bidder_data.get('placeOfRegistration', ''),
                            'offer_validity_days': bidder_data.get('offerValidityDays', ''),
                        })

                    # Attach bidder PDFs automatically
                    try:
                        self._attach_company_pdfs_to_bidder(bidder, pdf_paths, extract_dir=extract_dir)
                    except Exception:
                        pass

                    # Batch create payments/work exp
                    if payments:
                        existing_transaction_ids = set(
                            self.env['tende_ai.payment'].sudo().search([('bidder_id', '=', bidder.id)]).mapped('transaction_id')
                        )
                        payment_records = []
                        for payment_data in payments:
                            transaction_id = (payment_data.get('transactionId', '') or '').strip()
                            if transaction_id and transaction_id in existing_transaction_ids:
                                continue
                            payment_records.append({
                                'bidder_id': bidder.id,
                                'vendor': payment_data.get('vendor', ''),
                                'payment_mode': payment_data.get('paymentMode', ''),
                                'bank_name': payment_data.get('bankName', ''),
                                'transaction_id': transaction_id,
                                'amount_inr': payment_data.get('amountINR', ''),
                                'transaction_date': payment_data.get('transactionDate', ''),
                                'status': payment_data.get('status', ''),
                            })
                        if payment_records:
                            self.env['tende_ai.payment'].sudo().create(payment_records)

                    if work_exp:
                        existing_work = self.env['tende_ai.work_experience'].sudo().search([('bidder_id', '=', bidder.id)])
                        existing_keys = set()
                        for w in existing_work:
                            existing_keys.add((w.name_of_work or '', w.employer or '', w.contract_amount_inr or '', w.date_of_start or ''))

                        work_records = []
                        for work_data in work_exp:
                            name_of_work = work_data.get('projectName') or work_data.get('nameOfWork') or work_data.get('name_of_work') or ''
                            employer = work_data.get('clientName') or work_data.get('employer') or ''
                            location = work_data.get('location') or work_data.get('scopeOfWork') or work_data.get('scope_of_work') or ''
                            key = (
                                name_of_work or '',
                                employer or '',
                                work_data.get('contractAmountINR', '') or '',
                                work_data.get('dateOfStart', '') or '',
                            )
                            if key in existing_keys:
                                continue
                            work_records.append({
                                'bidder_id': bidder.id,
                                'vendor_company_name': vendor_company_name,
                                'name_of_work': name_of_work,
                                'employer': employer,
                                'location': location,
                                'contract_amount_inr': work_data.get('contractAmountINR', ''),
                                'date_of_start': work_data.get('dateOfStart', ''),
                                'date_of_completion': work_data.get('dateOfCompletion', ''),
                                'completion_certificate': work_data.get('completionCertificate', ''),
                                'attachment': work_data.get('attachment', ''),
                            })
                        if work_records:
                            self.env['tende_ai.work_experience'].sudo().create(work_records)

                    # Commit after each bidder so UI updates
                    try:
                        self.env.cr.commit()
                    except Exception:
                        self.env.cr.rollback()

                    # Aggregate analytics
                    c_an = result.get("analytics") or {}
                    if isinstance(c_an, dict):
                        per_company_analytics.append(c_an)
                        total_valid_pdfs += int(c_an.get("validPdfCount") or 0)
                        total_calls += int(c_an.get("geminiCalls") or 0)
                        c_tokens = c_an.get("tokens") or {}
                        if isinstance(c_tokens, dict):
                            total_tokens = self._merge_tokens_total(total_tokens, c_tokens)

        return {
            "companiesDetected": len(jobs),
            "totalPdfReceived": total_pdfs_received,
            "totalValidPdfProcessed": total_valid_pdfs,
            "apiCallsTotal": total_calls,
            "tokensTotal": total_tokens,
            "perCompany": per_company_analytics,
        }

    def _background_evaluate_tender(self):
        """Evaluate eligibility criteria for already-extracted bidders (no bidder re-parsing)."""
        overall_t0 = time.time()
        _logger.info("TENDER AI [Job %s]: Background eligibility evaluation started", self.name)

        try:
            if self._should_stop():
                self.sudo().write({'state': 'cancelled', 'error_message': 'Processing cancelled by user'})
                return

            extract_dir = self.extract_dir
            if not extract_dir or not os.path.isdir(extract_dir):
                self.sudo().write({'state': 'failed', 'error_message': 'Extract directory not found. Run Extraction again.'})
                return

            # Eligibility evaluation per bidder (AI)
            criteria_recs = self.env['tende_ai.eligibility_criteria'].sudo().search([('job_id', '=', self.id)], order='sl_no')
            criteria = [{
                "slNo": c.sl_no,
                "criteria": c.criteria,
                "supportingDocument": c.supporting_document,
                "criteria_id": c.id,
            } for c in criteria_recs]

            Check = self.env['tende_ai.bidder_check'].sudo()
            Line = self.env['tende_ai.bidder_check_line'].sudo()
            # Clear old checks for this run
            Check.search([('job_id', '=', self.id)]).unlink()

            bidders = self.env['tende_ai.bidder'].sudo().search([('job_id', '=', self.id)])
            for bidder in bidders:
                if self._should_stop():
                    self.sudo().write({'state': 'cancelled', 'error_message': 'Processing cancelled by user'})
                    return

                # Collect bidder PDFs from attachments (preferred) or fallback to folder scan
                pdf_paths = []
                try:
                    # attachment names are relative to extract_dir
                    for att in bidder.attachment_ids:
                        name = att.name or ""
                        if name.lower().endswith(".pdf"):
                            abs_path = os.path.join(extract_dir, name) if extract_dir else None
                            if abs_path and os.path.isfile(abs_path):
                                pdf_paths.append(abs_path)
                except Exception:
                    pdf_paths = []

                if not pdf_paths:
                    # fallback: scan company folder
                    wanted = (bidder.vendor_company_name or '').strip().lower()
                    company_dir = None
                    try:
                        for name in os.listdir(extract_dir):
                            p = os.path.join(extract_dir, name)
                            if os.path.isdir(p) and name.strip().lower() == wanted:
                                company_dir = p
                                break
                        if company_dir:
                            for root, _, files in os.walk(company_dir):
                                for fn in files:
                                    if fn.lower().endswith('.pdf') and fn.lower() != 'tender.pdf':
                                        pdf_paths.append(os.path.join(root, fn))
                    except Exception:
                        pass

                check = Check.create({
                    'job_id': self.id,
                    'bidder_id': bidder.id,
                    'overall_result': 'unknown',
                    'total_criteria': len(criteria),
                    'processed_on': fields.Datetime.now(),
                })

                try:
                    bidder_facts = {
                        "companyName": bidder.vendor_company_name or "",
                        "email": bidder.email_id or "",
                        "phone": bidder.contact_no or "",
                        "pan": bidder.pan or "",
                        "gstin": bidder.gstin or "",
                        "placeOfRegistration": bidder.place_of_registration or "",
                        "offerValidityDays": bidder.offer_validity_days or "",
                        "payments": [
                            {
                                "vendor": p.vendor,
                                "paymentMode": p.payment_mode,
                                "bankName": p.bank_name,
                                "transactionId": p.transaction_id,
                                "amountINR": p.amount_inr,
                                "transactionDate": p.transaction_date,
                                "status": p.status,
                            }
                            for p in self.env['tende_ai.payment'].sudo().search([('bidder_id', '=', bidder.id)])
                        ],
                        "workExperience": [
                            {
                                "nameOfWork": w.name_of_work,
                                "employer": w.employer,
                                "location": w.location,
                                "contractAmountINR": w.contract_amount_inr,
                                "dateOfStart": w.date_of_start,
                                "dateOfCompletion": w.date_of_completion,
                                "completionCertificate": w.completion_certificate,
                                "attachment": w.attachment,
                            }
                            for w in self.env['tende_ai.work_experience'].sudo().search([('bidder_id', '=', bidder.id)])
                        ],
                        "attachmentNames": [a.name for a in (bidder.attachment_ids or [])],
                    }

                    eval_out = evaluate_bidder_against_criteria(
                        bidder_name=bidder.vendor_company_name or '',
                        bidder_facts=bidder_facts,
                        criteria=criteria,
                        pdf_paths=pdf_paths,
                        env=self.env,
                    )
                    res = (eval_out or {}).get("result") or {}
                    lines = res.get("lines") or []

                    passed = failed = unknown = 0
                    to_create = []
                    for ln in lines:
                        sl = (ln.get("slNo") or "").strip()
                        result = (ln.get("result") or "unknown").lower()
                        if result not in ("pass", "fail", "unknown"):
                            result = "unknown"
                        if result == "pass":
                            passed += 1
                        elif result == "fail":
                            failed += 1
                        else:
                            unknown += 1

                        crit_rec = None
                        for c in criteria:
                            if (c.get("slNo") or "").strip() == sl:
                                crit_rec = c
                                break

                        to_create.append({
                            'check_id': check.id,
                            'criteria_id': (crit_rec.get("criteria_id") if crit_rec else False),
                            'sl_no': sl,
                            'criteria': (crit_rec.get("criteria") if crit_rec else ''),
                            'supporting_document': (crit_rec.get("supportingDocument") if crit_rec else ''),
                            'result': result,
                            'reason': ln.get("reason", ''),
                            'evidence': ln.get("evidence", ''),
                            'missing_documents': "\n".join(ln.get("missingDocuments") or []) if isinstance(ln.get("missingDocuments"), list) else (ln.get("missingDocuments") or ''),
                        })

                    if to_create:
                        Line.create(to_create)

                    overall = res.get("overallResult") or "unknown"
                    overall = overall.lower()
                    if overall not in ("pass", "fail", "unknown"):
                        overall = "unknown"

                    check.write({
                        'overall_result': overall,
                        'passed_criteria': passed,
                        'failed_criteria': failed,
                        'unknown_criteria': unknown,
                        'duration_seconds': float((eval_out.get("durationMs") or 0)) / 1000.0,
                        'error_message': '',
                    })
                    try:
                        self.message_post(
                            body=f"<b>Eligibility evaluated</b><br/>Bidder: {bidder.vendor_company_name}<br/>Result: <b>{overall.upper()}</b>",
                            subtype_xmlid='mail.mt_note',
                        )
                    except Exception:
                        pass

                except Exception as e:
                    check.write({'overall_result': 'unknown', 'error_message': str(e)})

                try:
                    self.env.cr.commit()
                except Exception:
                    self.env.cr.rollback()

            # Update analytics (preserve parse analytics if present)
            overall_t1 = time.time()
            prev = {}
            try:
                if self.analytics:
                    prev = json.loads(self.analytics) if isinstance(self.analytics, str) else (self.analytics or {})
            except Exception:
                prev = {}
            if not isinstance(prev, dict):
                prev = {}
            prev.update({
                "stage": "processed",
                "eligibilityEvaluatedOn": fields.Datetime.now().isoformat(),
                "durationMs": int((overall_t1 - overall_t0) * 1000),
                "durationSeconds": round(overall_t1 - overall_t0, 3),
            })
            try:
                analytics_json = json.dumps(prev, ensure_ascii=False)
            except Exception:
                analytics_json = str(prev)

            self._safe_job_write({
                'analytics': analytics_json,
                'state': 'completed',
                'evaluation_finished_on': fields.Datetime.now(),
            })
            try:
                self.env.cr.commit()
            except Exception:
                self.env.cr.rollback()

        except Exception as e:
            reason = self._format_failure_reason(e)
            self.sudo().write({'state': 'failed', 'error_message': reason})
            try:
                self.message_post(body=f"<b>Tender AI evaluation failed</b><br/><pre>{reason}</pre>", subtype_xmlid='mail.mt_note')
            except Exception:
                pass
            raise

    def _background_process_bidders(self):
        """Backward-compatible combined flow: parse bidders + evaluate eligibility."""
        overall_t0 = time.time()
        _logger.info("TENDER AI [Job %s]: Background combined processing started", self.name)

        try:
            if self._should_stop():
                self.sudo().write({'state': 'cancelled', 'error_message': 'Processing cancelled by user'})
                return

            extract_dir = self.extract_dir
            if not extract_dir or not os.path.isdir(extract_dir):
                self.sudo().write({'state': 'failed', 'error_message': 'Extract directory not found. Run Extraction again.'})
                return

            parse_metrics = self._background_parse_bidders(extract_dir) or {}
            # keep parsing analytics too
            try:
                self._safe_job_write({'analytics': json.dumps(parse_metrics, ensure_ascii=False)})
            except Exception:
                pass
            self._background_evaluate_tender()

        except Exception as e:
            reason = self._format_failure_reason(e)
            self.sudo().write({'state': 'failed', 'error_message': reason})
            try:
                self.message_post(body=f"<b>Tender AI processing failed</b><br/><pre>{reason}</pre>", subtype_xmlid='mail.mt_note')
            except Exception:
                pass
            raise

            company_workers = int(os.getenv("COMPANY_WORKERS", "4"))
            pdf_workers = int(os.getenv("PDF_WORKERS_PER_COMPANY", "5"))
            model = os.getenv("AI_COMPANY_MODEL") or os.getenv("GEMINI_COMPANY_MODEL") or "gemini-3-flash-preview"
            _logger.info("TENDER AI [Job %s]: Processing configuration - Company Workers: %d, PDF Workers: %d, Model: configured", 
                        self.name, company_workers, pdf_workers)

            bidders = []
            payments_by_company = []
            work_experience_by_company = []

            # Analytics aggregation
            total_pdfs_received = 0
            total_valid_pdfs = 0
            total_gemini_calls = 0
            total_tokens = {"promptTokens": 0, "outputTokens": 0, "totalTokens": 0}
            per_company_analytics = []

            # Include tender tokens/calls first
            tender_analytics = tender_data.get("tenderAnalytics") or {}
            tender_tokens = (tender_analytics.get("tokens") or {}) if isinstance(tender_analytics, dict) else {}
            total_tokens = self._merge_tokens_total(total_tokens, tender_tokens)
            total_gemini_calls += 1

            if jobs:
                for j in jobs:
                    total_pdfs_received += len(j.get("pdf_paths") or [])
                _logger.info("TENDER AI [Job %s]: Total PDFs to process across all companies: %d", 
                            self.name, total_pdfs_received)

                _logger.info("TENDER AI [Job %s]: Starting parallel company processing", self.name)
                _logger.info("TENDER AI [Job %s]:   - Companies: %d", self.name, len(jobs))
                _logger.info("TENDER AI [Job %s]:   - Company Workers: %d", self.name, company_workers)
                _logger.info("TENDER AI [Job %s]:   - PDF Workers per Company: %d", self.name, pdf_workers)
                _logger.info("TENDER AI [Job %s]:   - Model: configured", self.name)
                
                # Check if processing was stopped before company processing
                if self._should_stop():
                    _logger.info("TENDER AI [Job %s]: Processing cancelled before company processing", self.name)
                    self.sudo().write({
                        'state': 'cancelled',
                        'error_message': 'Processing cancelled by user',
                    })
                    return
                
                with ThreadPoolExecutor(max_workers=company_workers) as ex:
                    futures = [
                        ex.submit(self._process_one_company, job, model, pdf_workers)
                        for job in jobs
                    ]

                    completed = 0
                    for fut in as_completed(futures):
                        # Check if processing was stopped
                        if self._should_stop():
                            _logger.info("TENDER AI [Job %s]: Processing cancelled during company processing", self.name)
                            _logger.info("TENDER AI [Job %s]: Cancelling remaining company processing tasks", self.name)
                            # Cancel remaining futures
                            for remaining_fut in futures:
                                if not remaining_fut.done():
                                    remaining_fut.cancel()
                            self.sudo().write({
                                'state': 'cancelled',
                                'error_message': 'Processing cancelled by user',
                            })
                            return
                        
                        try:
                            completed += 1
                            result = fut.result() or {}
                            company_name = result.get("companyName", "Unknown")
                            _logger.info("TENDER AI [Job %s]: ✓ Completed processing company %d/%d: %s", 
                                        self.name, completed, len(jobs), company_name)

                            # Prepare batch records for efficient database writes
                            bidder_data = result.get("bidder") or {}
                            payments = result.get("payments") or []
                            work_exp = result.get("work_experience") or []
                            pdf_paths = result.get("_pdf_paths") or []
                            
                            # Check if bidder already exists for this job (by company name)
                            vendor_company_name = bidder_data.get('vendorCompanyName', '') or company_name
                            existing_bidder = self.env['tende_ai.bidder'].sudo().search([
                                ('job_id', '=', self.id),
                                ('vendor_company_name', '=', vendor_company_name)
                            ], limit=1)
                            
                            if existing_bidder:
                                # Update existing bidder
                                _logger.debug("TENDER AI [Job %s]: Updating existing bidder: %s", 
                                            self.name, vendor_company_name)
                                existing_bidder.write({
                                    'company_address': bidder_data.get('companyAddress', '') or existing_bidder.company_address,
                                    'email_id': bidder_data.get('emailId', '') or existing_bidder.email_id,
                                    'contact_person': bidder_data.get('contactPerson', '') or existing_bidder.contact_person,
                                    'contact_no': bidder_data.get('contactNo', '') or existing_bidder.contact_no,
                                    'pan': bidder_data.get('pan', '') or existing_bidder.pan,
                                    'gstin': bidder_data.get('gstin', '') or existing_bidder.gstin,
                                    'place_of_registration': bidder_data.get('placeOfRegistration', '') or existing_bidder.place_of_registration,
                                    'offer_validity_days': bidder_data.get('offerValidityDays', '') or existing_bidder.offer_validity_days,
                                })
                                bidder = existing_bidder
                            else:
                                # Create new bidder record
                                bidder = self.env['tende_ai.bidder'].sudo().create({
                                    'job_id': self.id,
                                    'vendor_company_name': vendor_company_name,
                                    'company_address': bidder_data.get('companyAddress', ''),
                                    'email_id': bidder_data.get('emailId', ''),
                                    'contact_person': bidder_data.get('contactPerson', ''),
                                    'contact_no': bidder_data.get('contactNo', ''),
                                    'pan': bidder_data.get('pan', ''),
                                    'gstin': bidder_data.get('gstin', ''),
                                    'place_of_registration': bidder_data.get('placeOfRegistration', ''),
                                    'offer_validity_days': bidder_data.get('offerValidityDays', ''),
                                })
                                _logger.info("TENDER AI [Job %s]: ✓ Created bidder record: %s", self.name, vendor_company_name)

                            # Attach all extracted bidder PDFs (so user can preview/download on bidder form)
                            attached_count = 0
                            try:
                                attached_count = self._attach_company_pdfs_to_bidder(
                                    bidder, pdf_paths, extract_dir=getattr(self, 'extract_dir', None)
                                )
                            except Exception:
                                attached_count = 0
                            if attached_count:
                                _logger.info(
                                    "TENDER AI [Job %s]: ✓ Attached %d PDF(s) to bidder: %s",
                                    self.name, attached_count, vendor_company_name
                                )

                            # Batch create payment records (check for duplicates by transaction_id)
                            if payments:
                                payment_records = []
                                existing_transaction_ids = set(
                                    self.env['tende_ai.payment'].sudo().search([
                                        ('bidder_id', '=', bidder.id)
                                    ]).mapped('transaction_id')
                                )
                                
                                for payment_data in payments:
                                    transaction_id = payment_data.get('transactionId', '').strip()
                                    # Skip if payment with same transaction_id already exists
                                    if transaction_id and transaction_id in existing_transaction_ids:
                                        continue
                                    
                                    payment_records.append({
                                        'bidder_id': bidder.id,
                                        'vendor': payment_data.get('vendor', ''),
                                        'payment_mode': payment_data.get('paymentMode', ''),
                                        'bank_name': payment_data.get('bankName', ''),
                                        'transaction_id': transaction_id,
                                        'amount_inr': payment_data.get('amountINR', ''),
                                        'transaction_date': payment_data.get('transactionDate', ''),
                                        'status': payment_data.get('status', ''),
                                    })
                                if payment_records:
                                    self.env['tende_ai.payment'].sudo().create(payment_records)
                                    _logger.info("TENDER AI [Job %s]: ✓ Created %d payment record(s) for bidder: %s", 
                                                self.name, len(payment_records), vendor_company_name)

                            # Batch create work experience records (check for duplicates)
                            if work_exp:
                                work_records = []
                                # Get existing work experiences for deduplication
                                existing_work = self.env['tende_ai.work_experience'].sudo().search([
                                    ('bidder_id', '=', bidder.id)
                                ])
                                existing_work_keys = set()
                                for ew in existing_work:
                                    key = (
                                        (ew.name_of_work or '').lower().strip(),
                                        (ew.employer or '').lower().strip(),
                                        (ew.location or '').lower().strip(),
                                        (ew.date_of_start or '').lower().strip(),
                                    )
                                    existing_work_keys.add(key)
                                
                                for work_data in work_exp:
                                    # Create deduplication key
                                    work_key = (
                                        (work_data.get('nameOfWork', '') or '').lower().strip(),
                                        (work_data.get('employer', '') or '').lower().strip(),
                                        (work_data.get('location', '') or '').lower().strip(),
                                        (work_data.get('dateOfStart', '') or '').lower().strip(),
                                    )
                                    # Skip if duplicate
                                    if work_key in existing_work_keys:
                                        continue
                                    
                                    work_records.append({
                                        'bidder_id': bidder.id,
                                        'vendor_company_name': work_data.get('vendorCompanyName', ''),
                                        'name_of_work': work_data.get('nameOfWork', ''),
                                        'employer': work_data.get('employer', ''),
                                        'location': work_data.get('location', ''),
                                        'contract_amount_inr': work_data.get('contractAmountINR', ''),
                                        'date_of_start': work_data.get('dateOfStart', ''),
                                        'date_of_completion': work_data.get('dateOfCompletion', ''),
                                        'completion_certificate': work_data.get('completionCertificate', ''),
                                        'attachment': work_data.get('attachment', ''),
                                    })
                                if work_records:
                                    self.env['tende_ai.work_experience'].sudo().create(work_records)
                                    _logger.info("TENDER AI [Job %s]: ✓ Created %d work experience record(s) for bidder: %s", 
                                                self.name, len(work_records), vendor_company_name)
                            
                            # Log completion of bidder processing
                            payment_count = len(payments) if payments else 0
                            work_exp_count = len(work_exp) if work_exp else 0
                            _logger.info("TENDER AI [Job %s]: ✓ Bidder data processed - Company: %s, Payments: %d, Work Experience: %d", 
                                        self.name, vendor_company_name, payment_count, work_exp_count)
                            
                            # Try to commit after each company (but don't fail if it conflicts)
                            # Commit after each bidder to show data immediately
                            try:
                                self.env.cr.commit()
                                _logger.info("TENDER AI [Job %s]: ✓ Committed bidder data - %s is now visible in UI", self.name, vendor_company_name)
                            except Exception as commit_err:
                                # If commit fails, continue - data will be visible on next commit
                                _logger.debug("TENDER AI [Job %s]: Commit skipped (will commit later): %s", self.name, str(commit_err))
                                self.env.cr.rollback()

                            c_an = result.get("analytics") or {}
                            if isinstance(c_an, dict):
                                per_company_analytics.append(c_an)
                                total_valid_pdfs += int(c_an.get("validPdfCount") or 0)
                                total_gemini_calls += int(c_an.get("geminiCalls") or 0)

                                c_tokens = c_an.get("tokens") or {}
                                if isinstance(c_tokens, dict):
                                    total_tokens = self._merge_tokens_total(total_tokens, c_tokens)

                        except Exception:
                            continue

            # Final analytics
            overall_t1 = time.time()
            analytics = {
                "jobId": self.name,
                "durationMs": int((overall_t1 - overall_t0) * 1000),
                "durationSeconds": round(overall_t1 - overall_t0, 3),
                "companiesDetected": len(jobs),
                "totalPdfReceived": total_pdfs_received,
                "totalValidPdfProcessed": total_valid_pdfs,
                "geminiCallsTotal": total_gemini_calls,
                "tokensTotal": total_tokens,
                "perCompany": per_company_analytics,
            }

            # ✅ Completed
            overall_duration = time.time() - overall_t0
            _logger.info("TENDER AI [Job %s]: ✓ Processing completed successfully", self.name)
            _logger.info("TENDER AI [Job %s]:   - Total Duration: %.2f seconds (%.2f minutes)", 
                        self.name, overall_duration, overall_duration / 60)
            _logger.info("TENDER AI [Job %s]:   - Companies Processed: %d", self.name, len(jobs))
            _logger.info("TENDER AI [Job %s]:   - Total PDFs Processed: %d", self.name, total_valid_pdfs)
            _logger.info("TENDER AI [Job %s]:   - Total AI API Calls: %d", self.name, total_gemini_calls)
            _logger.info("TENDER AI [Job %s]:   - Total Tokens Used: %s", self.name, total_tokens)
            _logger.info("=" * 80)
            
            # Serialize analytics to JSON string properly
            try:
                analytics_json = json.dumps(analytics, ensure_ascii=False)
            except Exception as e:
                _logger.warning("TENDER AI [Job %s]: Failed to serialize analytics to JSON, using str(): %s", 
                              self.name, str(e))
                analytics_json = str(analytics)
            
            # Truncate analytics if too large to avoid database issues
            if len(analytics_json) > 50000:  # ~50KB limit
                simplified_analytics = analytics.copy()
                simplified_analytics['perCompany'] = [
                    {
                        'companyName': c.get('companyName', ''),
                        'durationMs': c.get('durationMs', 0),
                        'pdfCountReceived': c.get('pdfCountReceived', 0),
                        'validPdfCount': c.get('validPdfCount', 0),
                        'geminiCalls': c.get('geminiCalls', 0),
                        'tokens': c.get('tokens', {}),
                    }
                    for c in per_company_analytics
                ]
                analytics_json = json.dumps(simplified_analytics, ensure_ascii=False)
            
            # Write final state and analytics together (single write is faster)
            self.sudo().write({
                'state': 'completed',
                'error_message': '',
                'analytics': analytics_json,
            })

        except Exception as e:
            reason = self._format_failure_reason(e)
            error_msg = f"{reason}\n\n{traceback.format_exc()[:4000]}"
            _logger.error("TENDER AI [Job %s]: ✗ Processing failed with error", self.name)
            _logger.error("TENDER AI [Job %s]:   - Error: %s", self.name, str(e))
            _logger.error("TENDER AI [Job %s]:   - Traceback: %s", self.name, traceback.format_exc())
            _logger.info("=" * 80)
            
            self._safe_job_write({
                'state': 'failed',
                'error_message': error_msg,
            })
            try:
                self.message_post(
                    body=f"<b>Tender AI failed</b><br/><pre>{reason}</pre>",
                    subtype_xmlid='mail.mt_note',
                )
            except Exception:
                pass

    def _is_company_folder(self, name: str) -> bool:
        """Check if folder name represents a company"""
        if not name:
            return False
        if name.startswith("."):
            return False
        if name.lower() == "__macosx":
            return False
        return True

    def _collect_company_jobs(self, extract_dir: str) -> list:
        """
        Collect company folders and their PDF files.
        Structure expected:
          extract_dir/
            tender.pdf
            CompanyA/ (pdfs...)
            CompanyB/ (pdfs...)
        """
        jobs = []

        for name in os.listdir(extract_dir):
            if not self._is_company_folder(name):
                continue

            company_dir = os.path.join(extract_dir, name)
            if not os.path.isdir(company_dir):
                continue

            company_name = name.strip()

            pdf_paths = []
            for root, _, files in os.walk(company_dir):
                for fn in files:
                    if not fn.lower().endswith(".pdf"):
                        continue
                    if fn.lower() == "tender.pdf":
                        continue
                    pdf_paths.append(os.path.join(root, fn))

            if not pdf_paths:
                continue

            jobs.append({"company_name": company_name, "pdf_paths": pdf_paths})

        return jobs

    def _process_one_company(self, job: dict, model: str, pdf_workers: int) -> dict:
        """Process one company folder"""
        company_name = job.get("company_name", "")
        pdf_paths = job.get("pdf_paths", [])
        
        _logger.info("TENDER AI [Job %s]: Processing company: %s (%d PDFs)", 
                    self.name, company_name, len(pdf_paths))
        _logger.info("TENDER AI [Job %s]:   - Calling AI service: extract_company_bidder_and_payments()", 
                    self.name)
        _logger.info("TENDER AI [Job %s]:   - Company: %s", self.name, company_name)
        _logger.info("TENDER AI [Job %s]:   - PDFs: %d", self.name, len(pdf_paths))
        _logger.info("TENDER AI [Job %s]:   - Model: configured", self.name)
        _logger.info("TENDER AI [Job %s]:   - Workers: %d", self.name, pdf_workers)
        
        company_start_time = time.time()
        result = extract_company_bidder_and_payments(
            company_name=company_name,
            pdf_paths=pdf_paths,
            model=model,
            max_workers=pdf_workers,
            env=self.env,
        )
        # Ensure we always return a dict (attachments & downstream logic rely on it)
        if not isinstance(result, dict):
            result = {}
        company_duration = time.time() - company_start_time
        
        # Log company analytics
        analytics = result.get("analytics") or {}
        if isinstance(analytics, dict):
            gemini_calls = analytics.get("geminiCalls", 0)
            valid_pdfs = analytics.get("validPdfCount", 0)
            tokens = analytics.get("tokens") or {}
            _logger.info("TENDER AI [Job %s]: ✓ Company processing completed: %s", 
                        self.name, company_name)
            _logger.info("TENDER AI [Job %s]:   - Duration: %.2f seconds", self.name, company_duration)
            _logger.info("TENDER AI [Job %s]:   - AI API Calls: %d", self.name, gemini_calls)
            _logger.info("TENDER AI [Job %s]:   - Valid PDFs Processed: %d", self.name, valid_pdfs)
            _logger.info("TENDER AI [Job %s]:   - Tokens Used: %s", self.name, tokens)

        return {
            "companyName": company_name,
            "bidder": result.get("bidder") or {},
            "payments": result.get("payments") or [],
            "work_experience": result.get("work_experience") or [],
            "analytics": result.get("analytics") or {},
            # Critical: used by _attach_company_pdfs_to_bidder() to auto-create bidder attachments
            "_pdf_paths": pdf_paths,
        }

    def _safe_write(self, vals):
        """
        Simple write to database. Errors will be handled at job level.
        """
        try:
            self.sudo().write(vals)
        except Exception as e:
            # Log but don't retry - let job-level retry handle it
            _logger.warning("TENDER AI [Job %s]: Write failed: %s", self.name, str(e))
            raise

    def _merge_tokens_total(self, total: dict, incoming: dict) -> dict:
        """Merge token counts"""
        if not isinstance(total, dict):
            total = {"promptTokens": 0, "outputTokens": 0, "totalTokens": 0}
        if not isinstance(incoming, dict):
            return total

        def _to_int(v):
            try:
                return int(v)
            except Exception:
                return 0

        total["promptTokens"] += _to_int(incoming.get("promptTokens"))
        total["outputTokens"] += _to_int(incoming.get("outputTokens"))
        total["totalTokens"] += _to_int(incoming.get("totalTokens"))
        return total

