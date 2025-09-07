# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import models, fields, api


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    ml_number = fields.Integer(string="##")
    sh_product_img = fields.Image(
        string="Image", compute="_compute_get_product_image")

    def _compute_get_product_image(self):
        for rec in self:
            rec.sh_product_img = rec.product_id.image_128

    @api.onchange('product_id')
    def _inverse_product_id(self):
        res = super(AccountMoveLine, self)._inverse_product_id()
        for record in self:
            if(
                record and
                record.product_id
            ):
                if(
                    record and
                    record.move_id and
                    not record.move_id.sh_print_taxes and
                    record.tax_ids
                ):

                    record.tax_ids = [(5, 0, 0)]
            record.sh_product_img = record.product_id.image_128 if record else False

        return res

class AccountMove(models.Model):
    _inherit = "account.move"


    sh_print_taxes = fields.Boolean(string="Print Taxes",related="company_id.sh_print_taxes",readonly=False)
    sh_print_line_no = fields.Boolean(string="Print Serial Number", related="company_id.sh_print_line_no",readonly=False)
    sh_print_product_img = fields.Boolean(string="Print Product Image", related="company_id.sh_print_product_img",readonly=False)
    sh_image_size = fields.Selection([
        ('small', 'Small'),
        ('medium', 'Medium'),
        ('large', 'Large'),
    ],
        string="Print Image Size",
        related="company_id.sh_image_size",readonly=False
    )
    sh_dummy = fields.Boolean(
        string="dummy_fields",
        compute="_compute_onchange_compute_line_number",
        invisible=True,
        default=True
    )

    @api.depends('invoice_line_ids', 'amount_total')
    def _compute_onchange_compute_line_number(self):
        if(
            self and
            self.invoice_line_ids
        ):
            number = 1
            for line in self.invoice_line_ids:
                line.ml_number = number
                line.update({'ml_number': number})
                number += 1
            self.sh_dummy = True
        else:
            self.sh_dummy = False

    @api.onchange('sh_print_taxes')
    def _onchange_remove_taxes(self):
        if(
            self and
            not self.sh_print_taxes and
            self.invoice_line_ids
        ):
            for line in self.invoice_line_ids:
                if line.tax_ids:
                    line.update({'tax_ids': [(5, 0, 0)]})
