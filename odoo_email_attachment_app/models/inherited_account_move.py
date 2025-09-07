# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.tools.misc import formatLang, format_date, get_lang



class InheritedAccountMove(models.Model):
	_inherit = 'account.move'


	def _compute_attachment_count(self):
		for product in self:
			product.attachment_count = self.env['ir.attachment'].search_count([
			('res_model', '=', 'account.move'),
			'|',('res_obj_id', '=', self.id),('res_id', '=', self.id)
		])

	attachment_count = fields.Integer(compute='_compute_attachment_count', string="File")

	def action_open_attachments(self):
		attachment_action = self.env.ref('base.action_attachment')
		action = attachment_action.read()[0]
		action['domain'] = [('res_model', '=', 'account.move'),'|',('res_obj_id', '=', self.id),('res_id', '=', self.id)]
		action['context'] = "{'default_res_model': '%s','default_res_ids': %d}" % (self._name, self.id)
		return action


	def action_invoice_sent(self):
		""" Open a window to compose an email, with the edi invoice template
			message loaded by default
		"""
		self.ensure_one()
		template = self.env.ref('account.email_template_edi_invoice', raise_if_not_found=False)
		lang = get_lang(self.env)
		if template and template.lang:
			lang = template._render_lang(self.ids)[self.id]
		else:
			lang = lang.code
		compose_form = self.env.ref('account.account_invoice_send_wizard_form', raise_if_not_found=False)
		if template:
			attachment_ids = self.env['ir.attachment'].search([
				('res_model', '=', 'account.move'),('res_obj_id', 'in', self.ids)
			])
			template.attachment_ids = attachment_ids
		ctx = dict(
			default_model='account.move',
			default_res_ids=self.ids,
			# For the sake of consistency we need a default_res_model if
			# default_res_id is set. Not renaming default_model as it can
			# create many side-effects.
			default_res_model='account.move',
			default_use_template=bool(template),
			default_template_id=template and template.id or False,
			default_composition_mode='comment',
			mark_invoice_as_sent=True,
			custom_layout="mail.mail_notification_paynow",
			model_description=self.with_context(lang=lang).type_name,
			force_email=True
		)
		return {
			'name': _('Send Invoice'),
			'type': 'ir.actions.act_window',
			'view_type': 'form',
			'view_mode': 'form',
			'res_model': 'account.move.send',
			'views': [(compose_form, 'form')],
			'view_id': compose_form,
			'target': 'new',
			'context': ctx,
		}