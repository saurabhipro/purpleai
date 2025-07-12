from odoo import http
from odoo.http import request
import re
import os
from werkzeug.utils import secure_filename

KML_FOLDER = 'custom_addons/ddn/static/kml/'

class PropertyMapController(http.Controller):
    def dms_to_decimal(self, dms_str):
        """Convert DMS (Degrees, Minutes, Seconds) string to decimal degrees."""
        if not dms_str:
            return None
        match = re.match(r"(\d+)°\s*(\d+)'[\s]*(\d+(?:\.\d+)?)\"\s*([NSEW])", dms_str)
        if not match:
            return None
        degrees, minutes, seconds, direction = match.groups()
        decimal = float(degrees) + float(minutes)/60 + float(seconds)/3600
        if direction in ['S', 'W']:
            decimal = -decimal
        return decimal

    @http.route('/ddn/property/map_data', type='json', auth='user')
    def property_map_data(self, zone=None, ward=None, status=None):
        domain = []
        if zone:
            domain.append(('zone', '=', zone))
        if ward:
            domain.append(('ward_id', '=', ward))
        if status:
            domain.append(('property_status', '=', status))
        domain.append(('latitude', '!=', False))
        domain.append(('longitude', '!=', False))
        properties = request.env['ddn.property.info'].sudo().search(domain)
        result = []
        for prop in properties:
            lat_decimal = self.dms_to_decimal(prop.latitude) if prop.latitude else None
            lng_decimal = self.dms_to_decimal(prop.longitude) if prop.longitude else None
            result.append({
                'id': prop.id,
                'upic_no': prop.upic_no,
                'address': f"{prop.address_line_1 or ''} {prop.address_line_2 or ''}",
                'zone': prop.zone,
                'ward': prop.ward_id.name if prop.ward_id else '',
                'status': prop.property_status,
                'latitude': lat_decimal,
                'longitude': lng_decimal,
            })
        return result 

    @http.route('/ddn/property/get_filters', type='json', auth='user')
    def get_property_filters(self):
        try:
            # Fetch unique zones
            PropertyInfo = request.env['ddn.property.info'].sudo()
            
            # First, let's check if we have any properties
            all_properties = PropertyInfo.search([])
            
            # Get all zones (including False/None values to debug)
            all_zones = all_properties.mapped('zone')
            
            # Filter out False/None values
            valid_zones = [z for z in all_zones if z]
            unique_zones = list(set(valid_zones))
            
            # Fetch wards
            WardInfo = request.env['ward.info'].sudo()
            ward_records = WardInfo.search([])
            
            wards = [{'id': ward.id, 'name': ward.name} for ward in ward_records]
            
            response = {
                'zones': sorted(unique_zones) if unique_zones else [],
                'wards': wards
            }
            return response
            
        except Exception as e:
            return {'zones': [], 'wards': [], 'error': str(e)}

    @http.route('/ddn/kml/upload', type='http', auth='user', methods=['POST'], csrf=False)
    def upload_kml(self, **kwargs):
        kml_file = kwargs.get('kml_file')
        if not kml_file:
            return request.make_response('No file uploaded', headers=[('Content-Type', 'text/plain')], status=400)
        filename = secure_filename(kml_file.filename)
        save_path = os.path.join(KML_FOLDER, filename)
        os.makedirs(KML_FOLDER, exist_ok=True)
        with open(save_path, 'wb') as f:
            f.write(kml_file.read())
        return request.make_response('KML uploaded', headers=[('Content-Type', 'text/plain')], status=200)

    @http.route('/ddn/kml/list', type='json', auth='user')
    def list_kml(self):
        try:
            files = [f for f in os.listdir(KML_FOLDER) if f.lower().endswith('.kml')]
            urls = [f'/ddn/static/kml/{f}' for f in files]
            return {'files': files, 'urls': urls}
        except Exception as e:
            return {'files': [], 'urls': [], 'error': str(e)}