from odoo import models, fields, api, _

class AuditDocument(models.Model):
    _name = 'audit.document'
    _description = 'Audit Document'

    memo_id = fields.Many2one('audit.memo', string='Audit Memo', ondelete='cascade')
    name = fields.Char(string='Description', required=True)
    file = fields.Binary(string='File', required=True, attachment=True)
    file_name = fields.Char(string='File Name')
    uploaded_by = fields.Many2one('res.users', string='Uploaded By', default=lambda self: self.env.user, readonly=True)
    upload_date = fields.Datetime(string='Upload Date', default=fields.Datetime.now, readonly=True)
