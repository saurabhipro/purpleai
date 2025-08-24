from odoo import models, fields

class AradaWorkflow(models.Model):
    _name = 'arada.workflow'
    _description = 'Arada Workflow'

    name = fields.Char(string='Name', required=True)
    
    user_id = fields.Many2one(
        comodel_name='res.users',
        string='Assigned User',
        required=True
    )

    global_status = fields.Selection([
        ('ptl', 'PTL'),
        ('form_verification', 'Form Verification'),
        ('kick_off_meeting', 'Kick Off Meeting'),
        ('pending_with_rdd', 'Pending With RDD'),
        ('pending_with_tenant', 'Pending With Tenant'),
        ('rdd_review', 'RDD Review'),
        ('noc', 'NOC'),
        ('site_inspection_submission', 'Site Inspection Submission'),
        ('handover', 'Handover')
    ], string='Global Status', default='ptl', tracking=True)