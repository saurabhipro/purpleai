from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


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