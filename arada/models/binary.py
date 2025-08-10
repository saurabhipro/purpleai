from odoo import models, fields

class TenantAttachment(models.Model):
    _name = 'tenant.attachment'
    _description = 'Tenant Attachments'

    name = fields.Char(string="File Name", required=True)
    file = fields.Binary(string="File", required=True)
    tenant_ids = fields.Many2many('tenant.details', string="Tenants")