from odoo import models, fields

class ResCompany(models.Model):
    _inherit = 'res.company'

    backend_theme_level = fields.Char(
        string='Backend Theme Level',
        default='global_level',
        help='Backend theme level for the company.'
    )
