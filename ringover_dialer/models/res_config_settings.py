# -*- coding: utf-8 -*-

from odoo import fields, models, api

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    ringover_size = fields.Selection([
        ('small', 'Small'),
        ('medium', 'Medium'),
        ('big', 'Big'),
        ('auto', 'Auto (Fullscreen)')
    ], string="Dialer Size", config_parameter='ringover.size', default='medium')

    ringover_position_bottom = fields.Char(string="Bottom Position (px/%)", config_parameter='ringover.bottom', default='0px')
    ringover_position_right = fields.Char(string="Right Position (px/%)", config_parameter='ringover.right', default='0px')

    ringover_show_tray = fields.Boolean(string="Show Launcher Icon", config_parameter='ringover.show_tray', default=True)
