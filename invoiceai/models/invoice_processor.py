# -*- coding: utf-8 -*-
import json
import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class InvoiceProcessor(models.Model):
    _name = 'purple_ai.invoice_processor'
    _description = 'Invoice review queue (AI extraction)'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    extraction_result_id = fields.Many2one('purple_ai.extraction_result', string='Extraction Source', required=True, ondelete='cascade')
    client_id = fields.Many2one('purple_ai.client', related='extraction_result_id.client_id', store=True)
    company_id = fields.Many2one('res.company', string='Company', related='client_id.company_id', store=True, readonly=True)
    filename = fields.Char(related='extraction_result_id.filename', store=True)
    data_html = fields.Html(related='extraction_result_id.data_html')
    pdf_file = fields.Binary(related='extraction_result_id.pdf_file', readonly=True)
    extracted_data = fields.Text(related='extraction_result_id.extracted_data', readonly=False, store=True)
    
    # Financial fields extracted/calculated
    vendor_name = fields.Char(string='Vendor Name')
    partner_id = fields.Many2one('res.partner', string='Vendor/Partner', tracking=True)
    invoice_date = fields.Date(string='Invoice Date')
    invoice_number = fields.Char(string='Invoice Number')
    supplier_gstin = fields.Char(string='Supplier GSTIN')
    vendor_bank_account = fields.Char(string='Vendor Bank Account')
    po_number = fields.Char(string='PO Number')
    service_type = fields.Char(string='Service Type')
    
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)

    untaxed_amount = fields.Monetary(string='Untaxed Amount', currency_field='currency_id')
    gst_rate = fields.Float(string='GST Rate (%)', default=18.0)
    gst_amount = fields.Monetary(string='GST Amount', currency_field='currency_id', compute='_compute_totals', store=True, readonly=False)
    
    tds_rate = fields.Float(string='TDS Rate (%)', default=10.0)
    tds_amount = fields.Monetary(string='TDS Deductible', currency_field='currency_id', compute='_compute_totals', store=True, readonly=False)
    
    total_amount = fields.Monetary(string='Total Invoice Amount', currency_field='currency_id', compute='_compute_totals', store=True, readonly=False)
    net_payable = fields.Monetary(string='Net Payable (to Vendor)', currency_field='currency_id', compute='_compute_totals', store=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('failed', 'Validation Failed'),
        ('posted', 'Posted'),
        ('cancel', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)

    workflow_status = fields.Selection([
        ('draft_extracted', 'Draft Extracted'),
        ('hold_vrf_vendor_missing', 'Hold - Vendor Missing in VRF'),
        ('hold_last_provision', 'Hold - Move to Last Provisions'),
        ('hold_foreign_invoice', 'Hold - Foreign Invoice'),
        ('hold_advance_proforma', 'Hold - Move to Advance'),
        ('pending_vrf_field_mapping', 'Pending VRF Field Mapping'),
        ('gl_decision_in_progress', 'GL Decision In Progress'),
        ('waiting_fa_schedule_update', 'Waiting FA Schedule Update'),
        ('waiting_prepaid_review', 'Waiting Prepaid Review'),
        ('validation_passed', 'Validation Passed'),
        ('pending_manager_approval', 'Pending Manager Approval'),
        ('manager_approved', 'Manager Approved'),
        ('manager_rejected', 'Manager Rejected'),
        ('ready_for_tally', 'Ready for Tally'),
    ], string='Workflow Status', default='draft_extracted', tracking=True)

    approval_state = fields.Selection([
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], string='Approval State', default='pending', tracking=True)
    manager_user_id = fields.Many2one('res.users', related='client_id.manager_user_id', store=True, readonly=True)
    approved_by = fields.Many2one('res.users', string='Approved By', readonly=True)
    approved_on = fields.Datetime(string='Approved On', readonly=True)
    rejected_by = fields.Many2one('res.users', string='Rejected By', readonly=True)
    rejected_on = fields.Datetime(string='Rejected On', readonly=True)
    rejection_reason = fields.Text(string='Rejection Reason')

    validation_log = fields.Html(string='Validation Report')
    is_validated = fields.Boolean(default=False)

    @api.depends('untaxed_amount', 'gst_rate', 'tds_rate')
    def _compute_totals(self):
        for rec in self:
            # Only update if in draft or failed state
            if rec.state in ('draft', 'failed'):
                rec.gst_amount = rec.untaxed_amount * (rec.gst_rate / 100.0)
                rec.tds_amount = rec.untaxed_amount * (rec.tds_rate / 100.0)
                rec.total_amount = rec.untaxed_amount + rec.gst_amount
                rec.net_payable = rec.total_amount - rec.tds_amount

    @api.model
    def _flat_data_from_extraction_json(self, extraction):
        """Lowercase keys so VENDOR_NAME / vendor_name both map; skip validations blob."""
        data = {}
        if not extraction.extracted_data:
            return data
        try:
            raw_data = json.loads(extraction.extracted_data)
            for key, val in raw_data.items():
                if key == 'validations':
                    continue
                lk = str(key).lower()
                data[lk] = val.get('value') if isinstance(val, dict) else val
        except Exception:
            pass
        return data

    @api.model
    def create_from_extraction(self, extraction_id):
        extraction = self.env['purple_ai.extraction_result'].browse(extraction_id)
        if not extraction.exists():
            _logger.warning('create_from_extraction: extraction id=%s does not exist', extraction_id)
            return self.browse()
        data = self._flat_data_from_extraction_json(extraction)

        # ── Helpers ────────────────────────────────────────────────────────────
        def to_float(val):
            """Parse monetary strings from any locale/format."""
            if not val:
                return 0.0
            try:
                return float(str(val).replace(',', '').replace('$', '').replace('₹', '').strip())
            except Exception:
                return 0.0

        def safe_date(val):
            """Parse date strings in any format GPT/Gemini might return."""
            if not val:
                return False
            from datetime import datetime
            val = str(val).strip()
            # Try ISO first (Gemini standard: 2026-03-14)
            for fmt in (
                '%Y-%m-%d',       # 2026-03-14
                '%d/%m/%Y',       # 14/03/2026
                '%d-%m-%Y',       # 14-03-2026
                '%m/%d/%Y',       # 03/14/2026
                '%d %B %Y',       # 14 March 2026
                '%d %b %Y',       # 14 Mar 2026
                '%B %d, %Y',      # March 14, 2026
                '%b %d, %Y',      # Mar 14, 2026
                '%d.%m.%Y',       # 14.03.2026
                '%Y/%m/%d',       # 2026/03/14
            ):
                try:
                    return datetime.strptime(val, fmt).date()
                except ValueError:
                    continue
            _logger.warning("safe_date: could not parse date string '%s'", val)
            return False

        # ── Build record values ─────────────────────────────────────────────────
        vendor = data.get('vendor_name') or data.get('supplier_name')
        partner = False
        if vendor:
            partner = self.env['res.partner'].search([('name', '=', vendor)], limit=1)

        vals = {
            'extraction_result_id': extraction.id,
            'vendor_name': vendor,
            'partner_id': partner.id if partner else False,
            'invoice_number': data.get('invoice_number') or data.get('bill_no'),
            'invoice_date': safe_date(data.get('invoice_date')),
            'untaxed_amount': to_float(data.get('untaxed_amount') or data.get('subtotal')),
            'supplier_gstin': data.get('supplier_gstin'),
            'vendor_bank_account': data.get('vendor_bank_account'),
            'po_number': data.get('po_number'),
            'service_type': data.get('service_type'),
            'workflow_status': 'draft_extracted',
            'approval_state': 'pending',
        }
        write_vals = {k: v for k, v in vals.items() if k != 'extraction_result_id'}
        existing = self.search([('extraction_result_id', '=', extraction.id)], limit=1)
        if existing:
            existing.write(write_vals)
            return existing
        proc = self.create(vals)
        return proc

    def _check_manager_permission(self):
        self.ensure_one()
        if self.env.user.has_group('base.group_system'):
            return True
        if self.manager_user_id and self.manager_user_id == self.env.user:
            return True
        raise UserError(_("Only the configured Client Manager can approve/reject this invoice."))

    def action_send_for_manager_approval(self):
        for rec in self:
            if rec.state == 'failed':
                raise UserError(_("Validation must pass before manager approval."))
            rec.write({
                'workflow_status': 'pending_manager_approval',
                'approval_state': 'pending',
                'rejection_reason': False,
            })
        return True

    def action_manager_approve(self):
        now = fields.Datetime.now()
        for rec in self:
            rec._check_manager_permission()
            if rec.state == 'failed':
                raise UserError(_("Cannot approve: invoice is in failed validation state."))
            rec.write({
                'approval_state': 'approved',
                'approved_by': self.env.user.id,
                'approved_on': now,
                'rejected_by': False,
                'rejected_on': False,
                'workflow_status': 'ready_for_tally',
            })
        return True

    def action_manager_reject(self):
        now = fields.Datetime.now()
        for rec in self:
            rec._check_manager_permission()
            if not (rec.rejection_reason or '').strip():
                raise UserError(_("Please enter Rejection Reason before rejecting."))
            rec.write({
                'approval_state': 'rejected',
                'rejected_by': self.env.user.id,
                'rejected_on': now,
                'approved_by': False,
                'approved_on': False,
                'workflow_status': 'manager_rejected',
            })
        return True

    def action_bulk_reprocess_pending(self):
        for rec in self:
            if rec.state == 'failed' or rec.approval_state == 'rejected':
                rec.write({
                    'workflow_status': 'gl_decision_in_progress',
                    'approval_state': 'pending',
                    'rejection_reason': False,
                })
                rec.action_validate()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Reprocess complete'),
                'message': _('Selected pending invoices were re-processed.'),
                'type': 'success',
                'sticky': False,
            },
        }

    @api.model
    def action_create_demo_invoices(self):
        """Create sample workflow invoices in the active company (idempotent)."""
        company = self.env.company
        template = self.env['purple_ai.extraction_master'].search([('name', '=', 'Invoice Extraction')], limit=1)
        if not template:
            raise UserError(_("Invoice Extraction template not found."))

        client = self.env['purple_ai.client'].sudo().search([
            ('name', '=', 'Demo AP Team'),
            ('company_id', '=', company.id),
        ], limit=1)
        if not client:
            client = self.env['purple_ai.client'].sudo().create({
                'name': 'Demo AP Team',
                'company_id': company.id,
                'extraction_master_id': template.id,
                'manager_user_id': self.env.user.id,
                'folder_path': '/home/odoo18/invoice/demo_ap_team',
            })

        samples = [
            ('INV-APPROVAL-001', 'pending_manager_approval', 'pending', 'draft'),
            ('INV-READY-002', 'ready_for_tally', 'approved', 'draft'),
            ('INV-FAILED-003', 'gl_decision_in_progress', 'pending', 'failed'),
            ('INV-FOREIGN-004', 'hold_foreign_invoice', 'pending', 'draft'),
            ('INV-REJECT-005', 'manager_rejected', 'rejected', 'draft'),
        ]
        created = 0
        for inv_no, workflow_status, approval_state, state in samples:
            exists = self.search([('invoice_number', '=', inv_no), ('company_id', '=', company.id)], limit=1)
            if exists:
                continue
            extraction = self.env['purple_ai.extraction_result'].sudo().create({
                'client_id': client.id,
                'filename': f'{inv_no}.pdf',
                'state': 'done',
            })
            vals = {
                'extraction_result_id': extraction.id,
                'vendor_name': 'Demo Vendor',
                'invoice_number': inv_no,
                'invoice_date': fields.Date.today(),
                'untaxed_amount': 10000 + (created * 1000),
                'state': state,
                'workflow_status': workflow_status,
                'approval_state': approval_state,
            }
            if approval_state == 'approved':
                vals.update({'approved_by': self.env.user.id, 'approved_on': fields.Datetime.now()})
            if approval_state == 'rejected':
                vals.update({
                    'rejected_by': self.env.user.id,
                    'rejected_on': fields.Datetime.now(),
                    'rejection_reason': 'Demo rejection reason',
                })
            self.sudo().create(vals)
            created += 1

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Demo invoices'),
                'message': _('Created %s demo invoice(s) in company %s.') % (created, company.name),
                'type': 'success',
                'sticky': False,
            },
        }
