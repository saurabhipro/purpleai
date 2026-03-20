# -*- coding: utf-8 -*-
from odoo import models, fields

class DocDocument(models.Model):
    _name = 'doc.document'
    _description = 'Word Document'

    name = fields.Char(string='Document Name', required=True)
    content = fields.Binary(string='Document Binary Content')
    html_snapshot = fields.Html(string='HTML Snapshot for Editor')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('archived', 'Archived'),
    ], default='draft', string='Status')
