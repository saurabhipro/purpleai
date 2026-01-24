from odoo import models, fields, api


class EligibilityCriteria(models.Model):
    _name = 'tende_ai.eligibility_criteria'
    _description = 'Eligibility Criteria'
    _rec_name = 'sl_no'
    _order = 'sl_no'

    job_id = fields.Many2one('tende_ai.job', string='Job', required=True, ondelete='cascade', readonly=True)
    tender_id = fields.Many2one('tende_ai.tender', string='Tender', required=True, ondelete='cascade', readonly=True)
    
    sl_no = fields.Char(string='Sl. No.')
    criteria = fields.Text(string='Criteria')
    supporting_document = fields.Text(string='Supporting Document')