# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class InheritedPurchaseOrder(models.Model):
	_inherit = 'purchase.order'


	def _compute_attachment_count(self):
		for product in self:
			product.attachment_count = self.env['ir.attachment'].search_count([
			('res_model', '=', 'purchase.order'),
			'|',('res_obj_id', '=', self.id),('res_id', '=', self.id)
		])

	attachment_count = fields.Integer(compute='_compute_attachment_count', string="File")

	def action_open_attachments(self):
		attachment_action = self.env.ref('base.action_attachment')
		action = attachment_action.read()[0]
		action['domain'] = [('res_model', '=', 'purchase.order'),'|',('res_obj_id', '=', self.id),('res_id', '=', self.id)]
		action['context'] = "{'default_res_model': '%s','default_res_ids': %d}" % (self._name, self.id)
		return action


	def action_rfq_send(self):
		'''
		This function opens a window to compose an email, with the edi purchase template message loaded by default
		'''
		self.ensure_one()
		ir_model_data = self.env['ir.model.data']
		try:
			if self.env.context.get('send_rfq', False):
				template_id = ir_model_data._xmlid_lookup('purchase.email_template_edi_purchase')[1]
			else:
				template_id = ir_model_data._xmlid_lookup('purchase.email_template_edi_purchase_done')[1]

		except ValueError:
			template_id = False
		try:
			compose_form_id = ir_model_data._xmlid_lookup('mail.email_compose_message_wizard_form')[1]
		except ValueError:
			compose_form_id = False
		ctx = dict(self.env.context or {})
		ctx.update({
			'default_model': 'purchase.order',
			'active_model': 'purchase.order',
			# 'active_id': self.ids,
			'default_res_ids': self.ids,
			'default_use_template': bool(template_id),
			'default_template_id': template_id if template_id else None,
			'default_composition_mode': 'comment',
			'custom_layout': "mail.mail_notification_paynow",
			'force_email': True,
			'mark_rfq_as_sent': True,
		})

		# In the case of a RFQ or a PO, we want the "View..." button in line with the state of the
		# object. Therefore, we pass the model description in the context, in the language in which
		# the template is rendered.
		lang = self.env.context.get('lang')
		# if {'default_template_id', 'default_model', 'default_res_ids'} <= ctx.keys():
		template = self.env['mail.template'].browse(ctx['default_template_id'])
		# 	if template and template.lang:
		# 		lang = template._render_lang([ctx['default_res_ids']])[ctx['default_res_ids']]
		if template:
			attachment_ids = self.env['ir.attachment'].search([
				('res_model', '=', 'purchase.order'),('res_obj_id', 'in', self.ids)
			])
			template.attachment_ids = attachment_ids

		self = self.with_context(lang=lang)
		if self.state in ['draft', 'sent']:
			ctx['model_description'] = _('Request for Quotation')
		else:
			ctx['model_description'] = _('Purchase Order')

		return {
			'name': _('Compose Email'),
			'type': 'ir.actions.act_window',
			'view_mode': 'form',
			'res_model': 'mail.compose.message',
			'views': [(compose_form_id, 'form')],
			'view_id': compose_form_id,
			'target': 'new',
			'context': ctx,
		}