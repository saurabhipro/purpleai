from odoo import models, fields, api
from odoo import models, fields, api
from odoo.exceptions import ValidationError
import base64
import re
from io import BytesIO
import qrcode
import uuid
import qrcode
from io import BytesIO
import base64
from odoo.http import request
from PIL import Image
import io
import logging
from odoo.tools import config

Image.MAX_IMAGE_PIXELS = 300000000  # e.g., 300 million pixels

_logger = logging.getLogger(__name__)

class Property(models.Model):
    _name = 'ddn.property.info'
    _description = 'Property Information'
    _inherit = ['mail.thread', 'mail.activity.mixin']    
    _rec_name = "upic_no"


    # Owner Information
    company_id = fields.Many2one('res.company', string="Company", default=lambda self : self.env.company.id, readonly=True)
    property_id = fields.Char('Property Id')
    unit_no = fields.Char('Unit No.')
    uuid = fields.Char(string='UUID', readonly=True, copy=False, store=True, default=lambda self: str(uuid.uuid4()))
    zone_id = fields.Many2one('ddn.zone', string='Zone')
    ward_id = fields.Many2one('ddn.ward',string='Ward')
    colony_id = fields.Many2one('ddn.colony', string='Colony')
    upic_no = fields.Char('UPIC NO')
    qr_code = fields.Binary("QR Code", compute="_compute_qr_code", store=True)
    mobile_no = fields.Char('Mobile No')
    survey_line_ids = fields.One2many('ddn.property.survey', 'property_id', string="Survey Line", tracking=True)
    address_line_1 = fields.Char(string="Address 1")
    address_line_2 = fields.Char(string="Address 2")
    surveyer_id = fields.Many2one('res.users', string="Surveyor")
    microsite_url = fields.Char(string='Microsite URL', compute='_compute_microsite_url', store=False)
    is_solar = fields.Boolean(string='Is Solar', default=True)
    is_rainwater_harvesting = fields.Boolean(string='Is Rain water harvesting', default=True)

    latitude = fields.Char(
        string='Latitude',
        help='Latitude in decimal degrees (e.g., 16.863889)'
    )
    longitude = fields.Char(
        string='Longitude',
        help='Longitude in decimal degrees (e.g., 74.622479)'
    )
   

    # Property Infrastructure Information
    road_width = fields.Char('Road Width')
    no_of_trees = fields.Char('No Of Trees')
    
    # Solar, Bore, Water, and Rainwater Information
    no_of_solar = fields.Char('No Of Solar')
    is_bore = fields.Char('Is Boar')
    no_of_bore = fields.Char('No Of Boar')
    no_of_rain_water_harvesting = fields.Char('No Of Rain Water harvesting')
    
    # Water Connection and Hand Pump Information
    is_water_conn_status = fields.Char('Is Warter Conn Status')
    is_hand_pump = fields.Char('Is Hand Pump')
    no_of_hand_pump = fields.Char('No Of Hand Pump')
    is_well = fields.Char('Is Well')
    no_of_well = fields.Char('No Of Well')
    
    # Lift, Drain, and Building Information
    is_lift = fields.Char('Is Lift')
    no_of_lift = fields.Char('No Of Lift')
    drain = fields.Char('Drain')
    building_permissions = fields.Char('Building Permissions')
    building_advertise = fields.Char('Building Advertise')
    building_advertise_type = fields.Char('Building Advertise Type')
    
    # Garbage Information
    garbage_segrigation = fields.Char('Garbage Segrigation')
    garbage_disposal = fields.Char('Garbage Disposal')
    septic_tank_yes_no = fields.Char('Septic Tank Yes/No')
    
    # Water Meter Information
    water_meter_yes_no = fields.Char('Water Meter Yes/No')
    water_connection_year = fields.Char('Water Connection Year')
    
    # License Information
    licence_no = fields.Char('Licence No')
    licence_date = fields.Date('Licence Date')
    
    # Property Construction Information
    year_of_permission = fields.Char('Year Of Permission')
    year_of_construction = fields.Char('Year Of Construction')
    building_age = fields.Char('Building Age')
    building_year = fields.Char('Building Year')
    build_completion_date = fields.Date('Build Completion Date')

    # oid = fields.Date('Oid')
    
    # Fire, Water Meter, ETP, and Waste Information
    is_fire = fields.Char('Is Fire')
    no_of_fire = fields.Char('No Of Fire')
    water_meter_condition = fields.Char('Water Meter Condition')
    is_water_motar = fields.Char('Is Water Motar')
    water_connection_no = fields.Char('Water Connection No')
    water_consumer_no = fields.Char('Water Consumer No')
    is_etp = fields.Char('Is ETP')
    
    # Composting and Sewage Information
    is_home_composting = fields.Char('Is Home Composting')
    is_vermicompost = fields.Char('Is Vermi compost')
    is_echarging = fields.Char('Is ECharging')
    is_sewage_water = fields.Char('Is Sewage Water')
    
    # Permission and Certificate Information
    is_const_permission = fields.Char('Is Const Permission')
    const_completion_oc = fields.Char('Const Completion OC')
    gunthewari_certificate = fields.Char('Gunthewari Certificate')
    
    # Bukhand, Construction, and Animal Information
    is_bukhand = fields.Char('Is Bukhand')
    is_construction = fields.Char('Is Construction')
    total_no_of_people = fields.Char('Total No Of People')
    
    # Animal Information
    is_animals = fields.Char('Is Animals')
    dog = fields.Char('Dog')
    cat = fields.Char('Cat')
    cow = fields.Char('Cow')
    buffalo = fields.Char('Buffalo')
    horse = fields.Char('Horse')
    oax = fields.Char('Oax')
    pig = fields.Char('Pig')
    donkey = fields.Char('Donkey')
    other = fields.Char('Other')
    
    # Additional Information
    is_gotha = fields.Char('Is Gotha')
    oc_number = fields.Char('OC Number')

    currnet_tax = fields.Float('Current Tax')
    total_amount = fields.Float('Total Amount')
  
    partition_no = fields.Char('Partition No')
    city_survey_no = fields.Char('CityServey No')
    plot_no = fields.Char('Plot No')
    
    
    # Billing Information
    bill_no = fields.Char('Bill No')
    
    # Plot Information
    plot_area = fields.Float('Plot Area')  # In Sq. Ft. or desired unit
    
    # Old Rent Information
    
    # New Property Information
    toilet_no = fields.Char('New Toilet No')
    plot_taxable_area_sqft = fields.Char('Plot Taxable Area SqFt')
    
    owner_name = fields.Char('Owner Name')
    renter_name = fields.Char('Renter Name')
    occupier_name = fields.Char('Occupier Name')
    owner_patta = fields.Char('Owner Patta')
    # Remarks
    comb_prop_remark = fields.Text('Comb Prop Remark')
    
    # Location Information


    property_status = fields.Selection([
        ('new', 'New'),
        ('uploaded', 'Uploaded'),
        ('pdf_downloaded', 'PDF Downloaded'),
        ('surveyed', 'Surveyed'),
        ('unlocked', 'Unlocked'),
        ('discovered', 'Discovered'),
        ('visit_again', 'Visit Again'),
    ], string="Property Status", default="new")
    
    property_type = fields.Many2one('ddn.property.type', string='Property Type', tracking=True)
    
    _sql_constraints = [
        ('unique_upic_no', 'UNIQUE(upic_no)', 'The UPICNO must be unique.')
    ]

    digipin = fields.Char('Digi Pin', compute='_compute_digipin', store=True)

    DIGIPIN_GRID = [
        ['F', 'C', '9', '8'],
        ['J', '3', '2', '7'],
        ['K', '4', '5', '6'],
        ['L', 'M', 'P', 'T']
    ]

    BOUNDS = {
        'minLat': 2.5,
        'maxLat': 38.5,
        'minLon': 63.5,
        'maxLon': 99.5
    }

    @api.depends('latitude', 'longitude')
    def _compute_digipin(self):
        for rec in self:
            try:
                lat = float(rec.latitude) if rec.latitude else None
                lon = float(rec.longitude) if rec.longitude else None
                if lat is not None and lon is not None:
                    rec.digipin = rec._get_digi_pin(lat, lon)
                else:
                    rec.digipin = ''
            except Exception:
                rec.digipin = ''

    def _get_digi_pin(self, lat, lon):
        if not (self.BOUNDS['minLat'] <= lat <= self.BOUNDS['maxLat']):
            return ''
        if not (self.BOUNDS['minLon'] <= lon <= self.BOUNDS['maxLon']):
            return ''

        min_lat = self.BOUNDS['minLat']
        max_lat = self.BOUNDS['maxLat']
        min_lon = self.BOUNDS['minLon']
        max_lon = self.BOUNDS['maxLon']

        digi_pin = ''

        for level in range(1, 11):
            lat_div = (max_lat - min_lat) / 4.0
            lon_div = (max_lon - min_lon) / 4.0

            row = 3 - int((lat - min_lat) / lat_div)
            col = int((lon - min_lon) / lon_div)

            row = max(0, min(row, 3))
            col = max(0, min(col, 3))

            digi_pin += self.DIGIPIN_GRID[row][col]

            if level == 3 or level == 6:
                digi_pin += '-'

            max_lat = min_lat + lat_div * (4 - row)
            min_lat = min_lat + lat_div * (3 - row)
            min_lon = min_lon + lon_div * col
            max_lon = min_lon + lon_div

        return digi_pin
   
    @api.depends('uuid')
    def _compute_qr_code(self):
        for record in self:
            try:
                # Get base URL from company website
                base_url = request.httprequest.host_url
                if record.company_id and record.company_id.website:
                    base_url = record.company_id.website
                
                # Create property URL with UUID
                property_url = f"{base_url}/get/{record.uuid}"
                
                # Create QR code instance
                qr = qrcode.QRCode(
                    version=1,
                    error_correction=qrcode.constants.ERROR_CORRECT_L,
                    box_size=20,
                    border=4,
                )
                
                # Add URL to QR code
                qr.add_data(property_url)
                qr.make(fit=True)
                
                # Create image
                img = qr.make_image(fill_color="black", back_color="white")
                
                # Convert to base64
                buffer = BytesIO()
                img.save(buffer, format='PNG')
                qr_image = base64.b64encode(buffer.getvalue())
                
                record.qr_code = qr_image
            except Exception as e:
                _logger.error(f"Error generating QR code for property {record.id}: {str(e)}")
                record.qr_code = False

    
    @api.model_create_multi
    def create(self, vals_list):
        """Override create to validate coordinates before saving."""
        for vals in vals_list:
            try:
                if vals.get('latitude'):
                    lat = vals['latitude']
                    if not re.match(r'^\d{1,2}°\s*\d{1,2}\'\s*\d{1,2}(\.\d+)?"\s*[NS]$', lat):
                        vals['latitude'] = None
                if vals.get('longitude'):
                    lng = vals['longitude']
                    if not re.match(r'^\d{1,3}°\s*\d{1,2}\'\s*\d{1,2}(\.\d+)?"\s*[EW]$', lng):
                        vals['longitude'] = None
            except (ValueError, TypeError):
                vals['latitude'] = None
                vals['longitude'] = None
        return super().create(vals_list)
    
    
    
    
  
    @api.depends('uuid')
    def _compute_microsite_url(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        base_url = request.httprequest.host_url
        for rec in self:
            if rec.company_id and rec.company_id.website:
                base_url = self.company_id.website
                if rec.uuid:
                    rec.microsite_url = f"{base_url}/get/{rec.uuid}"
                else:
                    rec.microsite_url = ''

    @api.model
    def search_read(self, domain=None, fields=None, offset=0, limit=None, order=None):
        """Override search_read to return decimal coordinates."""
        res = super().search_read(domain=domain, fields=fields, offset=offset, limit=limit, order=order)
        
        if res and ('latitude' in (fields or []) or 'longitude' in (fields or [])):
            for record in res:
                if 'latitude' in record:
                    record['latitude'] = str(record.get('latitude', ''))
                if 'longitude' in record:
                    record['longitude'] = str(record.get('longitude', ''))
                    
        return res

    def safe_open_image(self, source):
        img = Image.open(io.BytesIO(source))
        max_size = (4096, 4096)  # set your max width/height
        img.thumbnail(max_size, Image.ANTIALIAS)
        return img
    
    def action_generate_pdf_plate(self):
        self.ensure_one()
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        url = f"{base_url}/download/ward_properties_pdf/erp?property_id={self.id}"
        return {
            'type': 'ir.actions.act_url',
            'url': url,
            'target': 'new',
        }
    
    def _prepare_property_vals(self, data):
        """Prepare property values from data."""
        # Get zone and ward IDs from names if provided
        zone_id = False
        ward_id = False
        
        if data.get('zone_name'):
            zone = request.env['ddn.zone'].sudo().search([('name', '=', data['zone_name'])], limit=1)
            zone_id = zone.id if zone else False
            
        if data.get('ward_name'):
            ward = request.env['ddn.ward'].sudo().search([('name', '=', data['ward_name'])], limit=1)
            ward_id = ward.id if ward else False

        # Get colony ID if colony_name is provided
        colony_id = False
        if data.get('colony_name'):
            colony = request.env['ddn.colony'].sudo().search([('name', '=', data['colony_name'])], limit=1)
            colony_id = colony.id if colony else False

        # Map property_type_id to property_type
        property_type = data.get('property_type_id')

        # Get property_status with default value
        property_status = data.get('property_status', 'discovered')
        # Validate property_status
        valid_statuses = ['uploaded', 'pdf_downloaded', 'surveyed', 'discovered']
        if property_status not in valid_statuses:
            property_status = 'discovered'  # Default to discovered if invalid status

        return {
            'company_id': data.get('company_id'),
            'address_line_1': data.get('address_line_1'),
            'address_line_2': data.get('address_line_2'),
            'mobile_no': data.get('mobile'),
            'owner_name': data.get('owner_name'),
            'longitude': data.get('longitude'),
            'latitude': data.get('latitude'),
            'surveyer_id': data.get('surveyer_id'),
            'zone_id': zone_id or data.get('zone_id'),
            'ward_id': ward_id or data.get('ward_id'),
            'colony_id': colony_id,
            'property_status': property_status,  # Now accepts custom status
            'property_type': property_type
        }
    