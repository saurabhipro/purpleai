from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


class LARRLandAcquisition(models.Model):
    _name = 'larr.land.acquisition'
    _description = 'Land Acquisition'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char('Acquisition Reference', required=True, copy=False, readonly=True, 
                      default=lambda self: _('New'))
    project_id = fields.Many2one('larr.project', 'Project', required=True, tracking=True)
    
    # Land Details
    land_owner_id = fields.Many2one('res.partner', 'Land Owner', required=True, tracking=True)
    land_address = fields.Text('Land Address', required=True, tracking=True)
    land_area = fields.Float('Land Area (Acres)', required=True, tracking=True)
    land_type = fields.Selection([
        ('agricultural', 'Agricultural'),
        ('residential', 'Residential'),
        ('commercial', 'Commercial'),
        ('industrial', 'Industrial'),
        ('forest', 'Forest'),
        ('wasteland', 'Wasteland'),
        ('other', 'Other')
    ], required=True, tracking=True)
    
    # Acquisition Details
    acquisition_date = fields.Date('Acquisition Date', tracking=True)
    acquisition_type = fields.Selection([
        ('voluntary', 'Voluntary'),
        ('compulsory', 'Compulsory'),
        ('negotiated', 'Negotiated')
    ], required=True, tracking=True)
    
    # Compensation Details
    compensation_amount = fields.Monetary('Compensation Amount', currency_field='currency_id', tracking=True)
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)
    compensation_status = fields.Selection([
        ('pending', 'Pending'),
        ('partial', 'Partial'),
        ('completed', 'Completed')
    ], default='pending', tracking=True)
    
    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('survey', 'Survey'),
        ('negotiation', 'Negotiation'),
        ('agreement', 'Agreement'),
        ('possession', 'Possession'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled')
    ], default='draft', tracking=True)
    
    # Documents
    document_ids = fields.Many2many('ir.attachment', string='Documents')
    
    # Related Records
    rehabilitation_ids = fields.One2many('larr.rehabilitation', 'acquisition_id', string='Rehabilitations')
    compensation_ids = fields.One2many('larr.compensation', 'acquisition_id', string='Compensations')
    
    # Computed Fields
    rehabilitation_count = fields.Integer(compute='_compute_counts')
    compensation_count = fields.Integer(compute='_compute_counts')
    
    @api.depends('rehabilitation_ids', 'compensation_ids')
    def _compute_counts(self):
        for record in self:
            record.rehabilitation_count = len(record.rehabilitation_ids)
            record.compensation_count = len(record.compensation_ids)
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('larr.land.acquisition') or _('New')
        return super().create(vals_list)
    
    def action_survey(self):
        self.write({'state': 'survey'})
    
    def action_negotiation(self):
        self.write({'state': 'negotiation'})
    
    def action_agreement(self):
        self.write({'state': 'agreement'})
    
    def action_possession(self):
        self.write({'state': 'possession'})
    
    def action_complete(self):
        self.write({'state': 'completed'})
    
    def action_cancel(self):
        self.write({'state': 'cancelled'})


class LARRRehabilitation(models.Model):
    _name = 'larr.rehabilitation'
    _description = 'Rehabilitation and Resettlement'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char('Rehabilitation Reference', required=True, copy=False, readonly=True, 
                      default=lambda self: _('New'))
    project_id = fields.Many2one('larr.project', 'Project', required=True, tracking=True)
    acquisition_id = fields.Many2one('larr.land.acquisition', 'Land Acquisition', tracking=True)
    
    # Affected Person Details
    affected_person_id = fields.Many2one('res.partner', 'Affected Person', required=True, tracking=True)
    family_members = fields.Integer('Number of Family Members', tracking=True)
    
    # Current Residence
    current_address = fields.Text('Current Address', tracking=True)
    current_land_area = fields.Float('Current Land Area (Acres)', tracking=True)
    current_house_type = fields.Selection([
        ('pucca', 'Pucca House'),
        ('semi_pucca', 'Semi-Pucca House'),
        ('kutcha', 'Kutcha House'),
        ('hut', 'Hut'),
        ('other', 'Other')
    ], tracking=True)
    
    # Rehabilitation Plan
    rehabilitation_type = fields.Selection([
        ('land_for_land', 'Land for Land'),
        ('house_for_house', 'House for House'),
        ('monetary', 'Monetary Compensation'),
        ('employment', 'Employment'),
        ('other', 'Other')
    ], required=True, tracking=True)
    
    # New Residence
    new_address = fields.Text('New Address', tracking=True)
    new_land_area = fields.Float('New Land Area (Acres)', tracking=True)
    new_house_type = fields.Selection([
        ('pucca', 'Pucca House'),
        ('semi_pucca', 'Semi-Pucca House'),
        ('kutcha', 'Kutcha House'),
        ('hut', 'Hut'),
        ('other', 'Other')
    ], tracking=True)
    
    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('survey', 'Survey'),
        ('planning', 'Planning'),
        ('implementation', 'Implementation'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled')
    ], default='draft', tracking=True)
    
    # Dates
    survey_date = fields.Date('Survey Date', tracking=True)
    planning_date = fields.Date('Planning Date', tracking=True)
    implementation_date = fields.Date('Implementation Date', tracking=True)
    completion_date = fields.Date('Completion Date', tracking=True)
    
    # Documents
    document_ids = fields.Many2many('ir.attachment', string='Documents')
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('larr.rehabilitation') or _('New')
        return super().create(vals_list)
    
    def action_survey(self):
        self.write({'state': 'survey'})
    
    def action_planning(self):
        self.write({'state': 'planning'})
    
    def action_implementation(self):
        self.write({'state': 'implementation'})
    
    def action_complete(self):
        self.write({'state': 'completed'})
    
    def action_cancel(self):
        self.write({'state': 'cancelled'})


class LARRCompensation(models.Model):
    _name = 'larr.compensation'
    _description = 'Compensation Management'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char('Compensation Reference', required=True, copy=False, readonly=True, 
                      default=lambda self: _('New'))
    acquisition_id = fields.Many2one('larr.land.acquisition', 'Land Acquisition', required=True, tracking=True)
    beneficiary_id = fields.Many2one('res.partner', 'Beneficiary', required=True, tracking=True)
    
    # Compensation Details
    compensation_type = fields.Selection([
        ('land', 'Land Compensation'),
        ('structure', 'Structure Compensation'),
        ('crop', 'Crop Compensation'),
        ('livelihood', 'Livelihood Compensation'),
        ('other', 'Other')
    ], required=True, tracking=True)
    
    amount = fields.Monetary('Amount', currency_field='currency_id', required=True, tracking=True)
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)
    
    # Payment Details
    payment_method = fields.Selection([
        ('bank_transfer', 'Bank Transfer'),
        ('cheque', 'Cheque'),
        ('cash', 'Cash'),
        ('other', 'Other')
    ], tracking=True)
    
    payment_date = fields.Date('Payment Date', tracking=True)
    payment_reference = fields.Char('Payment Reference', tracking=True)
    
    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('paid', 'Paid'),
        ('cancelled', 'Cancelled')
    ], default='draft', tracking=True)
    
    # Documents
    document_ids = fields.Many2many('ir.attachment', string='Documents')
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('larr.compensation') or _('New')
        return super().create(vals_list)
    
    def action_approve(self):
        self.write({'state': 'approved'})
    
    def action_pay(self):
        self.write({'state': 'paid'})
    
    def action_cancel(self):
        self.write({'state': 'cancelled'})


class LARRStakeholder(models.Model):
    _name = 'larr.stakeholder'
    _description = 'Stakeholder Management'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char('Stakeholder Name', required=True, tracking=True)
    project_id = fields.Many2one('larr.project', 'Project', required=True, tracking=True)
    partner_id = fields.Many2one('res.partner', 'Partner', tracking=True)
    
    # Stakeholder Details
    stakeholder_type = fields.Selection([
        ('land_owner', 'Land Owner'),
        ('affected_person', 'Affected Person'),
        ('government', 'Government Official'),
        ('contractor', 'Contractor'),
        ('consultant', 'Consultant'),
        ('other', 'Other')
    ], required=True, tracking=True)
    
    contact_person = fields.Char('Contact Person', tracking=True)
    phone = fields.Char('Phone', tracking=True)
    email = fields.Char('Email', tracking=True)
    address = fields.Text('Address', tracking=True)
    
    # Engagement
    engagement_level = fields.Selection([
        ('high', 'High'),
        ('medium', 'Medium'),
        ('low', 'Low')
    ], tracking=True)
    
    concerns = fields.Text('Concerns/Risks', tracking=True)
    mitigation_plan = fields.Text('Mitigation Plan', tracking=True)
    
    # Status
    state = fields.Selection([
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('resolved', 'Resolved')
    ], default='active', tracking=True)
    
    # Documents
    document_ids = fields.Many2many('ir.attachment', string='Documents') 