# -*- coding: utf-8 -*-
from odoo import http
from .main import *

class Master(http.Controller):

    @http.route([
        '/api/zone/<int:company_id>',
        '/api/zone/<int:company_id>/<int:zone_id>'
    ], type='http', auth='public', methods=['GET', 'POST', 'PUT', 'DELETE'], csrf=False)
    @check_permission
    def get_zones(self, company_id=None, zone_id=None, **kwargs):
        try:
            # Ensure company_id is provided
            if not company_id:
                return Response(json.dumps({'error': 'company_id is required'}), status=400, content_type='application/json')

            # Parse incoming JSON data
            data = json.loads(request.httprequest.data or "{}")

            if request.httprequest.method == 'GET':
                if zone_id:
                    zone = request.env['ddn.zone'].sudo().search([
                        ('id', '=', zone_id), ('company_id', '=', company_id)
                    ], limit=1)
                    if not zone:
                        return Response(json.dumps({'error': 'Zone not found'}), status=404, content_type='application/json')
                    return Response(json.dumps({
                        'id': zone.id,
                        'name': zone.name,
                        'company_id': zone.company_id.id if zone.company_id else None,
                        'company_name': zone.company_id.name if zone.company_id else None
                    }), status=200, content_type='application/json')

                zones = request.env['ddn.zone'].sudo().search([('company_id', '=', company_id)])
                return Response(json.dumps([
                    {
                        'id': zone.id,
                        'name': zone.name,
                        'company_id': zone.company_id.id if zone.company_id else None,
                        'company_name': zone.company_id.name if zone.company_id else None
                    } for zone in zones
                ]), status=200, content_type='application/json')

            if request.httprequest.method == 'POST':
                name = data.get('name')
                if not name:
                    return Response(json.dumps({'error': 'Name is required'}), status=400, content_type='application/json')

                zone = request.env['ddn.zone'].sudo().create({
                    'name': name,
                    'company_id': company_id
                })
                return Response(json.dumps({
                    'id': zone.id,
                    'name': zone.name,
                    'company_id': zone.company_id.id if zone.company_id else None,
                    'company_name': zone.company_id.name if zone.company_id else None
                }), status=201, content_type='application/json')

            if request.httprequest.method == 'PUT' and zone_id:
                zone = request.env['ddn.zone'].sudo().search([
                    ('id', '=', zone_id), ('company_id', '=', company_id)
                ], limit=1)
                if not zone:
                    return Response(json.dumps({'error': 'Zone not found'}), status=404, content_type='application/json')

                name = data.get('name')
                if name:
                    zone.write({'name': name})

                return Response(json.dumps({
                    'id': zone.id,
                    'name': zone.name,
                    'company_id': zone.company_id.id if zone.company_id else None,
                    'company_name': zone.company_id.name if zone.company_id else None
                }), status=200, content_type='application/json')

            if request.httprequest.method == 'DELETE' and zone_id:
                zone = request.env['ddn.zone'].sudo().search([
                    ('id', '=', zone_id), ('company_id', '=', company_id)
                ], limit=1)
                if not zone:
                    return Response(json.dumps({'error': 'Zone not found'}), status=404, content_type='application/json')

                zone.unlink()
                return Response(json.dumps({'status': 'deleted'}), status=200, content_type='application/json')

        except Exception as e:
            return Response(json.dumps({'error': str(e)}), status=500, content_type='application/json')

        except jwt.ExpiredSignatureError:
            raise AccessError('JWT token has expired')
        except jwt.InvalidTokenError:
            raise AccessError('Invalid JWT token')


    @http.route(['/api/ward/<int:company_id>', '/api/ward/<int:company_id>/<int:ward_id>'],
            type='http', auth='public', methods=['GET', 'POST', 'PUT', 'DELETE'], csrf=False)
    @check_permission
    def get_wards(self, company_id=None, ward_id=None, **kwargs):
        try:
            # Ensure company_id is provided
            if not company_id:
                return Response(json.dumps({'error': 'company_id is required'}), status=400, content_type='application/json')

            # Parse the JSON request body
            data = json.loads(request.httprequest.data or "{}")

            if request.httprequest.method == 'GET':
                if ward_id:
                    ward = request.env['ddn.ward'].sudo().search([
                        ('id', '=', ward_id), ('company_id', '=', company_id)
                    ], limit=1)
                    if not ward:
                        return Response(json.dumps({'error': 'Ward not found'}), status=404, content_type='application/json')
                    return Response(json.dumps({
                        'id': ward.id,
                        'name': ward.name,
                        'zone_id': ward.zone_id.id if ward.zone_id else None,
                        'zone_name': ward.zone_id.name if ward.zone_id else None,
                        'company_id': ward.company_id.id if ward.company_id else None,
                        'company_name': ward.company_id.name if ward.company_id else None
                    }), status=200, content_type='application/json')

                # Return all wards under the company
                wards = request.env['ddn.ward'].sudo().search([('company_id', '=', company_id)])
                return Response(json.dumps([
                    {
                        'id': ward.id,
                        'name': ward.name,
                        'zone_id': ward.zone_id.id if ward.zone_id else None,
                        'zone_name': ward.zone_id.name if ward.zone_id else None,
                        'company_id': ward.company_id.id if ward.company_id else None,
                        'company_name': ward.company_id.name if ward.company_id else None
                    } for ward in wards
                ]), status=200, content_type='application/json')

            if request.httprequest.method == 'POST':
                name = data.get('name')
                zone_id = data.get('zone_id')
                if not name or not zone_id:
                    return Response(json.dumps({'error': 'Name and zone_id are required'}), status=400, content_type='application/json')

                ward = request.env['ddn.ward'].sudo().create({
                    'name': name,
                    'zone_id': zone_id,
                    'company_id': company_id
                })
                return Response(json.dumps({
                    'id': ward.id,
                    'name': ward.name,
                    'zone_id': ward.zone_id.id if ward.zone_id else None,
                    'zone_name': ward.zone_id.name if ward.zone_id else None,
                    'company_id': ward.company_id.id if ward.company_id else None,
                    'company_name': ward.company_id.name if ward.company_id else None
                }), status=201, content_type='application/json')

            if request.httprequest.method == 'PUT' and ward_id:
                ward = request.env['ddn.ward'].sudo().search([
                    ('id', '=', ward_id), ('company_id', '=', company_id)
                ], limit=1)
                if not ward:
                    return Response(json.dumps({'error': 'Ward not found'}), status=404, content_type='application/json')

                name = data.get('name')
                zone_id = data.get('zone_id')

                updates = {}
                if name:
                    updates['name'] = name
                if zone_id:
                    updates['zone_id'] = zone_id
                if updates:
                    ward.write(updates)

                return Response(json.dumps({
                    'id': ward.id,
                    'name': ward.name,
                    'zone_id': ward.zone_id.id if ward.zone_id else None,
                    'zone_name': ward.zone_id.name if ward.zone_id else None,
                    'company_id': ward.company_id.id if ward.company_id else None,
                    'company_name': ward.company_id.name if ward.company_id else None
                }), status=200, content_type='application/json')

            if request.httprequest.method == 'DELETE' and ward_id:
                ward = request.env['ddn.ward'].sudo().search([
                    ('id', '=', ward_id), ('company_id', '=', company_id)
                ], limit=1)
                if not ward:
                    return Response(json.dumps({'error': 'Ward not found'}), status=404, content_type='application/json')
                ward.unlink()
                return Response(json.dumps({'status': 'deleted'}), status=200, content_type='application/json')

        except Exception as e:
            return Response(json.dumps({'error': str(e)}), status=500, content_type='application/json')
