# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import models, fields

class sh_res_company(models.Model):
    _inherit = "res.company"

    sh_print_taxes = fields.Boolean(string="Print Taxes")
    sh_print_line_no = fields.Boolean(string="Print Serial Number")
    sh_print_product_img = fields.Boolean(string="Print Product Image")
    sh_image_size = fields.Selection([
        ('small', 'Small'),
        ('medium', 'Medium'),
        ('large', 'Large'),
    ],
        default='small',
        string="Print Image Size"
    )


class sh_res_config(models.TransientModel):
    _inherit = "res.config.settings"

    sh_print_taxes = fields.Boolean(string="Print Taxes",related="company_id.sh_print_taxes",readonly=False)
    sh_print_line_no = fields.Boolean(string="Print Serial Number",related="company_id.sh_print_line_no",readonly=False)
    sh_print_product_img = fields.Boolean(string="Print Product Image",related="company_id.sh_print_product_img",readonly=False)
    sh_image_size = fields.Selection([
        ('small', 'Small'),
        ('medium', 'Medium'),
        ('large', 'Large'),
    ],
        string="Print Image Size",
        related="company_id.sh_image_size",readonly=False
    )
