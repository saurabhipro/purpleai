import json

import base64
from odoo import http, _
from odoo.exceptions import UserError
from odoo.http import request
import logging


_logger = logging.getLogger(__name__)


class BpmnShareController(http.Controller):

    @http.route(['/bpmn_viewer/<access_token>'], type="http", auth="public", methods=['GET'], website=False, csrf=False)
    def share_bpmn(self, access_token):
        bpmn_model = request.env["rmt.bpmn.model"].sudo().search([["access_token", "=", access_token]], limit=1)
        if not bpmn_model:
            return request.not_found()
        values = {
            'bpmn_data': bpmn_model.bpmn_data,
            'modelId': bpmn_model.id,
            'title': bpmn_model.name,
            'desc': bpmn_model.desc,
        }
        return request.render("rmt_bpmn.bpmn_viewer", values)