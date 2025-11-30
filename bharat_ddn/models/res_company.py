from odoo import models, fields

class ResCompany(models.Model):
    _inherit = 'res.company'

    plate_background_image = fields.Binary(string='Plate Background Image', attachment=True, help='Upload the background image for property plates.') 
    s3_bucket_name = fields.Char(string='S3 Bucket Name') 
    aws_acsess_key = fields.Char(string='AWS Access Key') 
    aws_secret_key = fields.Char(string='AWS Secret Key') 
    aws_region = fields.Char(string='AWS Region') 
    s3_pdf_path_prefix = fields.Char(string='S3 PDF Path Prefix', default='pdf/', help='S3 path prefix for PDF files (e.g., pdf/ or ddnindore/pdf/). PDFs will be organized colony-wise under this path.')
    company_registry_placeholder = fields.Char()


from odoo import models, fields

class ResPartner(models.Model):
    _inherit = 'res.partner'

    partner_company_registry_placeholder = fields.Char(string="Placeholder for Company Registry")