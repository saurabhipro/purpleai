# -*- coding: utf-8 -*-
"""Compatibility: allow searching ``ir.model`` by ``modules`` ("In Apps").

Odoo core defines ``ir.model.modules`` as a non-stored computed field. Custom
search views, saved filters, or Studio domains that reference ``modules`` then
raise: "Non-stored field ir.model.modules cannot be searched."  We store the
same computed value so SQL domains work; values are refreshed on module
install/upgrade via ``post_init_hook`` (see ``hooks.py``).
"""

from odoo import fields, models


class IrModel(models.Model):
    _inherit = "ir.model"

    modules = fields.Char(
        compute="_in_modules",
        string="In Apps",
        help="List of modules in which the object is defined or inherited",
        store=True,
        index=True,
    )
