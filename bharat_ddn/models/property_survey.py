from odoo import models, fields, api
from odoo.exceptions import ValidationError
import boto3
import base64
from odoo.exceptions import UserError


class SurveyParameters(models.Model):
    _name = 'ddn.property.survey'
    _description = 'Survey Parameters'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'property_id'
    
    unit = fields.Char('Unit')
    property_id = fields.Many2one('ddn.property.info', 'Property ID')
    # Related fields for Dashboard/List View
    # Related fields for Dashboard/List View
    ward_id = fields.Many2one('ddn.ward', related='property_id.ward_id', string='Ward', store=True)
    colony_id = fields.Many2one('ddn.colony', related='property_id.colony_id', string='Colony', store=True)
    info_property_id = fields.Char(related='property_id.property_id', string='Property ID', store=True)

    company_id = fields.Many2one('res.company', string="Company", related='property_id.company_id', store=True, default=lambda self : self.env.company.id, readonly=True)
    address_line_1 = fields.Char('Address Line 1')
    address_line_2 = fields.Char('Address Line 2')
    total_floors = fields.Char('Total Floors')
    floor_number = fields.Char('Floor Number')
    owner_name = fields.Char('Owner Name')
    father_name = fields.Char('Father Name')
    area = fields.Float('Area (in Sq. Ft.)')
    area_code = fields.Char('Area Code')
    latitude = fields.Char('Latitude')
    longitude = fields.Char('Longitude')
    surveyer_id = fields.Many2one('res.users', string='Surveyor')
    installer_id = fields.Many2one('res.users', string='Installer')
    property_image = fields.Binary() 
    property_image1 = fields.Binary() 
    image1_s3_url = fields.Char(string="URL Image")
    image2_s3_url = fields.Char(string="Url Image2")
    mobile_no = fields.Char('Mobile No')
    survey_date = fields.Date('Survey Date', default=fields.Date.context_today)
    is_solar = fields.Boolean(string='Is Solar', default=True)
    is_rainwater_harvesting = fields.Boolean(string='Is Rain water harvesting', default=True)

    def unlink(self):
        for record in self:
            if record.property_id:
                record.property_id.property_status = 'pdf_downloaded'
                record.property_id.latitude = 0.00
                record.property_id.longitude = 0.00
                record.property_id.mobile_no = False
                record.property_id.owner_name = False
                record.property_id.property_id = False
                record.property_id.property_type = False
                record.property_id.address_line_1 = False
                record.property_id.address_line_2 = False
                record.property_id.unit_no = False
        return super(SurveyParameters, self).unlink()

    def _upload_image_field_to_s3(self, field_name, s3_filename):
        self.ensure_one()

        image_data = getattr(self, field_name, False)
        if not image_data:
            raise UserError(f"The field '{field_name}' is empty.")

        company_id = self.company_id
        AWS_ACCESS_KEY = company_id.aws_acsess_key
        AWS_SECRET_KEY = company_id.aws_secret_key
        AWS_REGION = company_id.aws_region
        S3_BUCKET_NAME = company_id.s3_bucket_name

        s3_client = boto3.client(
            's3',
            aws_access_key_id=AWS_ACCESS_KEY,
            aws_secret_access_key=AWS_SECRET_KEY,
            region_name=AWS_REGION,
            verify=False  # Disable only in development
        )

        # Decode and upload
        decoded_image = base64.b64decode(image_data)
        s3_key = f"{s3_filename}.jpg"

        s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=s3_key,
            Body=decoded_image,
            ContentType='image/jpeg'
        )

        return f"https://{S3_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{s3_key}"
    


    def action_upload_all_images(self):
        for rec in self:
            rec.image1_s3_url = rec._upload_image_field_to_s3('property_image', f"{rec.property_id.upic_no}_1")
            rec.image2_s3_url = rec._upload_image_field_to_s3('property_image1', f'{rec.property_id.upic_no}_2')
            # Clear binary fields to save DB space
            rec.property_image = False
            rec.property_image1 = False


    @api.onchange('property_id')
    def _onchange_property_id(self):
        if self.property_id:
            self.address_line_1 = self.property_id.address_line_1
            self.address_line_2 = self.property_id.address_line_2
            self.owner_name = self.property_id.owner_name
            self.mobile_no = self.property_id.mobile_no
            self.longitude = self.property_id.longitude
            self.latitude = self.property_id.latitude
            self.surveyer_id = self.property_id.surveyer_id

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            if record.property_id:
                # Update property with all relevant survey fields
                vals_to_write = {}
                if record.latitude:
                    vals_to_write['latitude'] = record.latitude
                if record.longitude:
                    vals_to_write['longitude'] = record.longitude
                if record.mobile_no:
                    vals_to_write['mobile_no'] = record.mobile_no
                if record.surveyer_id:
                    vals_to_write['surveyer_id'] = record.surveyer_id.id
                if record.address_line_1:
                    vals_to_write['address_line_1'] = record.address_line_1
                if record.address_line_2:
                    vals_to_write['address_line_2'] = record.address_line_2
            
                if record.owner_name:
                    vals_to_write['owner_name'] = record.owner_name
                if vals_to_write:
                    record.property_id.write(vals_to_write)
        return records

    def write(self, vals):
        res = super().write(vals)
        for record in self:
            if record.property_id:
                vals_to_write = {}
                # Update all relevant fields in property when changed in survey
                if 'latitude' in vals and record.latitude:
                    vals_to_write['latitude'] = record.latitude
                if 'longitude' in vals and record.longitude:
                    vals_to_write['longitude'] = record.longitude
                if 'mobile_no' in vals and record.mobile_no:
                    vals_to_write['mobile_no'] = record.mobile_no
                if 'surveyer_id' in vals and record.surveyer_id:
                    vals_to_write['surveyer_id'] = record.surveyer_id.id
                if 'address_line_1' in vals and record.address_line_1:
                    vals_to_write['address_line_1'] = record.address_line_1
                if 'address_line_2' in vals and record.address_line_2:
                    vals_to_write['address_line_2'] = record.address_line_2
                if 'owner_name' in vals and record.owner_name:
                    vals_to_write['owner_name'] = record.owner_name
                if vals_to_write:
                    record.property_id.write(vals_to_write)
        return res