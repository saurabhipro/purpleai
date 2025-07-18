from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


class LARRVillage(models.Model):
    _name = 'larr.village'
    _description = 'Village Master'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char('Village Name', required=True, tracking=True)
    tehsil = fields.Char('Tehsil', required=True, tracking=True)
    district_id = fields.Many2one('larr.district', 'District', required=True, tracking=True)
    sarpanch_name = fields.Char('Sarpanch Name', tracking=True)
    contact = fields.Char('Contact', tracking=True)
    
    # Status
    state = fields.Selection([
        ('active', 'Active'),
        ('inactive', 'Inactive')
    ], default='active', tracking=True)
    
    # Additional Details
    population = fields.Integer('Population', tracking=True)
    area_hectares = fields.Float('Area (Hectares)', tracking=True)
    gram_panchayat_code = fields.Char('Gram Panchayat Code', tracking=True)
    
    # Location Details
    latitude = fields.Float('Latitude', tracking=True)
    longitude = fields.Float('Longitude', tracking=True)
    
    # Documents
    document_ids = fields.Many2many('ir.attachment', string='Documents')
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name'):
                vals['name'] = _('New Village')
        return super().create(vals_list)
    
    def action_activate(self):
        self.write({'state': 'active'})
    
    def action_deactivate(self):
        self.write({'state': 'inactive'})
    
    @api.constrains('contact')
    def _check_contact(self):
        for record in self:
            if record.contact and not record.contact.isdigit():
                raise ValidationError(_('Contact number should contain only digits.'))
    
    @api.constrains('latitude', 'longitude')
    def _check_coordinates(self):
        for record in self:
            if record.latitude and (record.latitude < -90 or record.latitude > 90):
                raise ValidationError(_('Latitude must be between -90 and 90 degrees.'))
            if record.longitude and (record.longitude < -180 or record.longitude > 180):
                raise ValidationError(_('Longitude must be between -180 and 180 degrees.')) 