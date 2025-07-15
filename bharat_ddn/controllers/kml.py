from odoo import http
from odoo.http import request
import re
import os
import json
from werkzeug.utils import secure_filename

class KMLController(http.Controller):
    """Controller for KML viewer functionality"""
    
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

    @http.route('/ddn/kml/get_properties', type='json', auth='public')
    def get_kml_properties(self, zone_id=None, ward_id=None, status=None):
        domain = [
            ('latitude', '!=', False),
            ('longitude', '!=', False),
            ('latitude', '!=', ''),
            ('longitude', '!=', '')
        ]
        properties = request.env['ddn.property.info'].sudo().search_read(
            domain,
            fields=['id', 'upic_no', 'owner_name', 'latitude', 'longitude']
        )
        return {
            'success': True,
            'properties': properties
        }

    @http.route('/ddn/kml/get_filters', type='json', auth='user')
    def get_kml_filters(self):
        """Get zones and wards for KML viewer filters."""
        try:
            # Get zones
            zones = request.env['ddn.zone'].sudo().search_read([], fields=['id', 'zone_name'])
            for z in zones:
                z['name'] = z.pop('zone_name')
            
            # Get wards
            wards = request.env['ddn.ward'].sudo().search_read(
                [],
                fields=['id', 'name'],
                order='name'
            )

            # Get property statuses
            statuses = [
                {'id': 'all', 'name': 'All Status'},
                {'id': 'new', 'name': 'New'},
                {'id': 'uploaded', 'name': 'Uploaded'},
                {'id': 'pdf_downloaded', 'name': 'PDF Downloaded'},
                {'id': 'surveyed', 'name': 'Surveyed'},
                {'id': 'unlocked', 'name': 'Unlocked'},
                {'id': 'discovered', 'name': 'Discovered'},
                {'id': 'visit_again', 'name': 'Visit Again'}
            ]

            return {
                'success': True,
                'zones': zones,
                'wards': wards,
                'statuses': statuses
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'zones': [],
                'wards': [],
                'statuses': []
            }

    @http.route('/ddn/kml/get_wards_by_zone', type='json', auth='user')
    def get_wards_by_zone(self, zone_id):
        """Get wards filtered by zone."""
        try:
            if not zone_id:
                return {'success': True, 'wards': []}
                
            wards = request.env['ddn.ward'].sudo().search_read(
                [('zone_id', '=', int(zone_id))],
                fields=['id', 'name'],
                order='name'
            )
            
            return {
                'success': True,
                'wards': wards
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'wards': []
            }

    @http.route('/ddn/kml/get_property_details', type='json', auth='user')
    def get_property_details(self, property_id):
        """Get detailed information for a specific property."""
        try:
            property_record = request.env['ddn.property.info'].sudo().browse(int(property_id))
            
            if not property_record.exists():
                return {
                    'success': False,
                    'error': 'Property not found'
                }

            # Get survey information
            survey_data = []
            for survey in property_record.survey_line_ids:
                survey_data.append({
                    'id': survey.id,
                    'survey_date': survey.create_date.strftime('%Y-%m-%d %H:%M:%S') if survey.create_date else '',
                    'area': survey.area,
                    'total_floors': survey.total_floors,
                    'floor_number': survey.floor_number,
                    'owner_name': survey.owner_name,
                    'father_name': survey.father_name,
                    'mobile_no': survey.mobile_no,
                    'address_line_1': survey.address_line_1,
                    'address_line_2': survey.address_line_2,
                    'image1_url': survey.image1_s3_url,
                    'image2_url': survey.image2_s3_url,
                    'is_solar': survey.is_solar,
                    'is_rainwater_harvesting': survey.is_rainwater_harvesting
                })

            return {
                'success': True,
                'property': {
                    'id': property_record.id,
                    'upic_no': property_record.upic_no,
                    'owner_name': property_record.owner_name,
                    'address_line_1': property_record.address_line_1,
                    'address_line_2': property_record.address_line_2,
                    'latitude': property_record.latitude,
                    'longitude': property_record.longitude,
                    'property_status': property_record.property_status,
                    'zone_name': property_record.zone_id.name if property_record.zone_id else '',
                    'ward_name': property_record.ward_id.name if property_record.ward_id else '',
                    'colony_name': property_record.colony_id.name if property_record.colony_id else '',
                    'property_type_name': property_record.property_type.name if property_record.property_type else '',
                    'mobile_no': property_record.mobile_no,
                    'plot_area': property_record.plot_area,
                    'road_width': property_record.road_width,
                    'no_of_trees': property_record.no_of_trees,
                    'is_solar': property_record.is_solar,
                    'is_rainwater_harvesting': property_record.is_rainwater_harvesting,
                    'surveys': survey_data
                }
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    @http.route('/ddn/kml/get_statistics', type='json', auth='user')
    def get_kml_statistics(self, zone_id=None, ward_id=None):
        """Get statistics for the KML viewer."""
        try:
            # Build base domain
            domain = [
                ('latitude', '!=', False),
                ('longitude', '!=', False),
                ('latitude', '!=', ''),
                ('longitude', '!=', '')
            ]
            
            if zone_id:
                domain.append(('zone_id', '=', int(zone_id)))
            if ward_id:
                domain.append(('ward_id', '=', int(ward_id)))

            # Get counts for each status
            status_counts = {}
            valid_statuses = ['surveyed', 'discovered', 'visit_again', 'uploaded', 'pdf_downloaded']
            
            for status in valid_statuses:
                status_domain = domain + [('property_status', '=', status)]
                count = request.env['ddn.property.info'].sudo().search_count(status_domain)
                status_counts[status] = count
            
            # Get total count
            total_count = request.env['ddn.property.info'].sudo().search_count(domain)
            
            return {
                'success': True,
                'statistics': {
                    'total_properties': total_count,
                    'status_counts': status_counts
                }
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    @http.route('/ddn/kml/export_properties', type='http', auth='user', methods=['POST'], csrf=False)
    def export_properties(self, **kwargs):
        """Export filtered properties to KML format."""
        try:
            data = json.loads(request.httprequest.data or "{}")
            zone_id = data.get('zone_id')
            ward_id = data.get('ward_id')
            status = data.get('status', 'surveyed')

            # Build domain
            domain = [
                ('property_status', '=', status),
                ('latitude', '!=', False),
                ('longitude', '!=', False),
                ('latitude', '!=', ''),
                ('longitude', '!=', '')
            ]
            
            if zone_id:
                domain.append(('zone_id', '=', int(zone_id)))
            if ward_id:
                domain.append(('ward_id', '=', int(ward_id)))

            properties = request.env['ddn.property.info'].sudo().search_read(
                domain,
                fields=[
                    'id', 'upic_no', 'owner_name', 'address_line_1', 'address_line_2',
                    'latitude', 'longitude', 'property_status', 'zone_id', 'ward_id'
                ]
            )

            # Generate KML content
            kml_content = self.generate_kml_content(properties)
            
            # Return KML file
            headers = [
                ('Content-Type', 'application/vnd.google-earth.kml+xml'),
                ('Content-Disposition', 'attachment; filename="properties.kml"')
            ]
            
            return request.make_response(kml_content, headers=headers)

        except Exception as e:
            return request.make_response(
                json.dumps({'error': str(e)}),
                headers=[('Content-Type', 'application/json')],
                status=500
            )

    def generate_kml_content(self, properties):
        """Generate KML content from properties."""
        kml_header = '''<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
<Document>
    <name>Surveyed Properties</name>
    <description>Properties exported from DDN system</description>
'''
        
        kml_footer = '''
</Document>
</kml>'''

        placemarks = []
        for prop in properties:
            try:
                # Convert coordinates
                lat = self.dms_to_decimal(prop['latitude']) if isinstance(prop['latitude'], str) else float(prop['latitude'])
                lng = self.dms_to_decimal(prop['longitude']) if isinstance(prop['longitude'], str) else float(prop['longitude'])
                
                if lat is None or lng is None or lat == 0 or lng == 0:
                    continue

                address = f"{prop['address_line_1'] or ''} {prop['address_line_2'] or ''}".strip()
                
                placemark = f'''
    <Placemark>
        <name>{prop['upic_no'] or 'No UPIC'}</name>
        <description>
            <![CDATA[
            <h3>{prop['upic_no'] or 'No UPIC'}</h3>
            <p><strong>Owner:</strong> {prop['owner_name'] or 'N/A'}</p>
            <p><strong>Address:</strong> {address or 'N/A'}</p>
            <p><strong>Status:</strong> {prop['property_status']}</p>
            ]]>
        </description>
        <Point>
            <coordinates>{lng},{lat},0</coordinates>
        </Point>
    </Placemark>'''
                
                placemarks.append(placemark)
                
            except Exception:
                continue

        return kml_header + ''.join(placemarks) + kml_footer 