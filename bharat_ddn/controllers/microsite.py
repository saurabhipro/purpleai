from odoo import http
from odoo.http import request
from odoo.addons.web.controllers.utils import ensure_db, _get_login_redirect_url, is_user_internal
import pandas as pd
from io import BytesIO
import logging
_logger = logging.getLogger(__name__)

class CustomWebsite(http.Controller):
    
    @http.route('/get/<string:uuid>', auth='public', website=True)
    def get_property_details_by_uuid(self, uuid, **kw):
        property = request.env['ddn.property.info'].sudo().search([('uuid', '=', uuid)], limit=1)
        services = request.env['ddn.services'].sudo().search([('company_id','=',property.company_id.id)])

        if not property:
            return "No property found"
        return request.render('microsite.id_indore_microsite_template', {'property':property, 'services':services})
5