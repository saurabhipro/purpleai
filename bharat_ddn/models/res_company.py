from odoo import models, fields

class ResCompany(models.Model):
    _inherit = 'res.company'

    plate_background_image = fields.Binary(string='Plate Background Image', attachment=True, help='Upload the background image for property plates.') 
    s3_bucket_name = fields.Char(string='S3 Bucket Name') 
    aws_acsess_key = fields.Char(string='AWS Access Key') 
    aws_secret_key = fields.Char(string='AWS Secret Key') 
    aws_region = fields.Char(string='AWS Region') 
    company_registry_placeholder = fields.Char()


from odoo import models, fields

class ResPartner(models.Model):
    _inherit = 'res.partner'

    partner_company_registry_placeholder = fields.Char(string="Placeholder for Company Registry")