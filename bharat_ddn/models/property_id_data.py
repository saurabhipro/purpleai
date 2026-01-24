from odoo import models, fields

class PropertyIdData(models.Model):
    _name = 'property.id.data'
    _description = 'Imported Property ID Data'
    _rec_name = 'property_id'
    
    property_id = fields.Char('Property ID', required=True)
    owner_name = fields.Char('Owner Name')
    address = fields.Char('Address')
    ward_id = fields.Many2one('ddn.ward', string='Ward')
    zone_id = fields.Many2one('ddn.zone', string='Zone')
    mobile_no = fields.Char('Mobile No')
    currnet_tax = fields.Float('Current Tax')
    total_amount = fields.Float('Total Amount')
    
    _sql_constraints = [
        ('unique_property_id', 'unique(property_id)', 'The Property ID must be unique!'),
    ] 