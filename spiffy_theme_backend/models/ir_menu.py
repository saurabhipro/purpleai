# -*- coding: utf-8 -*-
# Developed by Bizople Solutions Pvt. Ltd.
# See LICENSE file for full copyright and licensing details

from odoo import models, fields, api

class IrUiMenu(models.Model):
    _inherit = "ir.ui.menu"

    icon_img = fields.Image("Menu New Image")
    use_icon = fields.Boolean("Use Icon")
    icon_class_name = fields.Char("Icon Class Name")
    spiffy_app_group_id = fields.Many2one("spiffy.app.group", name="Spiffy App Group")
    spiffy_app_group = fields.Char("Spiffy App Groups")
    app_menu_list = fields.Char("Spiffy App Groups List")
