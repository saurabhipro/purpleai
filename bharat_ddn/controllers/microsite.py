from odoo import http
from odoo.http import request
from odoo.addons.web.controllers.utils import ensure_db, _get_login_redirect_url, is_user_internal
import pandas as pd
from io import BytesIO
import logging
from markupsafe import Markup
_logger = logging.getLogger(__name__)

class CustomWebsite(http.Controller):
    
    def _get_template_by_company(self, property):
        """Determine which template to use based on company name."""
        if not property or not property.company_id:
            return 'bharat_ddn.id_indore_microsite_template'
        
        company_name = property.company_id.name.lower()
        # Check if company name contains "sambhaji" or "sambhajinagar"
        if 'sambhaji' in company_name or 'sambhajinagar' in company_name:
            return 'bharat_ddn.id_sambhaji_microsite_template'
        
        # Default to Indore template
        return 'bharat_ddn.id_indore_microsite_template'
    
    @http.route('/qr.html', auth='public', website=True)
    def get_property_details_by_ddn(self, **kw):
        """Handle QR code URL with ddn parameter (UPIC number)."""
        ddn = kw.get('ddn', '').strip()
        if not ddn:
            return "No property identifier provided"
        
        # Log the scan
        scan_url = request.httprequest.url
        
        # Search for property by UPIC number
        property = request.env['ddn.property.info'].sudo().search([('upic_no', '=', ddn)], limit=1)
        
        # Log the QR scan
        request.env['ddn.qr.scan'].sudo().create({
            'uuid': property.uuid if property else '',
            'scan_url': scan_url,
            'property_id': property.id if property else False,
        })
        
        if not property:
            return "No property found"
        
        # Get services and template based on company
        services = request.env['ddn.services'].sudo().search([('company_id','=',property.company_id.id)]) if property else request.env['ddn.services'].sudo().search([])
        template_name = self._get_template_by_company(property)
        
        return request.render(
            template_name,
            {
                'property': property,
                'services': services,
                'Markup': Markup,
            }
        )
    
    @http.route('/get/<string:uuid>', auth='public', website=True)
    def get_property_details_by_uuid(self, uuid, **kw):
        # Log the scan
        scan_url = request.httprequest.url
        property = request.env['ddn.property.info'].sudo().search([('uuid', '=', uuid)], limit=1)
        request.env['ddn.qr.scan'].sudo().create({
            'uuid': uuid,
            'scan_url': scan_url,
            'property_id': property.id if property else False,
        })
        services = request.env['ddn.services'].sudo().search([('company_id','=',property.company_id.id)]) if property else request.env['ddn.services'].sudo().search([])

        if not property:
            return "No property found"
        
        # Get template based on company
        template_name = self._get_template_by_company(property)
        
        return request.render(
            template_name,
            {
                'property': property,
                'services': services,
                'Markup': Markup,
            }
        )
