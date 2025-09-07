# -*- coding: utf-8 -*-

# -*- coding: utf-8 -*-

from odoo import api, fields, models, _

class InheritIrAttachment(models.Model):
	_inherit = 'ir.attachment'

	res_obj_model = fields.Char('Resource Object Model', readonly=True, help="The database object this attachment will be attached to.")
	res_obj_id = fields.Many2oneReference('Resource Object ID', model_field='res_obj_model',
									  readonly=True, help="The record id this is attached to.")

	@api.model_create_multi
	def create(self, vals_list):
		attachments = super(InheritIrAttachment, self).create(vals_list)
		if attachments:
			for attach in attachments:
				if attach.res_model == 'sale.order':
					attach['res_obj_model'] = attach.res_model
					attach['res_obj_id'] = attach.res_id
				if attach.res_model == 'purchase.order':
					attach['res_obj_model'] = attach.res_model
					attach['res_obj_id'] = attach.res_id
				if attach.res_model == 'account.move':
					attach['res_obj_model'] = attach.res_model
					attach['res_obj_id'] = attach.res_id
		return attachments


class InheritedSaleOrder(models.Model):
	_inherit = 'sale.order'


	def _compute_attachment_count(self):
		for product in self:
			product.attachment_count = self.env['ir.attachment'].search_count([
			('res_model', '=', 'sale.order'),
			'|',('res_obj_id', '=', self.id),('res_id', '=', self.id)
		])

	attachment_count = fields.Integer(compute='_compute_attachment_count', string="File")

	def action_open_attachments(self):
		attachment_action = self.env.ref('base.action_attachment')
		action = attachment_action.read()[0]
		action['domain'] = [('res_model', '=', 'sale.order'),'|',('res_obj_id', '=', self.id),('res_id', '=', self.id)]
		action['context'] = "{'default_res_model': '%s','default_res_ids': %d}" % (self._name, self.id)
		return action


	def action_quotation_send(self):
		''' Opens a wizard to compose an email, with relevant mail template loaded by default '''
		self.ensure_one()
		self.order_line._validate_analytic_distribution()
		lang = self.env.context.get('lang')
		mail_template = self._find_mail_template()
		if mail_template and mail_template.lang:
			lang = mail_template._render_lang(self.ids)[self.id]
		if mail_template and mail_template.lang:
			attachment_ids = self.env['ir.attachment'].search([
				('res_model', '=', 'sale.order'),('res_obj_id', 'in', self.ids)
			])
			mail_template.attachment_ids = attachment_ids
		ctx = {
			'default_model': 'sale.order',
			'default_res_ids': self.ids,
			'default_use_template': bool(mail_template),
			'default_template_id': mail_template.id if mail_template else None,
			'default_composition_mode': 'comment',
			'mark_so_as_sent': True,
			'default_email_layout_xmlid': 'mail.mail_notification_layout_with_responsible_signature',
			'proforma': self.env.context.get('proforma', False),
			'force_email': True,
			'model_description': self.with_context(lang=lang).type_name,
		}
		return {
			'type': 'ir.actions.act_window',
			'view_mode': 'form',
			'res_model': 'mail.compose.message',
			'views': [(False, 'form')],
			'view_id': False,
			'target': 'new',
			'context': ctx,
		}



# class InheritedMailComposer(models.TransientModel):
# 	_inherit = 'mail.compose.message'

# 	def send_mail(self, auto_commit=False):
# 		""" Process the wizard content and proceed with sending the related
# 			email(s), rendering any template patterns on the fly if needed. """
# 		notif_layout = self._context.get('custom_layout')
# 		# Several custom layouts make use of the model description at rendering, e.g. in the
# 		# 'View <document>' button. Some models are used for different business concepts, such as
# 		# 'purchase.order' which is used for a RFQ and and PO. To avoid confusion, we must use a
# 		# different wording depending on the state of the object.
# 		# Therefore, we can set the description in the context from the beginning to avoid falling
# 		# back on the regular display_name retrieved in '_notify_prepare_template_context'.
# 		model_description = self._context.get('model_description')
# 		for wizard in self:
# 			# Duplicate attachments linked to the email.template.
# 			# Indeed, basic mail.compose.message wizard duplicates attachments in mass
# 			# mailing mode. But in 'single post' mode, attachments of an email template
# 			# also have to be duplicated to avoid changing their ownership.
# 			if wizard.attachment_ids and wizard.composition_mode != 'mass_mail' and wizard.template_id:
# 				new_attachment_ids = []
# 				for attachment in wizard.attachment_ids:
# 					if self._context.get('restrict_attachment') == True:
# 						new_attachment_ids.append(attachment.id)
# 					else:
# 						if attachment in wizard.template_id.attachment_ids:
# 							new_attachment_ids.append(attachment.copy({'res_model': 'mail.compose.message', 'res_id': wizard.id}).id)
# 						else:
# 							new_attachment_ids.append(attachment.id)
# 				new_attachment_ids.reverse()
# 				wizard.write({'attachment_ids': [(6, 0, new_attachment_ids)]})

# 			# Mass Mailing
# 			mass_mode = wizard.composition_mode in ('mass_mail', 'mass_post')

# 			Mail = self.env['mail.mail']
# 			ActiveModel = self.env[wizard.model] if wizard.model and hasattr(self.env[wizard.model], 'message_post') else self.env['mail.thread']
# 			if wizard.composition_mode == 'mass_post':
# 				# do not send emails directly but use the queue instead
# 				# add context key to avoid subscribing the author
# 				ActiveModel = ActiveModel.with_context(mail_notify_force_send=False, mail_create_nosubscribe=True)
# 			# wizard works in batch mode: [res_id] or active_ids or active_domain
# 			if mass_mode and wizard.use_active_domain and wizard.model:
# 				res_ids = self.env[wizard.model].search(safe_eval(wizard.active_domain)).ids
# 			elif mass_mode and wizard.model and self._context.get('active_ids'):
# 				res_ids = self._context['active_ids']
# 			else:
# 				res_ids = [wizard.res_id]

# 			batch_size = int(self.env['ir.config_parameter'].sudo().get_param('mail.batch_size')) or self._batch_size
# 			sliced_res_ids = [res_ids[i:i + batch_size] for i in range(0, len(res_ids), batch_size)]

# 			if wizard.composition_mode == 'mass_mail' or wizard.is_log or (wizard.composition_mode == 'mass_post' and not wizard.notify):  # log a note: subtype is False
# 				subtype_id = False
# 			elif wizard.subtype_id:
# 				subtype_id = wizard.subtype_id.id
# 			else:
# 				subtype_id = self.env['ir.model.data'].xmlid_to_res_id('mail.mt_comment')

# 			for res_ids in sliced_res_ids:
# 				batch_mails = Mail
# 				all_mail_values = wizard.get_mail_values(res_ids)
# 				for res_id, mail_values in all_mail_values.items():
# 					if wizard.composition_mode == 'mass_mail':
# 						batch_mails |= Mail.create(mail_values)
# 					else:
# 						post_params = dict(
# 							message_type=wizard.message_type,
# 							subtype_id=subtype_id,
# 							email_layout_xmlid=notif_layout,
# 							add_sign=not bool(wizard.template_id),
# 							mail_auto_delete=wizard.template_id.auto_delete if wizard.template_id else True,
# 							model_description=model_description)
# 						post_params.update(mail_values)
# 						if ActiveModel._name == 'mail.thread':
# 							if wizard.model:
# 								post_params['model'] = wizard.model
# 								post_params['res_id'] = res_id
# 							if not ActiveModel.message_notify(**post_params):
# 								# if message_notify returns an empty record set, no recipients where found.
# 								raise UserError(_("No recipient found."))
# 						else:
# 							ActiveModel.browse(res_id).message_post(**post_params)

# 				if wizard.composition_mode == 'mass_mail':
# 					batch_mails.send(auto_commit=auto_commit)

