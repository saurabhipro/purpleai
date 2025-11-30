from odoo import models, fields, api, _
from odoo.exceptions import UserError

class Colony(models.Model):
    _name = 'ddn.colony'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Colony'

    name = fields.Char(string='Name')
    ward_id = fields.Many2one('ddn.ward', string='Ward')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self : self.env.company.id, readonly=True)
    active = fields.Boolean(string='Active', default=True)
    code = fields.Char(string='Code')
    pdf_url = fields.Char(string='PDF URL', tracking=True)
    property_count = fields.Integer(string="Property Count", compute="_action_property_count")
    pdf_status = fields.Selection([
        ('uploaded', '✓ Uploaded'),
        ('not_uploaded', '✗ Not Uploaded')
    ], string='PDF Status', compute='_compute_pdf_status', store=False)

    def action_open_property(self):
        """Smart button action to open related colony"""
        self.ensure_one()
        return {
            'name': 'Property Records',
            'type': 'ir.actions.act_window',
            'res_model': 'ddn.property.info',
            'view_mode': 'list,form',
            'domain': [('company_id','=',self.company_id.id),('colony_id', '=', self.id)],
            'context': {'default_colony_id': self.id},
        }


    def _action_property_count(self):
        for rec in self:
            property_count = self.env['ddn.property.info'].search_count([('company_id','=',rec.company_id.id),('colony_id','=',rec.id)])
            rec.property_count = property_count

    @api.depends('pdf_url')
    def _compute_pdf_status(self):
        """Compute PDF status based on whether pdf_url exists"""
        for rec in self:
            if rec.pdf_url and rec.pdf_url.strip():
                rec.pdf_status = 'uploaded'
            else:
                rec.pdf_status = 'not_uploaded'
             
    def update_ward(self):
        """Update the pdf_url field and return a dynamic URL using colony_id."""

        config_parameter = self.env['ir.config_parameter'].sudo()
        base_url = config_parameter.get_param('web.base.url', default=False)

        if not base_url:
            raise UserError("Base URL not configured in system parameters.")

        for record in self:
            new_pdf_url = f"{base_url}/download/ward_properties_pdf?colony_id={record.id}"
            record.write({'pdf_url': new_pdf_url})

            properties = self.env['ddn.property.info'].search([
                ('colony_id', '=', record.id),
                ('property_status', '=', 'uploaded')
            ])
            if properties:
                properties.write({'property_status': 'pdf_downloaded'})

            return {
                'type': 'ir.actions.act_url',
                'url': f'/download/ward_properties_pdf?colony_id={record.id}',
                'target': 'new',
            }
