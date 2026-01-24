# -*- coding: utf-8 -*-

from odoo import models, fields, api
from datetime import datetime, timedelta
import json
import logging

_logger = logging.getLogger(__name__)


class TenderDashboard(models.TransientModel):
    _name = 'tende_ai.dashboard'
    _description = 'Tender AI Dashboard'
    
    @api.model
    def default_get(self, fields_list):
        """Create a default record to display dashboard"""
        res = super().default_get(fields_list)
        return res
    
    @api.model
    def get_dashboard_record(self):
        """Get or create a dashboard record for display"""
        # For TransientModel, we create a new record each time
        return self.create({})

    @api.model
    def get_stats(self):
        """
        Lightweight stats endpoint for OWL dashboard (RPC).
        Uses search_count/read_group where possible to avoid loading big recordsets.
        """
        Job = self.env["tende_ai.job"].sudo()
        Bidder = self.env["tende_ai.bidder"].sudo()
        Payment = self.env["tende_ai.payment"].sudo()
        Work = self.env["tende_ai.work_experience"].sudo()
        Tender = self.env["tende_ai.tender"].sudo()

        total_jobs = Job.search_count([])
        completed_jobs = Job.search_count([("state", "=", "completed")])
        extracting_jobs = Job.search_count([("state", "=", "extracting")])
        processing_jobs = Job.search_count([("state", "=", "processing")])
        extracted_jobs = Job.search_count([("state", "=", "extracted")])
        failed_jobs = Job.search_count([("state", "=", "failed")])
        cancelled_jobs = Job.search_count([("state", "=", "cancelled")])

        success_rate = (completed_jobs / total_jobs * 100.0) if total_jobs else 0.0

        total_bidders = Bidder.search_count([])
        # distinct companies (groupby on name)
        company_groups = Bidder.read_group([("vendor_company_name", "!=", False)], ["vendor_company_name"], ["vendor_company_name"])
        total_companies = len(company_groups or [])

        total_payments = Payment.search_count([])
        total_work_experience = Work.search_count([])

        # Tender states
        approved_tenders = Tender.search_count([("state", "=", "approved")])
        published_tenders = Tender.search_count([("state", "=", "published")])

        # Processing stats (from stored durations + analytics JSON best-effort)
        avg_processing_time = 0.0
        try:
            # processing_time_minutes is stored; use read_group for average
            grp = Job.read_group([("processing_time_minutes", ">", 0)], ["processing_time_minutes:avg"], [])
            avg_processing_time = float((grp[0] or {}).get("processing_time_minutes_avg") or 0.0) if grp else 0.0
        except Exception:
            avg_processing_time = 0.0

        total_pdfs = 0
        total_calls = 0
        total_tokens = 0
        # parse analytics for latest N jobs to keep it fast
        try:
            jobs = Job.search([("state", "=", "completed"), ("analytics", "!=", False)], order="create_date desc", limit=200)
            for j in jobs:
                try:
                    a = j.analytics
                    if isinstance(a, str):
                        a = json.loads(a)
                    if not isinstance(a, dict):
                        continue
                    total_pdfs += int(a.get("totalValidPdfProcessed", 0) or 0)
                    total_calls += int(a.get("geminiCallsTotal", 0) or 0)
                    tok = a.get("tokensTotal") or {}
                    if isinstance(tok, dict):
                        total_tokens += int(tok.get("totalTokens", 0) or 0)
                except Exception:
                    continue
        except Exception:
            pass

        return {
            "total_jobs": total_jobs,
            "completed_jobs": completed_jobs,
            "extracting_jobs": extracting_jobs,
            "extracted_jobs": extracted_jobs,
            "processing_jobs": processing_jobs,
            "failed_jobs": failed_jobs,
            "cancelled_jobs": cancelled_jobs,
            "success_rate": round(success_rate, 2),
            "total_companies": total_companies,
            "total_bidders": total_bidders,
            "total_payments": total_payments,
            "total_work_experience": total_work_experience,
            "approved_tenders": approved_tenders,
            "published_tenders": published_tenders,
            "total_pdfs_processed": total_pdfs,
            "total_ai_calls": total_calls,
            "total_tokens": total_tokens,
            "avg_processing_time_min": round(avg_processing_time, 2),
        }

    # KPI Fields - Overall Statistics
    total_jobs = fields.Integer(string='Total Jobs', compute='_compute_statistics', readonly=True)
    completed_jobs = fields.Integer(string='Completed Jobs', compute='_compute_statistics', readonly=True)
    processing_jobs = fields.Integer(string='Processing Jobs', compute='_compute_statistics', readonly=True)
    failed_jobs = fields.Integer(string='Failed Jobs', compute='_compute_statistics', readonly=True)
    success_rate = fields.Float(string='Success Rate (%)', compute='_compute_statistics', readonly=True)
    
    # Company & Bidder Statistics
    total_companies = fields.Integer(string='Total Companies', compute='_compute_statistics', readonly=True)
    total_bidders = fields.Integer(string='Total Bidders', compute='_compute_statistics', readonly=True)
    total_payments = fields.Integer(string='Total Payments', compute='_compute_statistics', readonly=True)
    total_work_experience = fields.Integer(string='Total Work Experience', compute='_compute_statistics', readonly=True)
    
    # Processing Statistics
    total_pdfs_processed = fields.Integer(string='Total PDFs Processed', compute='_compute_statistics', readonly=True)
    total_gemini_calls = fields.Integer(string='Total AI API Calls', compute='_compute_statistics', readonly=True)
    total_tokens_used = fields.Integer(string='Total Tokens Used', compute='_compute_statistics', readonly=True)
    avg_processing_time = fields.Float(string='Avg Processing Time (min)', compute='_compute_statistics', readonly=True)
    
    # Financial Statistics
    total_payment_amount = fields.Float(string='Total Payment Amount', compute='_compute_statistics', readonly=True)
    avg_payment_amount = fields.Float(string='Avg Payment Amount', compute='_compute_statistics', readonly=True)
    
    # Time-based Statistics
    jobs_today = fields.Integer(string='Jobs Today', compute='_compute_statistics', readonly=True)
    jobs_this_week = fields.Integer(string='Jobs This Week', compute='_compute_statistics', readonly=True)
    jobs_this_month = fields.Integer(string='Jobs This Month', compute='_compute_statistics', readonly=True)
    
    # Recent Activity
    last_processed_date = fields.Datetime(string='Last Processed', compute='_compute_statistics', readonly=True)
    fastest_processing_time = fields.Float(string='Fastest Processing (min)', compute='_compute_statistics', readonly=True)
    slowest_processing_time = fields.Float(string='Slowest Processing (min)', compute='_compute_statistics', readonly=True)

    @api.depends()
    def _compute_statistics(self):
        """Compute all dashboard statistics"""
        for record in self:
            # Job Statistics
            jobs = self.env['tende_ai.job'].search([])
            record.total_jobs = len(jobs)
            record.completed_jobs = len(jobs.filtered(lambda j: j.state == 'completed'))
            record.processing_jobs = len(jobs.filtered(lambda j: j.state == 'processing'))
            record.failed_jobs = len(jobs.filtered(lambda j: j.state == 'failed'))
            
            if record.total_jobs > 0:
                record.success_rate = (record.completed_jobs / record.total_jobs) * 100
            else:
                record.success_rate = 0.0
            
            # Company & Bidder Statistics
            bidders = self.env['tende_ai.bidder'].search([])
            record.total_bidders = len(bidders)
            
            # Get unique companies
            unique_companies = bidders.mapped('vendor_company_name')
            record.total_companies = len(set(unique_companies))
            
            # Payment Statistics
            payments = self.env['tende_ai.payment'].search([])
            record.total_payments = len(payments)
            
            # Calculate total payment amount (try to parse amount_inr)
            total_amount = 0.0
            valid_amounts = 0
            for payment in payments:
                try:
                    amount_str = payment.amount_inr or '0'
                    # Remove commas and currency symbols
                    amount_str = amount_str.replace(',', '').replace('₹', '').replace('INR', '').strip()
                    if amount_str:
                        amount = float(amount_str)
                        total_amount += amount
                        valid_amounts += 1
                except (ValueError, AttributeError):
                    continue
            
            record.total_payment_amount = total_amount
            record.avg_payment_amount = total_amount / valid_amounts if valid_amounts > 0 else 0.0
            
            # Work Experience Statistics
            work_exp = self.env['tende_ai.work_experience'].search([])
            record.total_work_experience = len(work_exp)
            
            # Processing Statistics from Analytics
            total_pdfs = 0
            total_calls = 0
            total_tokens = 0
            processing_times = []
            
            for job in jobs.filtered(lambda j: j.state == 'completed' and j.analytics):
                try:
                    analytics_str = job.analytics
                    if isinstance(analytics_str, str):
                        analytics = json.loads(analytics_str)
                    else:
                        analytics = analytics_str
                    
                    if isinstance(analytics, dict):
                        total_pdfs += int(analytics.get('totalValidPdfProcessed', 0) or 0)
                        total_calls += int(analytics.get('geminiCallsTotal', 0) or 0)
                        
                        tokens = analytics.get('tokensTotal', {})
                        if isinstance(tokens, dict):
                            total_tokens += int(tokens.get('totalTokens', 0) or 0)
                        
                        duration_sec = analytics.get('durationSeconds', 0) or 0
                        if duration_sec > 0:
                            processing_times.append(duration_sec / 60)  # Convert to minutes
                except (json.JSONDecodeError, ValueError, TypeError):
                    continue
            
            record.total_pdfs_processed = total_pdfs
            record.total_gemini_calls = total_calls
            record.total_tokens_used = total_tokens
            
            if processing_times:
                record.avg_processing_time = sum(processing_times) / len(processing_times)
                record.fastest_processing_time = min(processing_times)
                record.slowest_processing_time = max(processing_times)
            else:
                record.avg_processing_time = 0.0
                record.fastest_processing_time = 0.0
                record.slowest_processing_time = 0.0
            
            # Time-based Statistics
            today = datetime.now().date()
            week_ago = today - timedelta(days=7)
            month_ago = today - timedelta(days=30)
            
            jobs_today_list = jobs.filtered(lambda j: j.create_date and j.create_date.date() == today)
            jobs_week_list = jobs.filtered(lambda j: j.create_date and j.create_date.date() >= week_ago)
            jobs_month_list = jobs.filtered(lambda j: j.create_date and j.create_date.date() >= month_ago)
            
            record.jobs_today = len(jobs_today_list)
            record.jobs_this_week = len(jobs_week_list)
            record.jobs_this_month = len(jobs_month_list)
            
            # Last processed date
            completed_jobs_list = jobs.filtered(lambda j: j.state == 'completed')
            if completed_jobs_list:
                last_job = max(completed_jobs_list, key=lambda j: j.write_date or j.create_date)
                record.last_processed_date = last_job.write_date or last_job.create_date
            else:
                record.last_processed_date = False

    def action_open_jobs(self):
        """Open all jobs"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Tender Processing Jobs',
            'res_model': 'tende_ai.job',
            'view_mode': 'list,form',
            'domain': [],
        }

    def action_open_completed_jobs(self):
        """Open completed jobs"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Completed Jobs',
            'res_model': 'tende_ai.job',
            'view_mode': 'list,form',
            'domain': [('state', '=', 'completed')],
        }

    def action_open_bidders(self):
        """Open all bidders"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Bidders',
            'res_model': 'tende_ai.bidder',
            'view_mode': 'list,form',
            'domain': [],
        }

    def action_open_payments(self):
        """Open all payments"""
        return {
            'type': 'ir.actions.act_window',
            'name': 'Payments',
            'res_model': 'tende_ai.payment',
            'view_mode': 'list,form',
            'domain': [],
        }

