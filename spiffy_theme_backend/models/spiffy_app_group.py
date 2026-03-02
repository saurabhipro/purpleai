# -*- coding: utf-8 -*-
# Part of Odoo Module Developed by Bizople Solutions Pvt. Ltd.
# See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api
from odoo.exceptions import UserError

class SpiffyAppGroup(models.Model):
    _name = 'spiffy.app.group'
    _description = 'Spiffy App Group'
    _order = 'sequence'

    name = fields.Char(string='Name', required=True)
    group_menu_icon = fields.Binary(string='Group Menu Icon') 
    group_menu_list_ids = fields.One2many(
        'ir.ui.menu', 'spiffy_app_group_id', string='Group Menu List', domain=[('parent_id', '=', False)]
    )
    use_group_icon = fields.Boolean(string="Use Group Icon")
    group_icon_class_name = fields.Char(string="Group Icon Class Name")
    sequence = fields.Integer(string="Sequence", default=10)

    @api.onchange('group_menu_list_ids')
    def _onchange_group_menu_list_ids(self):
        current_menu_ids = self.group_menu_list_ids.ids
        app_groups = self.env['spiffy.app.group'].search([
                ('id','not in', self.ids), ('group_menu_list_ids', 'in', current_menu_ids)
            ])
        if app_groups:
            raise UserError(f"The menu is already assigned to another group. Please select unique menus.")
