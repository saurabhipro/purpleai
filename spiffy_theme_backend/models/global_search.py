# -*- coding: utf-8 -*-
# See LICENSE file for full copyright and licensing details.
# Developed by Bizople Solutions Pvt. Ltd.

from odoo import fields, models, api

import logging
_logger = logging.getLogger(__name__)


class GlobalSearch(models.Model):
    _name = "global.search.bizople"
    _description = "Global Search"

    name = fields.Char(string="Name")
    global_model_id = fields.Many2one('ir.model', string="Model", domain="[('transient', '=', False)]")
    global_field_ids = fields.Many2many('ir.model.fields', domain="[('model_id', '=', global_model_id), ('store', '=', True), ('ttype', '!=', 'binary')]")

    @api.onchange('global_model_id')
    def _onchange_global_model_id(self):
        for rec in self:
            if rec.global_field_ids:
                rec.global_field_ids = [(5, 0, 0)]  # Clears the many2many field
