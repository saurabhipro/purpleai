# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class InvoiceRejectReasonWizard(models.TransientModel):
    _name = 'purple_ai.invoice_reject_reason_wizard'
    _description = 'Invoice Rejection Reason Wizard'

    invoice_processor_id = fields.Many2one(
        'purple_ai.invoice_processor',
        string='Invoice',
        required=True,
        readonly=True,
    )
    rejection_reason = fields.Text(string='Rejection Reason', required=True)

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        invoice_id = self.env.context.get('active_id')
        if invoice_id:
            vals['invoice_processor_id'] = invoice_id
        return vals

    def action_confirm_reject(self):
        self.ensure_one()
        if not (self.rejection_reason or '').strip():
            raise UserError(_("Please enter rejection reason."))

        self.invoice_processor_id.action_manager_reject_with_reason(self.rejection_reason)
        return {'type': 'ir.actions.act_window_close'}
