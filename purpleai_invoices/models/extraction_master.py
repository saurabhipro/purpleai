# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class ExtractionMaster(models.Model):
    _name = 'purple_ai.extraction_master'
    _description = 'Extraction Template'
    _order = 'name'

    name = fields.Char(string='Template Name', required=True, help="e.g. Invoice Template, Resume Template")
    active = fields.Boolean(default=True)
    
    field_ids = fields.One2many('purple_ai.extraction_field', 'master_id', string='Fields to Extract')
    rule_ids = fields.One2many('purple_ai.validation_rule', 'master_id', string='Validation Rules')

class ExtractionField(models.Model):
    _name = 'purple_ai.extraction_field'
    _description = 'Extraction Field'
    _order = 'sequence, id'

    master_id = fields.Many2one('purple_ai.extraction_master', string='Template', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    name = fields.Char(string='Field Label', required=True, help="e.g. Invoice Number")
    field_key = fields.Char(string='JSON Key', required=True, help="Technical name for AI (no spaces)")
    instruction = fields.Text(string='AI Instruction', required=True, help="Prompt for AI on how to find this data")
    active = fields.Boolean(default=True)
    use_zoom = fields.Boolean(string='Use Zoom-In', default=False, help="If checked, the AI will also receive a zoomed-in crop of the document margin for better extraction.")

    _sql_constraints = [
        ('field_key_unique', 'unique(master_id, field_key)', 'The JSON key must be unique per template!')
    ]

class ValidationRule(models.Model):
    _name = 'purple_ai.validation_rule'
    _description = 'Validation Rule'
    _order = 'sequence, id'

    master_id = fields.Many2one('purple_ai.extraction_master', string='Template', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    name = fields.Char(string='Rule Name', required=True)
    rule_code = fields.Char(string='Rule ID', required=True, help="e.g. RULE_1")
    description = fields.Text(string='Description / AI Logic')
    eval_type = fields.Selection([
        ('python', 'Python Logic (Odoo Database Check)'),
        ('ai', 'AI Logic (Reasoning on Document)')
    ], string='Evaluation Type', default='python', required=True)
    active = fields.Boolean(default=True)
