# -*- coding: utf-8 -*-

from odoo import models, fields, api

class CustomExtraction(models.Model):
    _name = 'tende_ai.custom_extraction'
    _description = 'Custom Extraction Result'
    _order = 'id'

    bidder_id = fields.Many2one('tende_ai.bidder', string='Bidder', ondelete='cascade', index=True)
    tender_id = fields.Many2one('tende_ai.tender', string='Tender', ondelete='cascade', index=True)
    job_id = fields.Many2one('tende_ai.job', related='bidder_id.job_id', string='Job', store=True, index=True)
    
    field_id = fields.Many2one('tende_ai.extraction_field', string='Field', required=True, ondelete='restrict')
    field_name = fields.Char(related='field_id.name', string='Field Name', readonly=True)
    
    value = fields.Text(string='Extracted Value')
    source_file = fields.Char(string='Source File')
    source_page = fields.Char(string='Page No.')
    source_para = fields.Text(string='Source Paragraph/Context')
    
    job_id = fields.Many2one('tende_ai.job', compute='_compute_job_id', string='Job', store=True, index=True)

    @api.depends('bidder_id', 'tender_id')
    def _compute_job_id(self):
        for rec in self:
            if rec.bidder_id:
                rec.job_id = rec.bidder_id.job_id
            elif rec.tender_id:
                rec.job_id = rec.tender_id.job_id
            else:
                rec.job_id = False
