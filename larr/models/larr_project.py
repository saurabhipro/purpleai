from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


class LARRProject(models.Model):
    _name = 'larr.project'
    _description = 'LARR Project'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char('Project Name', required=True, tracking=True)
    code = fields.Char('Project Code', required=True, tracking=True)
    description = fields.Text('Description')
    start_date = fields.Date('Start Date', tracking=True)
    end_date = fields.Date('End Date', tracking=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled')
    ], default='draft', tracking=True)
    
    # Project Details
    project_type = fields.Selection([
        ('infrastructure', 'Infrastructure'),
        ('industrial', 'Industrial'),
        ('residential', 'Residential'),
        ('commercial', 'Commercial'),
        ('agricultural', 'Agricultural'),
        ('other', 'Other')
    ], required=True, tracking=True)
    
    total_area_required = fields.Float('Total Area Required (Acres)', tracking=True)
    estimated_cost = fields.Monetary('Estimated Cost', currency_field='currency_id', tracking=True)
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)
    
    # Team
    project_manager_id = fields.Many2one('hr.employee', 'Project Manager', tracking=True)
    team_member_ids = fields.Many2many('hr.employee', string='Team Members')
    
    # Related Records
    acquisition_ids = fields.One2many('larr.land.acquisition', 'project_id', string='Land Acquisitions')
    rehabilitation_ids = fields.One2many('larr.rehabilitation', 'project_id', string='Rehabilitations')
    stakeholder_ids = fields.One2many('larr.stakeholder', 'project_id', string='Stakeholders')
    
    # Computed Fields
    acquisition_count = fields.Integer(compute='_compute_counts')
    rehabilitation_count = fields.Integer(compute='_compute_counts')
    stakeholder_count = fields.Integer(compute='_compute_counts')
    progress_percentage = fields.Float(compute='_compute_progress', string='Progress %')
    
    @api.depends('acquisition_ids', 'rehabilitation_ids', 'stakeholder_ids')
    def _compute_counts(self):
        for record in self:
            record.acquisition_count = len(record.acquisition_ids)
            record.rehabilitation_count = len(record.rehabilitation_ids)
            record.stakeholder_count = len(record.stakeholder_ids)
    
    @api.depends('acquisition_ids.state', 'rehabilitation_ids.state')
    def _compute_progress(self):
        for record in self:
            total_acquisitions = len(record.acquisition_ids)
            completed_acquisitions = len(record.acquisition_ids.filtered(lambda x: x.state == 'completed'))
            
            if total_acquisitions > 0:
                record.progress_percentage = (completed_acquisitions / total_acquisitions) * 100
            else:
                record.progress_percentage = 0.0 