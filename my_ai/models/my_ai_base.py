# -*- coding: utf-8 -*-

from odoo import models, fields, api


class MyAIBase(models.Model):
    _name = 'my.ai.base'
    _description = 'MyAI Base Model'
    _rec_name = 'name'

    name = fields.Char(string='Name', required=True)
    description = fields.Text(string='Description')
    active = fields.Boolean(string='Active', default=True)
    create_date = fields.Datetime(string='Created On', readonly=True)
    write_date = fields.Datetime(string='Last Updated', readonly=True)

