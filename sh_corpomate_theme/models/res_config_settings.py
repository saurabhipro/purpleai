# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import fields, models, tools
import base64


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    sh_is_enable_bottom_nav_bar = fields.Boolean(
        related="website_id.sh_is_enable_bottom_nav_bar",
        string="Bottom Navigation Bar",
        readonly=False)

    sh_is_enable_toggle_zoom  = fields.Boolean(
        string='Is enable toggle zoom',
        related="website_id.sh_is_enable_toggle_zoom",
        readonly=False
        )

class Website(models.Model):
    _inherit = "website"

    sh_is_enable_bottom_nav_bar = fields.Boolean(
        "Bottom Navigation Bar",default=True)
    
    sh_is_enable_toggle_zoom  = fields.Boolean(
        string='Is enable toggle zoom',
        )
    


    def sh_corpomate_theme_default_logo_scrolled(self):
        with tools.file_open('website/static/src/img/website_logo.svg', 'rb') as logo_file:
            return base64.b64encode(logo_file.read())

    sh_corpomate_theme_logo_scrolled = fields.Binary(
        'Website Scrolled Logo', default=sh_corpomate_theme_default_logo_scrolled, help="Display this logo on the website when header scrolled down.")