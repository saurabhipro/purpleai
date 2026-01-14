from odoo import http
from .main import *
from odoo import http
from odoo.http import request, Response, route, Controller
from datetime import datetime, date, timedelta
import json
import logging
import logging
import boto3
import base64


_logger = logging.getLogger(__name__)
from datetime import datetime

# Constants
DEFAULT_LIMIT = 50
DEFAULT_PAGE = 1
PROPERTY_STATUSES = ['uploaded', 'pdf_downloaded', 'surveyed', 'discovered']

class PropertyDetailsAPI(http.Controller):
    """API controller for property details."""

    """ API CRUD """
        
    @http.route('/api/get_property', type='http', auth='public', methods=['POST'], csrf=False)
    @check_permission
    def get_property_details(self, **kwargs):
        """Get property details based on a single parameter (UPIC, mobile number, or UUID)."""
        try:
            data = json.loads(request.httprequest.data or "{}")
            parameter = data.get('parameter_name', '').strip()
            page = int(data.get('page', DEFAULT_PAGE))
            limit = int(data.get('limit', DEFAULT_LIMIT))

            domain = []
            if parameter:
                if parameter.isdigit() and len(parameter) == 10:
                    domain.append(('mobile_no', '=', parameter))
                elif len(parameter) == 36:  # UUID length is 36 characters
                    domain.append(('uuid', '=', parameter))
                else:
                    domain.append(('upic_no', '=', parameter))

            _logger.info(f"Searching with domain: {domain} and parameter: {parameter}")

            if domain:
                property_details = request.env['ddn.property.info'].sudo().search(domain, limit=1)
            else:
                property_details = []  # Explicitly return empty if no valid input

            property_data = [self._format_property_data(property) for property in property_details]

            return Response(json.dumps({
                'property_details': property_data,
                'matched_count': len(property_data),
                'page': page,
                'limit': limit,
                'message': 'No property found for the given parameter.' if not property_data else 'Property found.'
            }), status=200, content_type='application/json')

        except jwt.ExpiredSignatureError:
            raise AccessError('JWT token has expired')
        except jwt.InvalidTokenError:
            raise AccessError('Invalid JWT token')

    def _format_property_data(self, property):
        """Format property data for response."""
        return {
            "property_id": property.property_id or "",
            "status": property.property_status,
            "upic_no": property.upic_no,
            "zone_id": property.zone_id.name,
            "ward_id": property.ward_id.name,
            "colony_name": property.colony_id.name if property.colony_id else '',
            "unit_no": property.unit_no if property.unit_no else '',
            "latitude": property.latitude,
            "longitude": property.longitude,
            "mobile_no": property.mobile_no,
            "owner_name": property.owner_name,
            "property_type": property.property_type.name if property.property_type else '',
            "property_type_id": property.property_type.id if property.property_type else False,
            "survey_line_ids": [self._format_survey_data(survey) for survey in property.survey_line_ids if property.survey_line_ids]
        }

    def _format_survey_data(self, survey):
        """Format survey data for response."""
        return {
            "address_line_1": survey.address_line_1,
            "address_line_2": survey.address_line_2,
            "mobile_no": survey.mobile_no,
            "unit": survey.unit,
            "total_floors": survey.total_floors,
            "floor_number": survey.floor_number,
            "owner_name": survey.owner_name,
            "father_name": survey.father_name,
            "area": survey.area,
            "area_code": survey.area_code,
            "longitude": survey.longitude,
            "latitude": survey.latitude,
            "surveyer_id": survey.surveyer_id.id,
            "installer_id": survey.installer_id.id,
            "image1_s3_url": survey.image1_s3_url or "",
            "image2_s3_url": survey.image2_s3_url or "",
            "is_solar": survey.is_solar,
            "is_rainwater_harvesting": survey.is_rainwater_harvesting,
            "created_date": survey.create_date and survey.create_date.strftime('%Y-%m-%d') or ""
        }

    @http.route('/api/property/create_survey', type='http', auth='public', methods=['POST'], csrf=False)
    @check_permission
    def create_survey(self, **kwargs):
        """Create a new survey for a property."""
        try:
            data = json.loads(request.httprequest.data or "{}")
            upic_no = data.get('upic_no', '')
            property_type_id = data.get('property_type_id')
            mobile_no = data.get('mobile_no', '')
            uuid = data.get('uuid')
            property_id_from_data = data.get("property_id")  # The property_id from the request
            
            # Accept property_status (or survey_status for backward compatibility)
            property_status = data.get('property_status') or data.get('survey_status', 'surveyed')

            # Validate property_status
            if property_status not in ['surveyed', 'visit_again']:
                return Response(
                    json.dumps({'error': 'property_status/survey_status must be either "surveyed" or "visit_again"'}),
                    status=400,
                    content_type='application/json'
                )

            # Find property record either by upic_no or uuid
            domain = []
            if upic_no:
                domain = [('upic_no', '=', upic_no)]
            elif uuid:
                domain = [('uuid', '=', uuid)]
            else:
                return Response(json.dumps({'error': 'Either upic_no or uuid is required'}), status=400, content_type='application/json')
            
            property_record = request.env['ddn.property.info'].sudo().search(domain, limit=1)

            if not property_record:
                return Response(json.dumps({'error': 'Property not found'}), status=404, content_type='application/json')

            # Check if the property_id from request is already mapped to another property
            if property_id_from_data:
                existing_property = request.env['ddn.property.info'].sudo().search([
                    ('property_id', '=', property_id_from_data),
                    ('id', '!=', property_record.id)  # Exclude current property
                ], limit=1)
                if existing_property:
                    return Response(json.dumps({'error': 'property_id is already mapped to another property.'}), status=400, content_type='application/json')

            # Use image URLs directly from payload (no S3 upload)
            property_image_url = data.get('property_image_url')
            property_image1_url = data.get('property_image1_url')
            data['image1_s3_url'] = property_image_url
            data['image2_s3_url'] = property_image1_url
            data['uuid'] = uuid
            
            # Set the property_id to the actual property record's ID from database
            data['property_id'] = property_id_from_data
                
            if mobile_no:
                data['mobile_no'] = mobile_no
            
            # Validate required fields only for 'surveyed' status
            if property_status == 'surveyed' and not property_type_id:
                return Response(json.dumps({'error': 'property_type_id is required when property_status is "surveyed"'}), status=400, content_type='application/json')
            
            # Validate owner_name is not blank for 'surveyed' status
            owner_name = data.get('owner_name', '').strip()
            if property_status == 'surveyed' and not owner_name:
                return Response(json.dumps({'error': 'owner_name is required when property_status is "surveyed"'}), status=400, content_type='application/json')
            
            # Prepare survey line values (all fields optional for visit_again)
            survey_line_vals = self._prepare_survey_line_vals(data, property_status)
            
            # Update the survey and other fields
            update_vals = {
                'survey_line_ids': [(0, 0, survey_line_vals)],
                'property_status': property_status,
                'mobile_no': mobile_no if mobile_no else property_record.mobile_no,
            }
            
            # Only update property_id if it's provided
            if property_id_from_data:
                update_vals['property_id'] = property_id_from_data
                
            if property_status == 'surveyed' and property_type_id:
                update_vals['property_type'] = property_type_id
            
            # Write the updates to the property record
            property_record.write(update_vals)

            # Always return the same message and the actual uuid from the property record
            return Response(json.dumps({
                'message': 'Survey created successfully',
                'property_status': property_status,
                'uuid': property_record.uuid
            }), status=200, content_type='application/json')

        except jwt.ExpiredSignatureError:
            _logger.error("JWT token has expired")
            raise AccessError('JWT token has expired')
        except jwt.InvalidTokenError:
            _logger.error("Invalid JWT token")
            raise AccessError('Invalid JWT token')
        except Exception as e:
            _logger.error(f"Error in create_survey: {str(e)}")
            return Response(json.dumps({'error': str(e)}), status=500, content_type='application/json')

    def _prepare_survey_line_vals(self, data, property_status):
        """Prepare survey line values from data."""
        # Get the company_id from the property record if not provided
        company_id = data.get("company_id")
        if not company_id:
            # Try to get it from the property record
            upic_no = data.get('upic_no', '')
            uuid = data.get('uuid')
            domain = []
            if upic_no:
                domain = [('upic_no', '=', upic_no)]
            elif uuid:
                domain = [('uuid', '=', uuid)]
            
            if domain:
                property_record = request.env['ddn.property.info'].sudo().search(domain, limit=1)
                if property_record:
                    company_id = property_record.company_id.id
        
        return {
            'company_id': company_id,
            'property_id': data.get("property_id", False),
            'address_line_1': data.get("address_line_1", ''),
            'address_line_2': data.get("address_line_2", ''),
            'unit': data.get("unit", ''),
            'total_floors': data.get("total_floors", ''),
            'mobile_no': data.get("mobile_no", False),
            'floor_number': data.get("floor_number", ''),
            'owner_name': data.get("owner_name", ''),
            'father_name': data.get("father_name", ''),
            'longitude': data.get("longitude", ''),
            'latitude': data.get("latitude", ''),
            'surveyer_id': data.get("surveyer_id", False),
            'image1_s3_url': data.get("image1_s3_url", False),
            'image2_s3_url': data.get("image2_s3_url", False),
            'is_solar': data.get("is_solar", True),  # Default to True if not provided
            'is_rainwater_harvesting': data.get("is_rainwater_harvesting", True),  # Default to True if not provided
        }

    @http.route('/api/create_property', type='http', auth='public', methods=['POST'], csrf=False)
    @check_permission
    def create_property_details(self, **kwargs):
        """Create a new property record."""
        try:
            data = json.loads(request.httprequest.data or "{}")
            
            # Validate required fields
            required_fields = ['company_id', 'surveyer_id', 'address_line_1', 'mobile']
            missing_fields = [field for field in required_fields if not data.get(field)]
            
            if missing_fields:
                return Response(
                    json.dumps({
                        'status': 'error',
                        'message': f'Missing required fields: {", ".join(missing_fields)}'
                    }),
                    status=400,
                    content_type='application/json'
                )

            vals = self._prepare_property_vals(data)
            property_record = request.env['ddn.property.info'].sudo().create(vals)
            
            return Response(
                json.dumps({
                    'status': 'success',
                    'message': 'Property created successfully',
                    'property_id': property_record.id
                }),
                status=200,
                content_type='application/json'
            )

        except jwt.ExpiredSignatureError:
            _logger.error("JWT token has expired")
            return Response(
                json.dumps({'status': 'error', 'message': 'JWT token has expired'}),
                status=401,
                content_type='application/json'
            )

        except jwt.InvalidTokenError:
            _logger.error("Invalid JWT token")
            return Response(
                json.dumps({'status': 'error', 'message': 'Invalid JWT token'}),
                status=401,
                content_type='application/json'
            )

        except Exception as e:
            _logger.error(f"Error occurred: {str(e)}")
            return Response(
                json.dumps({'status': 'error', 'message': 'An error occurred', 'details': str(e)}),
                status=500,
                content_type='application/json'
            )
        

    @http.route('/api/dashboard', type='http', auth='public', methods=['POST'], csrf=False)
    @check_permission
    def dashboard_summary(self, **kwargs):
        """Get dashboard summary data for today's progress and overall summary."""
        try:
            data = json.loads(request.httprequest.data or "{}")
            surveyor_id = data.get('surveyor_id')
            company_id = data.get('company_id')

            # Get surveyor's information
            surveyor = request.env['res.users'].sudo().browse(surveyor_id)
            if not surveyor:
                return Response(
                    json.dumps({'error': 'Surveyor not found'}),
                    status=404,
                    content_type='application/json'
                )
            
            ward_id = surveyor.ward_id.id if surveyor.ward_id else False
            zone_id = surveyor.zone_id.id if surveyor.zone_id else False

            if not ward_id:
                return Response(
                    json.dumps({'error': 'Surveyor does not have a ward assigned'}),
                    status=400,
                    content_type='application/json'
                )

            Property = request.env['ddn.property.info'].sudo()
            Survey = request.env['ddn.property.survey'].sudo()

            def get_counts(company_id, ward_id, surveyor_id):
                today = datetime.now().date()
                today_start = datetime.combine(today, datetime.min.time())
                today_end = datetime.combine(today, datetime.max.time())

                # Total properties in the ward
                total = Property.search_count([
                    ('company_id', '=', company_id),
                    ('ward_id', '=', ward_id)
                ])

                # My Today's Stats - surveyed by this surveyor today
                my_today_surveyed = Survey.search_count([
                    ('company_id', '=', company_id),
                    ('property_id.ward_id', '=', ward_id),
                    ('surveyer_id', '=', surveyor_id),
                    ('create_date', '>=', today_start),
                    ('create_date', '<=', today_end)
                ])

                # My Today's Stats - discovered by this surveyor today
                my_today_discovered = Property.search_count([
                    ('company_id', '=', company_id),
                    ('ward_id', '=', ward_id),
                    ('property_status', '=', 'discovered'),
                    ('surveyer_id', '=', surveyor_id),
                    ('create_date', '>=', today_start),
                    ('create_date', '<=', today_end)
                ])

                # My Today's Stats - visit_again by this surveyor today
                my_today_visit_again = Property.search_count([
                    ('company_id', '=', company_id),
                    ('ward_id', '=', ward_id),
                    ('property_status', '=', 'visit_again'),
                    ('surveyer_id', '=', surveyor_id),
                    ('create_date', '>=', today_start),
                    ('create_date', '<=', today_end)
                ])

                # My Overall Stats - total surveyed by this surveyor
                my_total_surveyed = Survey.search_count([
                    ('company_id', '=', company_id),
                    ('property_id.ward_id', '=', ward_id),
                    ('surveyer_id', '=', surveyor_id)
                ])

                # My Overall Stats - total discovered by this surveyor
                my_total_discovered = Property.search_count([
                    ('company_id', '=', company_id),
                    ('ward_id', '=', ward_id),
                    ('property_status', '=', 'discovered'),
                    ('surveyer_id', '=', surveyor_id)
                ])

                # My Overall Stats - total visit_again by this surveyor
                my_total_visit_again = Property.search_count([
                    ('company_id', '=', company_id),
                    ('ward_id', '=', ward_id),
                    ('property_status', '=', 'visit_again'),
                    ('surveyer_id', '=', surveyor_id)
                ])

                # Overall Stats - total surveyed in ward (all surveyors)
                overall_total_surveyed = Survey.search_count([
                    ('company_id', '=', company_id),
                    ('property_id.ward_id', '=', ward_id)
                ])

                # Overall Stats - total discovered in ward (all surveyors)
                overall_total_discovered = Property.search_count([
                    ('company_id', '=', company_id),
                    ('ward_id', '=', ward_id),
                    ('property_status', '=', 'discovered')
                ])

                # Overall Stats - total visit_again in ward (all surveyors)
                overall_total_visit_again = Property.search_count([
                    ('company_id', '=', company_id),
                    ('ward_id', '=', ward_id),
                    ('property_status', '=', 'visit_again')
                ])

                # Calculate pending counts
                my_today_pending = total - my_today_surveyed - my_today_discovered - my_today_visit_again
                my_total_pending = total - my_total_surveyed - my_total_discovered - my_total_visit_again
                overall_total_pending = total - overall_total_surveyed - overall_total_discovered - overall_total_visit_again

                return {
                    'total': total,
                    'my_today_surveyed': my_today_surveyed,
                    'my_today_discovered': my_today_discovered,
                    'my_today_visit_again': my_today_visit_again,
                    'my_today_pending': my_today_pending,
                    'my_total_surveyed': my_total_surveyed,
                    'my_total_discovered': my_total_discovered,
                    'my_total_visit_again': my_total_visit_again,
                    'my_total_pending': my_total_pending,
                    'overall_total_surveyed': overall_total_surveyed,
                    'overall_total_discovered': overall_total_discovered,
                    'overall_total_visit_again': overall_total_visit_again,
                    'overall_total_pending': overall_total_pending,
                }

            counts = get_counts(company_id, ward_id, surveyor_id)

            # Get surveyor name and ward/zone names
            surveyor_name = surveyor.name or "Unknown"
            ward_name = surveyor.ward_id.name if surveyor.ward_id else "Unknown"
            zone_name = surveyor.zone_id.name if surveyor.zone_id else "Unknown"

            response = {
                "status": "success",
                "message": "Dashboard data fetched successfully",
                "surveyor_info": {
                    "name": surveyor_name,
                    "zone": zone_name,
                    "ward": ward_name,
                    "selected_ward": ward_name
                },
                "total_properties": {
                    "ward_name": ward_name,
                    "total_count": counts['total']
                },
                "my_todays_stats": {
                    "surveyed_today": counts['my_today_surveyed'],
                    "discovered": counts['my_today_discovered'],
                    "visit_again": counts['my_today_visit_again'],
                    "pending": counts['my_today_pending']
                },
                "my_overall_stats": {
                    "total_surveyed": counts['my_total_surveyed'],
                    "total_discovered": counts['my_total_discovered'],
                    "total_visit_again": counts['my_total_visit_again'],
                    "pending": counts['my_total_pending']
                },
                "overall_stats": {
                    "total_surveyed": counts['overall_total_surveyed'],
                    "total_discovered": counts['overall_total_discovered'],
                    "total_visit_again": counts['overall_total_visit_again'],
                    "pending": counts['overall_total_pending']
                }
            }
            return Response(json.dumps(response), status=200, content_type='application/json')

        except Exception as e:
            return Response(
                json.dumps({'status': 'error', 'message': 'An error occurred', 'details': str(e)}),
                status=500,
                content_type='application/json'
            )

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
            'property_status': 'discovered'
        }

    @http.route('/api/recent_surveys', type='http', auth='public', methods=['POST'], csrf=False)
    @check_permission
    def get_recent_surveys(self, **kwargs):
        """Get top 5 most recent surveys based on surveyor ID and (optionally) ward ID."""
        try:
            data = json.loads(request.httprequest.data or "{}")
            surveyor_id = data.get('surveyor_id')
            ward_id = data.get('ward_id')

            if not surveyor_id:
                return Response(
                    json.dumps({'error': 'surveyor_id is required'}),
                    status=400,
                    content_type='application/json'
                )

            # Build domain
            domain = [('surveyer_id', '=', surveyor_id)]
            if ward_id:
                domain.append(('property_id.ward_id', '=', ward_id))

            # Get the top 5 most recent surveys
            recent_surveys = request.env['ddn.property.survey'].sudo().search(
                domain,
                order='create_date desc',
                limit=5
            )

            # Get unique properties from the surveys
            properties = recent_surveys.mapped('property_id')
            
            # Format the response using the same format as get_property
            property_data = [self._format_property_data(property) for property in properties]

            return Response(
                json.dumps({
                    'property_details': property_data,
                    'matched_count': len(property_data),
                    'message': 'Recent surveys fetched successfully'
                }),
                status=200,
                content_type='application/json'
            )

        except Exception as e:
            _logger.error(f"Error in get_recent_surveys: {str(e)}")
            return Response(
                json.dumps({'error': str(e)}),
                status=500,
                content_type='application/json'
            )

    @http.route('/api/property_types', type='http', auth='public', methods=['GET'], csrf=False)
    @check_permission
    def get_property_types(self, **kwargs):
        """Get all property types with their names and IDs."""
        try:
            property_types = request.env['ddn.property.type'].sudo().search([])
            
            property_type_list = [{
                'id': pt.id,
                'name': pt.name,
                'code': pt.code if hasattr(pt, 'code') else '',
                'description': pt.description if hasattr(pt, 'description') else '',
                'group_id': pt.group_id.id if pt.group_id else False,
                'group_name': pt.group_id.name if pt.group_id else ''
            } for pt in property_types]

            return Response(
                json.dumps({
                    'status': 'success',
                    'message': 'Property types fetched successfully',
                    'property_types': property_type_list
                }),
                status=200,
                content_type='application/json'
            )

        except Exception as e:
            _logger.error(f"Error in get_property_types: {str(e)}")
            return Response(
                json.dumps({
                    'status': 'error',
                    'message': 'An error occurred while fetching property types',
                    'details': str(e)
                }),
                status=500,
                content_type='application/json'
            )

    @http.route('/api/properties/list', type='http', auth='public', methods=['POST'], csrf=False)
    @check_permission
    def list_properties_by_status(self, **kwargs):
        """Get properties list based on status with pagination for infinite scroll."""
        try:
            data = json.loads(request.httprequest.data or "{}")
            
            # Get parameters
            status = data.get('status', '').strip()
            page = int(data.get('page', DEFAULT_PAGE))
            limit = int(data.get('limit', DEFAULT_LIMIT))
            company_id = data.get('company_id')
            zone_id = data.get('zone_id')
            ward_id = data.get('ward_id')
            surveyor_id = data.get('surveyor_id')
            search_term = data.get('search_term', '').strip()
            created_date = data.get('created_date', '').strip()  # Optional date filter (YYYY-MM-DD)
            
            # Validate status
            valid_statuses = ['surveyed', 'discovered', 'visit_again']
            if status and status not in valid_statuses:
                return Response(
                    json.dumps({'error': f'Invalid status. Must be one of: {", ".join(valid_statuses)}'}),
                    status=400,
                    content_type='application/json'
                )
            
            # Build domain
            domain = []
            
            # Add status filter
            if status:
                domain.append(('property_status', '=', status))
            
            # Add company filter
            if company_id:
                domain.append(('company_id', '=', company_id))
            
            # Add zone filter
            if zone_id:
                domain.append(('zone_id', '=', zone_id))
            
            # Add ward filter
            if ward_id:
                domain.append(('ward_id', '=', ward_id))
            
            # Add surveyor filter
            if surveyor_id:
                domain.append(('surveyer_id', '=', surveyor_id))
            
            # Add search term filter (search in upic_no, property_id, owner_name, mobile_no)
            if search_term:
                domain.append('|')
                domain.append('|')
                domain.append('|')
                domain.append(('upic_no', 'ilike', search_term))
                domain.append(('property_id', 'ilike', search_term))
                domain.append(('owner_name', 'ilike', search_term))
                domain.append(('mobile_no', 'ilike', search_term))
            
            # Add created_date filter if provided (filter by survey create_date, not property create_date)
            if created_date:
                try:
                    from datetime import datetime, timedelta
                    date_obj = datetime.strptime(created_date, '%Y-%m-%d')
                    start_dt = date_obj.replace(hour=0, minute=0, second=0, microsecond=0)
                    end_dt = date_obj.replace(hour=23, minute=59, second=59, microsecond=999999)
                    # Find all property_ids with a survey created on this date
                    survey_domain = [('create_date', '>=', start_dt), ('create_date', '<=', end_dt)]
                    survey_property_ids = request.env['ddn.property.survey'].sudo().search(survey_domain).mapped('property_id.id')
                    if survey_property_ids:
                        domain.append(('id', 'in', survey_property_ids))
                    else:
                        # No surveys on this date, return empty result
                        domain.append(('id', '=', 0))
                except Exception as e:
                    _logger.error(f"Invalid created_date format: {created_date} - {str(e)}")
            
            # Calculate offset for pagination
            offset = (page - 1) * limit
            
            # Get total count for pagination info
            total_count = request.env['ddn.property.info'].sudo().search_count(domain)
            
            # Get properties with pagination
            properties = request.env['ddn.property.info'].sudo().search(
                domain,
                offset=offset,
                limit=limit,
                order='create_date desc'  # Most recent first
            )
            
            # Format properties data using the same format as get_property_details
            property_data = [self._format_property_data(property) for property in properties]
            
            # Calculate pagination info
            total_pages = (total_count + limit - 1) // limit  # Ceiling division
            has_next_page = page < total_pages
            has_prev_page = page > 1
            
            response_data = {
                "property_details": property_data,
                "matched_count": len(property_data),
                "pagination": {
                    "current_page": page,
                    "total_pages": total_pages,
                    "total_count": total_count,
                    "limit": limit,
                    "has_next_page": has_next_page,
                    "has_prev_page": has_prev_page,
                    "next_page": page + 1 if has_next_page else None,
                    "prev_page": page - 1 if has_prev_page else None
                },
                "filters": {
                    "status": status,
                    "company_id": company_id,
                    "zone_id": zone_id,
                    "ward_id": ward_id,
                    "surveyor_id": surveyor_id,
                    "search_term": search_term,
                    "created_date": created_date
                },
                "message": f"Found {len(property_data)} properties" if property_data else "No properties found"
            }
            
            return Response(
                json.dumps(response_data, default=str),
                status=200,
                content_type='application/json'
            )
            
        except jwt.ExpiredSignatureError:
            _logger.error("JWT token has expired")
            raise AccessError('JWT token has expired')
        except jwt.InvalidTokenError:
            _logger.error("Invalid JWT token")
            raise AccessError('Invalid JWT token')
        except Exception as e:
            _logger.error(f"Error in list_properties_by_status: {str(e)}")
            return Response(
                json.dumps({'error': str(e)}),
                status=500,
                content_type='application/json'
            )

    @http.route('/api/properties/status_counts', type='http', auth='public', methods=['POST'], csrf=False)
    @check_permission
    def get_property_status_counts(self, **kwargs):
        """Get count of properties by status for dashboard/filtering."""
        try:
            data = json.loads(request.httprequest.data or "{}")
            company_id = data.get('company_id')
            zone_id = data.get('zone_id')
            ward_id = data.get('ward_id')
            surveyor_id = data.get('surveyor_id')
            
            # Build base domain
            domain = []
            if company_id:
                domain.append(('company_id', '=', company_id))
            if zone_id:
                domain.append(('zone_id', '=', zone_id))
            if ward_id:
                domain.append(('ward_id', '=', ward_id))
            if surveyor_id:
                domain.append(('surveyer_id', '=', surveyor_id))
            
            # Get counts for each status
            status_counts = {}
            valid_statuses = ['new', 'uploaded', 'pdf_downloaded', 'surveyed', 'unlocked', 'discovered', 'visit_again']
            
            for status in valid_statuses:
                status_domain = domain + [('property_status', '=', status)]
                count = request.env['ddn.property.info'].sudo().search_count(status_domain)
                status_counts[status] = count
            
            # Get total count
            total_count = request.env['ddn.property.info'].sudo().search_count(domain) if domain else request.env['ddn.property.info'].sudo().search_count([])
            
            response_data = {
                "status_counts": status_counts,
                "total_count": total_count,
                "filters": {
                    "company_id": company_id,
                    "zone_id": zone_id,
                    "ward_id": ward_id,
                    "surveyor_id": surveyor_id
                }
            }
            
            return Response(
                json.dumps(response_data),
                status=200,
                content_type='application/json'
            )
            
        except jwt.ExpiredSignatureError:
            _logger.error("JWT token has expired")
            raise AccessError('JWT token has expired')
        except jwt.InvalidTokenError:
            _logger.error("Invalid JWT token")
            raise AccessError('Invalid JWT token')
        except Exception as e:
            _logger.error(f"Error in get_property_status_counts: {str(e)}")
            return Response(
                json.dumps({'error': str(e)}),
                status=500,
                content_type='application/json'
            )

class PropertyIdDataAPI(http.Controller):
    @http.route('/api/property_id_data/search', type='http', auth='public', methods=['POST'], csrf=False)
    def search_property_id_data(self, **kwargs):
        try:
            data = json.loads(request.httprequest.data or '{}')
            parameter = data.get('parameter_name', '').strip()
            
            if not parameter:
                return Response(json.dumps({'error': 'Please provide parameter_name'}), status=400, content_type='application/json')
            
            # Search across all relevant fields
            records = request.env['property.id.data'].sudo().search([
                '|',  # OR condition
                '|',  # OR condition
                ('mobile_no', '=', parameter),
                ('property_id', '=', parameter),
                ('owner_name', 'ilike', parameter)
            ])
            
            result = [
                {
                    'property_id': rec.property_id,
                    'owner_name': rec.owner_name,
                    'address': rec.address,
                    'mobile_no': rec.mobile_no,
                    'currnet_tax': rec.currnet_tax,
                    'total_amount': rec.total_amount,
                }
                for rec in records
            ]
            return Response(json.dumps({'results': result}), status=200, content_type='application/json')
        except Exception as e:
            return Response(json.dumps({'error': str(e)}), status=500, content_type='application/json')

    @http.route('/api/property/delete_survey', type='http', auth='public', methods=['POST'], csrf=False)
    @check_permission
    def delete_survey(self, **kwargs):
        """Delete survey and reset property to allow re-survey."""
        try:
            data = json.loads(request.httprequest.data or "{}")
            upic_no = data.get('upic_no', '').strip()
            uuid = data.get('uuid', '').strip()
            
            # Validate input
            if not upic_no and not uuid:
                return Response(
                    json.dumps({'error': 'Either upic_no or uuid is required'}),
                    status=400,
                    content_type='application/json'
                )
            
            # Find property record
            domain = []
            if upic_no:
                domain = [('upic_no', '=', upic_no)]
            elif uuid:
                domain = [('uuid', '=', uuid)]
            
            property_record = request.env['ddn.property.info'].sudo().search(domain, limit=1)
            
            if not property_record:
                return Response(
                    json.dumps({'error': 'Property not found'}),
                    status=404,
                    content_type='application/json'
                )
            
            # Delete all survey records
            if property_record.survey_line_ids:
                property_record.survey_line_ids.unlink()
            
            # Reset property fields
            # Note: Clearing lat/long will automatically clear the computed digipin field
            reset_vals = {
                'property_status': 'pdf_downloaded',
                'address_line_1': False,
                'address_line_2': False,
                'property_id': False,
                'owner_name': False,
                'property_type': False,
                'latitude': False,
                'longitude': False,
                'mobile_no': False,
                'surveyer_id': False,
            }
            
            property_record.write(reset_vals)
            
            _logger.info(f"Survey deleted and property reset for: {property_record.upic_no}")
            
            return Response(
                json.dumps({
                    'status': 'success',
                    'message': 'Survey deleted successfully. Property reset to pdf_downloaded status.',
                    'upic_no': property_record.upic_no,
                    'uuid': property_record.uuid,
                    'property_status': property_record.property_status
                }),
                status=200,
                content_type='application/json'
            )
            
        except jwt.ExpiredSignatureError:
            _logger.error("JWT token has expired")
            return Response(
                json.dumps({'status': 'error', 'message': 'JWT token has expired'}),
                status=401,
                content_type='application/json'
            )
        except jwt.InvalidTokenError:
            _logger.error("Invalid JWT token")
            return Response(
                json.dumps({'status': 'error', 'message': 'Invalid JWT token'}),
                status=401,
                content_type='application/json'
            )
        except Exception as e:
            _logger.error(f"Error deleting survey: {str(e)}")
            return Response(
                json.dumps({'status': 'error', 'message': 'An error occurred', 'details': str(e)}),
                status=500,
                content_type='application/json'
            )

    @http.route('/api/surveyor/surveys', type='http', auth='public', methods=['GET'], csrf=False)
    @check_permission
    def list_surveyor_surveys(self, **kwargs):
        try:
            page = int(request.httprequest.args.get('page', 1))
            limit = int(request.httprequest.args.get('limit', 10))
            offset = (page - 1) * limit

            # Use the new helper function
            user_id = extract_user_id_from_token(request.httprequest.headers.get('Authorization'))
            if not user_id:
                return Response(
                    json.dumps({'error': 'Invalid or missing authorization token'}),
                    status=401,
                    content_type='application/json'
                )

            # Search for properties surveyed by this surveyor
            domain = [('surveyer_id', '=', user_id)]
            
            # Get total count for pagination
            total_count = request.env['ddn.property.info'].sudo().search_count(domain)
            
            # Get paginated records
            properties = request.env['ddn.property.info'].sudo().search(
                domain,
                offset=offset,
                limit=limit,
                order='id desc'
            )

            # Format the response data
            survey_list = []
            for property in properties:
                survey_data = {
                    'upic_no': property.upic_no,
                    'property_id': property.id,
                    'status': property.property_status,
                    'address': {
                        'line1': property.address_line_1,
                        'line2': property.address_line_2
                    },
                    'owner_name': property.owner_name,
                    'mobile_no': property.mobile_no,
                    'zone': property.zone_id.name if property.zone_id else '',
                    'ward': property.ward_id.name if property.ward_id else '',
                    'colony': property.colony_id.name if property.colony_id else '',
                    'property_type': property.property_type.name if property.property_type else '',
                    'survey_details': []
                }

                # Add survey details if available
                for survey in property.survey_line_ids:
                    survey_details = {
                        'area': survey.area,
                        'total_floors': survey.total_floors,
                        'floor_number': survey.floor_number,
                        'father_name': survey.father_name,
                        'survey_date': survey.create_date.strftime('%Y-%m-%d %H:%M:%S') if survey.create_date else '',
                        'images': {
                            'image1': survey.image1_s3_url or "",
                            'image2': survey.image2_s3_url or ""
                        }
                    }
                    survey_data['survey_details'].append(survey_details)

                survey_list.append(survey_data)

            response = {
                'status': 'success',
                'data': {
                    'surveys': survey_list,
                    'pagination': {
                        'total_records': total_count,
                        'total_pages': (total_count + limit - 1) // limit,
                        'current_page': page,
                        'limit': limit
                    }
                }
            }

            return Response(
                json.dumps(response),
                status=200,
                content_type='application/json'
            )

        except Exception as e:
            _logger.error(f"Error in get_recent_surveys: {str(e)}")
            return Response(
                json.dumps({'error': str(e)}),
                status=500,
                content_type='application/json'
            )

def extract_user_id_from_token(token):
    if not token:
        raise AccessError('Authorization header is missing or invalid')
    if token.startswith("Bearer "):
        token = token[7:]
    decoded_token = jwt.decode(token, options={"verify_signature": False})
    return decoded_token['user_id']

class S3PresignAPI(Controller):
    @route('/api/s3_presigned_url', type='json', auth='public', methods=['POST'], csrf=False)
    def get_presigned_url(self, **kwargs):
        data = kwargs or request.httprequest.get_json(force=True, silent=True) or {}
        filename = data.get('filename')
        company_id = data.get('company_id')

        # Fetch company S3 credentials (adjust as per your model)
        company = request.env['res.company'].sudo().browse(company_id)
        AWS_ACCESS_KEY = company.aws_acsess_key
        AWS_SECRET_KEY = company.aws_secret_key
        AWS_REGION = company.aws_region
        S3_BUCKET_NAME = company.s3_bucket_name

        s3_client = boto3.client(
            's3',
            aws_access_key_id=AWS_ACCESS_KEY,
            aws_secret_access_key=AWS_SECRET_KEY,
            region_name=AWS_REGION
        )

        presigned_url = s3_client.generate_presigned_url(
            'put_object',
            Params={'Bucket': S3_BUCKET_NAME, 'Key': filename},
            ExpiresIn=3600  # 1 hour
        )
        return {'url': presigned_url}


