# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class ExtractionMaster(models.Model):
    _name = 'tende_ai.extraction_master'
    _description = 'Custom Extraction Group'
    _order = 'name'

    name = fields.Char(string='Document Group Name', required=True, help="e.g. Financial Documents, Technical Bid")
    document_type = fields.Selection([
        ('tender', 'Tender Document (tender.pdf)'),
        ('bidder', 'Bidder Documents (Company folders)')
    ], string='Applies To', default='bidder', required=True)
    
    field_ids = fields.One2many('tende_ai.extraction_field', 'master_id', string='Extraction Fields')
    active = fields.Boolean(default=True)

class ExtractionField(models.Model):
    _name = 'tende_ai.extraction_field'
    _description = 'Custom Extraction Field'
    _order = 'sequence, id'

    master_id = fields.Many2one('tende_ai.extraction_master', string='Master', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    name = fields.Char(string='Field Label', required=True)
    field_key = fields.Char(string='Field Key (JSON)', required=True, help="Unique technical name for AI extraction")
    instruction = fields.Text(string='Extraction Instruction', required=True, help="AI prompt instruction on how to find this data")
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('field_key_unique', 'unique(field_key)', 'The field key must be unique!')
    ]
