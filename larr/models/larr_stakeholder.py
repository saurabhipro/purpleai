from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


class LARRStakeholder(models.Model):
    _name = 'larr.stakeholder'
    _description = 'Stakeholder Management'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char('Stakeholder Name', required=True, tracking=True)
    project_id = fields.Many2one('larr.project', 'Project', required=True, tracking=True)
    partner_id = fields.Many2one('res.partner', 'Partner', tracking=True)
    
    # Stakeholder Details
    stakeholder_type = fields.Selection([
        ('land_owner', 'Land Owner'),
        ('affected_person', 'Affected Person'),
        ('government', 'Government Official'),
        ('contractor', 'Contractor'),
        ('consultant', 'Consultant'),
        ('other', 'Other')
    ], required=True, tracking=True)
    
    contact_person = fields.Char('Contact Person', tracking=True)
    phone = fields.Char('Phone', tracking=True)
    email = fields.Char('Email', tracking=True)
    address = fields.Text('Address', tracking=True)
    
    # Engagement
    engagement_level = fields.Selection([
        ('high', 'High'),
        ('medium', 'Medium'),
        ('low', 'Low')
    ], tracking=True)
    
    concerns = fields.Text('Concerns/Risks', tracking=True)
    mitigation_plan = fields.Text('Mitigation Plan', tracking=True)
    
    # Status
    state = fields.Selection([
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('resolved', 'Resolved')
    ], default='active', tracking=True)
    
    # Documents
    document_ids = fields.Many2many('ir.attachment', string='Documents') 