from odoo import models, fields

class AradaConfig(models.Model):
    _name = 'arada.config'
    _description = 'Arada Configuration'
    
    name = fields.Char(string='Name', required=True)
    description = fields.Text(string='Description')
    active = fields.Boolean(string='Active', default=True) 