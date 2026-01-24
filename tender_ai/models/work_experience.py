# -*- coding: utf-8 -*-

from odoo import models, fields, api


class WorkExperience(models.Model):
    _name = 'tende_ai.work_experience'
    _description = 'Work Experience Record'
    _order = 'date_of_start desc'

    bidder_id = fields.Many2one('tende_ai.bidder', string='Bidder', required=True, ondelete='cascade', readonly=True)
    job_id = fields.Many2one(
        'tende_ai.job',
        string='Job',
        related='bidder_id.job_id',
        readonly=True,
        store=True,
        index=True,
    )
    
    # NOTE: do not use field parameter "tracking" unless the model inherits mail.thread
    vendor_company_name = fields.Char(string='Vendor Company Name')
    name_of_work = fields.Char(string='Name of Work')
    employer = fields.Char(string='Employer')
    location = fields.Char(string='Location')
    contract_amount_inr = fields.Char(string='Contract Amount (INR)')
    date_of_start = fields.Char(string='Date of Start')
    date_of_completion = fields.Char(string='Date of Completion')
    completion_certificate = fields.Char(string='Completion Certificate')
    attachment = fields.Char(string='Attachment')

