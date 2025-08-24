from odoo import models, fields

class TenantAttachment(models.Model):
    _name = 'tenant.attachment'
    _description = 'Tenant Attachments'

    name = fields.Char(string="File Name", required=True)
    datas = fields.Binary(string="File", required=True)
    mimetype = fields.Char(string="Mime Type")  # <- Needed for many2many_binary
