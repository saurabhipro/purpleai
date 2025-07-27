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
    def get_kml_properties(self, zone_ids=None, ward_ids=None, status_ids=None, property_type_ids=None, 
                       bounds=None, zoom_level=None, limit=1000):
        print("get_kml_properties called with:", {
            'zone_ids': zone_ids,
            'ward_ids': ward_ids, 
            'status_ids': status_ids,
            'property_type_ids': property_type_ids,
            'bounds': bounds,
            'zoom_level': zoom_level,
            'limit': limit
        })
        
        # Get current company
        current_company = request.env.company
        
        # Build domain with company filter and proper handling of None/empty values
        domain = [
            ('company_id', '=', current_company.id),
            ('latitude', '!=', False),
            ('longitude', '!=', False),
            ('latitude', '!=', ''),
            ('longitude', '!=', '')
        ]
        
        # Add viewport bounds filter if provided
        if bounds and len(bounds) == 4:
            sw_lat, sw_lng, ne_lat, ne_lng = bounds
            domain.extend([
                ('latitude', '>=', str(sw_lat)),
                ('latitude', '<=', str(ne_lat)),
                ('longitude', '>=', str(sw_lng)),
                ('longitude', '<=', str(ne_lng))
            ])
        
        # Handle multiple zone selections
        if zone_ids and zone_ids != [] and zone_ids != ['']:
            if isinstance(zone_ids, str):
                zone_ids = [zone_ids]
            domain.append(('zone_id', 'in', [int(zid) for zid in zone_ids if zid and zid != '']))
        
        # Handle multiple ward selections
        if ward_ids and ward_ids != [] and ward_ids != ['']:
            if isinstance(ward_ids, str):
                ward_ids = [ward_ids]
            domain.append(('ward_id', 'in', [int(wid) for wid in ward_ids if wid and wid != '']))
        
        # Handle multiple status selections
        if status_ids and status_ids != [] and status_ids != ['']:
            if isinstance(status_ids, str):
                status_ids = [status_ids]
            domain.append(('property_status', 'in', status_ids))
        
        # Handle multiple property type selections
        if property_type_ids and property_type_ids != [] and property_type_ids != ['']:
            if isinstance(property_type_ids, str):
                property_type_ids = [property_type_ids]
            domain.append(('property_type', 'in', [int(ptid) for ptid in property_type_ids if ptid and ptid != '']))
        
        print("Final domain:", domain)
        
        # Get total count first
        total_count = request.env['ddn.property.info'].sudo().search_count(domain)
        print(f"Properties found in viewport: {total_count}")
        
        # Adjust limit based on zoom level
        if zoom_level:
            zoom_level = int(zoom_level)
            if zoom_level <= 10:  # Very zoomed out
                limit = min(limit, 500)  # Show fewer points
            elif zoom_level <= 12:  # Medium zoom
                limit = min(limit, 1000)
            elif zoom_level <= 14:  # Closer zoom
                limit = min(limit, 2000)
            else:  # Very close zoom
                limit = min(limit, 5000)  # Show more points
        
        # Get properties with additional fields
        properties = request.env['ddn.property.info'].sudo().search_read(
            domain,
            fields=[
                'id', 'upic_no', 'owner_name', 'latitude', 'longitude', 
                'property_status', 'zone_id', 'ward_id', 'property_type',
                'address_line_1', 'address_line_2', 'mobile_no', 'property_id'
            ],
            limit=limit,
            order='id'
        )

        # Get related data efficiently using a single query
        zone_ids = list(set([p['zone_id'][0] for p in properties if p.get('zone_id')]))
        ward_ids = list(set([p['ward_id'][0] for p in properties if p.get('ward_id')]))
        property_type_ids = list(set([p['property_type'][0] for p in properties if p.get('property_type')]))
        
        # Batch fetch related data
        zones = {z.id: z.name for z in request.env['ddn.zone'].sudo().browse(zone_ids)} if zone_ids else {}
        wards = {w.id: w.name for w in request.env['ddn.ward'].sudo().browse(ward_ids)} if ward_ids else {}
        property_types = {pt.id: pt.name for pt in request.env['ddn.property.type'].sudo().browse(property_type_ids)} if property_type_ids else {}

        # Get survey images for properties
        property_ids = [p['id'] for p in properties]
        surveys = request.env['ddn.property.survey'].sudo().search_read(
            [('property_id', 'in', property_ids)],
            fields=['property_id', 'image1_s3_url', 'image2_s3_url', 'property_image', 'property_image1']
        )
        
        # Create survey lookup
        survey_lookup = {}
        for survey in surveys:
            prop_id = survey['property_id'][0]
            survey_lookup[prop_id] = {
                'image1': survey.get('image1_s3_url') or survey.get('property_image'),
                'image2': survey.get('image2_s3_url') or survey.get('property_image1')
            }

        # Add related data to properties
        for prop in properties:
            if prop.get('zone_id'):
                prop['zone_name'] = zones.get(prop['zone_id'][0], 'N/A')
            if prop.get('ward_id'):
                prop['ward_name'] = wards.get(prop['ward_id'][0], 'N/A')
            if prop.get('property_type'):
                prop['property_type_name'] = property_types.get(prop['property_type'][0], 'N/A')
            
            # Add survey images
            survey_data = survey_lookup.get(prop['id'], {})
            prop['survey_image1'] = survey_data.get('image1')
            prop['survey_image2'] = survey_data.get('image2')

        print(f"Returning {len(properties)} properties (zoom: {zoom_level}, limit: {limit})")
        return {
            'success': True,
            'properties': properties,
            'total_count': total_count,
            'returned_count': len(properties),
            'viewport_bounds': bounds,
            'zoom_level': zoom_level,
            'has_more': len(properties) < total_count
        }

    @http.route('/ddn/kml/get_filters', type='json', auth='user')
    def get_kml_filters(self):
        print("get_kml_filters called")
        """Get zones, wards, statuses, and property types for KML viewer filters."""
        try:
            # Get current company
            current_company = request.env.company
            print("Current company:", current_company.name, current_company.id)
            
            # Get zones for current company only
            zones = request.env['ddn.zone'].sudo().search_read(
                [('company_id', '=', current_company.id)], 
                fields=['id', 'name']
            )
            print("Zones found:", len(zones))
            
            # Get wards for current company only
            wards = request.env['ddn.ward'].sudo().search_read(
                [('company_id', '=', current_company.id)],
                fields=['id', 'name'],
                order='name'
            )
            print("Wards found:", len(wards))

            # Get property types for current company only
            property_types = request.env['ddn.property.type'].sudo().search_read(
                [('company_id', '=', current_company.id)],
                fields=['id', 'name'],
                order='name'
            )
            print("Property types found:", len(property_types), property_types)

            # Get property statuses
            statuses = [
                {'id': 'new', 'name': 'New'},
                {'id': 'uploaded', 'name': 'Uploaded'},
                {'id': 'pdf_downloaded', 'name': 'PDF Downloaded'},
                {'id': 'surveyed', 'name': 'Surveyed'},
                {'id': 'unlocked', 'name': 'Unlocked'},
                {'id': 'discovered', 'name': 'Discovered'},
                {'id': 'visit_again', 'name': 'Visit Again'}
            ]
            
            print("Returning filters:", {
                'zones': zones,
                'wards': wards,
                'statuses': statuses,
                'property_types': property_types
            })
            
            return {
                'success': True,
                'zones': zones,
                'wards': wards,
                'statuses': statuses,
                'property_types': property_types
            }

        except Exception as e:
            print("Exception in get_kml_filters:", e)
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'error': str(e),
                'zones': [],
                'wards': [],
                'statuses': [],
                'property_types': []
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

    @http.route('/bharat_ddn/static/kml/<path:filename>', type='http', auth='public')
    def serve_kml_file(self, filename, **kwargs):
        """Serve KML/KMZ files from the static/kml directory."""
        try:
            # Get the file path
            file_path = os.path.join(os.path.dirname(__file__), '..', 'static', 'kml', filename)
            
            if os.path.exists(file_path):
                # Determine content type based on file extension
                if filename.lower().endswith('.kmz'):
                    content_type = 'application/vnd.google-earth.kmz'
                elif filename.lower().endswith('.kml'):
                    content_type = 'application/vnd.google-earth.kml+xml'
                else:
                    content_type = 'application/octet-stream'
                
                # Read and return the file
                with open(file_path, 'rb') as f:
                    content = f.read()
                
                return http.Response(
                    content,
                    content_type=content_type,
                    headers=[
                        ('Access-Control-Allow-Origin', '*'),
                        ('Access-Control-Allow-Methods', 'GET, OPTIONS'),
                        ('Access-Control-Allow-Headers', 'Content-Type')
                    ]
                )
            else:
                return http.Response("File not found", status=404)
                
        except Exception as e:
            print(f"Error serving KML file {filename}: {e}")
            return http.Response("Error serving file", status=500)

    @http.route('/ddn/kml/serve_imc', type='http', auth='public')
    def serve_imc_kml(self, **kwargs):
        """Serve IMC KML file with proper headers for Google Maps."""
        try:
            file_path = os.path.join(os.path.dirname(__file__), '..', 'static', 'kml', 'imc.kml')
            
            if os.path.exists(file_path):
                with open(file_path, 'rb') as f:
                    content = f.read()
                
                return http.Response(
                    content,
                    content_type='application/vnd.google-earth.kml+xml',
                    headers=[
                        ('Access-Control-Allow-Origin', '*'),
                        ('Access-Control-Allow-Methods', 'GET, OPTIONS'),
                        ('Access-Control-Allow-Headers', 'Content-Type'),
                        ('Cache-Control', 'no-cache')
                    ]
                )
            else:
                return http.Response("IMC KML file not found", status=404)
                
        except Exception as e:
            print(f"Error serving IMC KML file: {e}")
            return http.Response("Error serving IMC KML file", status=500) 