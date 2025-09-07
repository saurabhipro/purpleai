from odoo import models, api, fields, _



class PortalOderLine(models.Model):
    _name = 'portal.order.line'
    _description = 'Portal Order Line'

    active = fields.Boolean(
        'Active', default=True,
        help="If unchecked, it will allow you to hide the product without removing it.")    
    product_template_id = fields.Many2one('product.template', string="Product")
    name = fields.Char(string="Description", related="product_template_id.name")
    order_line_image = fields.Binary(string="Product Image", related="product_template_id.image_1920")
    product_uom_qty = fields.Float(string="Quantity", default=1.0)
    product_uom = fields.Many2one('uom.uom', string="UOM", related="product_template_id.uom_id")
    price_unit = fields.Float(string="Price Unit", related="product_template_id.list_price")
    sequence = fields.Integer(default=1)



