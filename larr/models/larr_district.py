from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


class LARRDistrict(models.Model):
    _name = 'larr.district'
    _description = 'LARR District'
    _order = 'name'
    _rec_name = 'name'

    name = fields.Char('District Name', required=True, tracking=True)
    code = fields.Char('District Code', tracking=True)
    state_id = fields.Many2one('res.country.state', 'State', required=True, tracking=True)
    description = fields.Text('Description')
    active = fields.Boolean('Active', default=True, tracking=True)
    
    # Related fields
    village_ids = fields.One2many('larr.village', 'district_id', string='Villages')
    survey_ids = fields.One2many('larr.survey', 'district_id', string='Surveys')
    village_count = fields.Integer(compute='_compute_village_count', string='Village Count')
    survey_count = fields.Integer(compute='_compute_survey_count', string='Survey Count')
    
    @api.depends('village_ids')
    def _compute_village_count(self):
        for record in self:
            record.village_count = len(record.village_ids)
    
    @api.depends('survey_ids')
    def _compute_survey_count(self):
        for record in self:
            record.survey_count = len(record.survey_ids)
    
    _sql_constraints = [
        ('name_uniq', 'unique(name, state_id)', 'District name must be unique per state!'),
        ('code_uniq', 'unique(code)', 'District code must be unique!'),
    ]
    
    def name_get(self):
        result = []
        for record in self:
            name = record.name
            if record.code:
                name = f"[{record.code}] {record.name}"
            result.append((record.id, name))
        return result 