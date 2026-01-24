# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class Tender(models.Model):
    _name = 'tende_ai.tender'
    _description = 'Tender Information'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    # Optional: tenders can be created manually (without a job) or generated from a Tender AI Job
    job_id = fields.Many2one('tende_ai.job', string='Job', required=False, ondelete='set null', readonly=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('in_review', 'In Review'),
        ('approved', 'Approved'),
        ('published', 'Published'),
        ('rejected', 'Rejected'),
    ], string='Status', default='draft', tracking=True, required=True)

    approved_by = fields.Many2one('res.users', string='Approved By', readonly=True, tracking=True)
    approved_on = fields.Datetime(string='Approved On', readonly=True, tracking=True)
    published_by = fields.Many2one('res.users', string='Published By', readonly=True, tracking=True)
    published_on_dt = fields.Datetime(string='Published On (Workflow)', readonly=True, tracking=True)
    
    # Basic Information
    department_name = fields.Char(string='Department Name', tracking=True)
    tender_id = fields.Char(string='Tender ID', tracking=True, index=True)
    ref_no = fields.Char(string='Reference Number', tracking=True, index=True)
    tender_creator = fields.Char(string='Tender Creator', tracking=True)
    
    # Classification
    procurement_category = fields.Char(string='Procurement Category', tracking=True)
    tender_type = fields.Char(string='Tender Type', tracking=True)
    organization_hierarchy = fields.Char(string='Organization Hierarchy', tracking=True)
    
    # Financial Information
    estimated_value_inr = fields.Char(string='Estimated Value (INR)', tracking=True)
    tender_currency = fields.Char(string='Tender Currency', tracking=True)
    bidding_currency = fields.Char(string='Bidding Currency', tracking=True)
    offer_validity_days = fields.Char(string='Offer Validity (Days)', tracking=True)
    
    # Reference Information
    previous_tender_no = fields.Char(string='Previous Tender Number', tracking=True)
    
    # Dates
    published_on = fields.Char(string='Published On', tracking=True)
    bid_submission_start = fields.Char(string='Bid Submission Start', tracking=True)
    bid_submission_end = fields.Char(string='Bid Submission End', tracking=True)
    tender_opened_on = fields.Char(string='Tender Opened On', tracking=True)
    
    # Description
    description = fields.Text(string='Description', tracking=True)
    nit = fields.Text(string='NIT', tracking=True)
    details_html = fields.Html(string='Tender Details (Rich Text)', tracking=True, sanitize=False)
    
    # Analytics
    analytics = fields.Text(string='Analytics (JSON)', readonly=True)
    
    # Related Records
    eligibility_criteria = fields.One2many('tende_ai.eligibility_criteria', 'tender_id', string='Eligibility Criteria')

    def action_submit_for_approval(self):
        for rec in self:
            if rec.state != 'draft':
                continue
            rec.write({'state': 'in_review'})

    def action_approve(self):
        for rec in self:
            if rec.state != 'in_review':
                raise ValidationError(_("Only tenders in 'In Review' can be approved."))
            rec.write({
                'state': 'approved',
                'approved_by': self.env.user.id,
                'approved_on': fields.Datetime.now(),
            })

    def action_reject(self):
        for rec in self:
            if rec.state not in ('in_review', 'approved'):
                raise ValidationError(_("Only tenders in 'In Review' or 'Approved' can be rejected."))
            rec.write({'state': 'rejected'})

    def action_publish(self):
        for rec in self:
            if rec.state != 'approved':
                raise ValidationError(_("Only approved tenders can be published."))
            rec.write({
                'state': 'published',
                'published_by': self.env.user.id,
                'published_on_dt': fields.Datetime.now(),
            })

    def action_reset_to_draft(self):
        for rec in self:
            rec.write({
                'state': 'draft',
                'approved_by': False,
                'approved_on': False,
                'published_by': False,
                'published_on_dt': False,
            })

