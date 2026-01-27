# -*- coding: utf-8 -*-

from odoo import api, fields, models
import uuid

class BpmnModeler(models.Model):
    _name = 'rmt.bpmn.model'
    _description = 'BPMN Model'

    name = fields.Char("Bpmn Name")
    desc = fields.Text()
    parent_id = fields.Many2one('rmt.bpmn.model')
    bpmn_data = fields.Text()
    access_token = fields.Char()
    url_share = fields.Char()
    tag_ids = fields.Many2many('rmt.bpmn.model.tag', string="Tags")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals['access_token'] = str(uuid.uuid4())
        return super(BpmnModeler, self).create(vals_list)

    def actionShare(self):
        if not self.access_token:
            self.access_token = str(uuid.uuid4())

        if not self.url_share:
            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            self.url_share = f"{base_url}/bpmn_viewer/{self.access_token}"

        return {
            "type": "ir.actions.act_url",
            "target": "new",
            "url": self.url_share
        }

    def actionView(self):
        return {
            "type": "ir.actions.client",
            "tag": "rmt_bpmn.BpmnViewer"
        }

    def actionCreate(self):
        return {
            "type": "ir.actions.client",
            "tag": "rmt_bpmn.BpmnModeler",
        }


class BpmnModelerTag(models.Model):
    _name = 'rmt.bpmn.model.tag'
    _description = 'BPMN Model Tag'

    name = fields.Char()
