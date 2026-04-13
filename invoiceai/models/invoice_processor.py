# -*- coding: utf-8 -*-
import json
import logging
from html import escape
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class InvoiceProcessor(models.Model):
    _name = 'purple_ai.invoice_processor'
    _description = 'Invoice review queue (AI extraction)'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    process_id = fields.Char(
        string='Process ID',
        readonly=True,
        copy=False,
        index=True,
        default='New',
    )
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
    overall_status = fields.Selection([
        ('draft_extracted', 'Draft Extracted'),
        ('pending_vrf_field_mapping', 'Pending VRF Field Mapping'),
        ('gl_decision_in_progress', 'GL Decision In Progress'),
        ('waiting_fa_schedule_update', 'Waiting FA Schedule Update'),
        ('waiting_prepaid_review', 'Waiting Prepaid Review'),
        ('pending_manager_approval', 'Pending Manager Approval'),
        ('manager_approved', 'Manager Approved'),
        ('manager_rejected', 'Manager Rejected'),
        ('ready_for_tally', 'Ready for Tally'),
        ('hold_vrf_vendor_missing', 'Hold - Vendor Missing in VRF'),
        ('hold_last_provision', 'Hold - Move to Last Provisions'),
        ('hold_foreign_invoice', 'Hold - Foreign Invoice'),
        ('hold_advance_proforma', 'Hold - Move to Advance'),
        ('validation_failed', 'Validation Failed'),
        ('posted', 'Posted'),
        ('cancelled', 'Cancelled'),
    ], string='Status', compute='_compute_overall_status', store=True, tracking=True)
    manager_user_id = fields.Many2one('res.users', related='client_id.manager_user_id', store=True, readonly=True)
    approved_by = fields.Many2one('res.users', string='Approved By', readonly=True)
    approved_on = fields.Datetime(string='Approved On', readonly=True)
    rejected_by = fields.Many2one('res.users', string='Rejected By', readonly=True)
    rejected_on = fields.Datetime(string='Rejected On', readonly=True)
    rejection_reason = fields.Text(string='Rejection Reason')
    is_on_hold = fields.Boolean(string='On Hold', compute='_compute_boolean_flags')
    is_manager_approved = fields.Boolean(string='Manager Approved', compute='_compute_boolean_flags')
    is_ready_for_tally = fields.Boolean(string='Ready for Tally', compute='_compute_boolean_flags')
    is_posted_to_tally = fields.Boolean(string='Posted to Tally', compute='_compute_boolean_flags')
    status_with_icon = fields.Char(string='Status', compute='_compute_status_with_icon')
    reconciliation_state = fields.Selection([
        ('pending', 'Pending'),
        ('reconciled', 'Reconciled'),
        ('reopened', 'Reopened'),
    ], string='Reconciliation State', default='pending', tracking=True)
    reconciled_by = fields.Many2one('res.users', string='Reconciled By', readonly=True)
    reconciled_on = fields.Datetime(string='Reconciled On', readonly=True)
    reconciliation_note = fields.Text(string='Reconciliation Note')
    general_data_html = fields.Html(string='General Data Summary', compute='_compute_general_data_html')
    financial_data_html = fields.Html(string='Financial Data Summary', compute='_compute_financial_data_html', sanitize=False)
    boolean_data_html = fields.Html(string='Boolean Data Summary', compute='_compute_boolean_data_html', sanitize=False)
    is_foreign_invoice = fields.Boolean(string='Is Foreign Invoice', compute='_compute_extracted_booleans')
    is_tds_applicable = fields.Boolean(string='Is TDS Applicable', compute='_compute_extracted_booleans')
    is_gst_applicable = fields.Boolean(string='Is GST Applicable', compute='_compute_extracted_booleans')
    is_rcm_applicable = fields.Boolean(string='Is RCM Applicable', compute='_compute_extracted_booleans')
    is_services_invoice = fields.Boolean(string='Is Services Invoice', compute='_compute_extracted_booleans')
    is_capex = fields.Boolean(string='Is CapEx', compute='_compute_extracted_booleans')
    is_prepaid = fields.Boolean(string='Is Prepaid', compute='_compute_extracted_booleans')
    belongs_to_next_period = fields.Boolean(string='Belongs To Next Period', compute='_compute_extracted_booleans')
    is_proforma_invoice = fields.Boolean(string='Is Proforma Invoice', compute='_compute_extracted_booleans')

    validation_log = fields.Html(string='Validation Report')
    is_validated = fields.Boolean(default=False)

    @api.depends(
        'process_id', 'status_with_icon', 'invoice_number', 'invoice_date',
        'vendor_name', 'partner_id', 'supplier_gstin', 'vendor_bank_account',
        'po_number', 'service_type'
    )
    def _compute_general_data_html(self):
        def verify_btn(val):
            sval = escape(str(val or ""))
            if not sval or sval == "-":
                return ""
            js_safe = sval.replace("'", "\\'")
            return (
                f"<button class='btn btn-sm btn-outline-primary py-0 px-2' "
                f"onclick=\"window.find && window.find('{js_safe}')\" "
                f"title='Find in document'><i class='fa fa-search'></i></button>"
            )

        for rec in self:
            rows = [
                ("Process ID", rec.process_id or "-"),
                ("Status", rec.status_with_icon or "-"),
                ("Invoice Number", rec.invoice_number or "-"),
                ("Invoice Date", rec.invoice_date.strftime('%Y-%m-%d') if rec.invoice_date else "-"),
                ("Vendor Name", rec.vendor_name or "-"),
                ("Vendor/Partner", rec.partner_id.display_name if rec.partner_id else "-"),
                ("Supplier GSTIN", rec.supplier_gstin or "-"),
                ("Vendor Bank Account", rec.vendor_bank_account or "-"),
                ("PO Number", rec.po_number or "-"),
                ("Service Type", rec.service_type or "-"),
            ]
            tr = []
            for label, value in rows:
                tr.append(
                    "<tr style='transition: all .15s ease;'>"
                    f"<th style='width:32%; padding:10px; border-bottom:1px solid #eef1f4;'>{label}</th>"
                    f"<td style='padding:10px; border-bottom:1px solid #eef1f4;'>{escape(str(value))}</td>"
                    f"<td style='width:48px; text-align:center; padding:10px; border-bottom:1px solid #eef1f4;'>{verify_btn(value)}</td>"
                    "</tr>"
                )
            rec.general_data_html = (
                "<style>"
                ".o_general_data_table tbody tr:hover{background:#f3f7ff;}"
                "</style>"
                "<table class='table table-sm o_general_data_table' style='border:1px solid #eef1f4; border-radius:8px; overflow:hidden;'>"
                "<tbody>"
                + "".join(tr) +
                "</tbody></table>"
            )

    @api.depends('untaxed_amount', 'gst_rate', 'gst_amount', 'total_amount', 'tds_rate', 'tds_amount', 'net_payable')
    def _compute_financial_data_html(self):
        def verify_btn(val):
            sval = str(val or "")
            if not sval:
                return ""
            safe_html = escape(sval)
            js_safe = safe_html.replace("'", "\\'")
            return (
                f"<button class='btn btn-sm btn-outline-primary py-0 px-2' "
                f"onclick=\"window.find && window.find('{js_safe}')\" "
                f"title='Find in document'><i class='fa fa-search'></i></button>"
            )

        for rec in self:
            rows = [
                ("Untaxed Amount", f"{rec.untaxed_amount:,.2f}"),
                ("GST Rate (%)", f"{rec.gst_rate:,.2f}"),
                ("GST Amount", f"{rec.gst_amount:,.2f}"),
                ("Total Invoice Amount", f"{rec.total_amount:,.2f}"),
                ("TDS Rate (%)", f"{rec.tds_rate:,.2f}"),
                ("TDS Deductible", f"{rec.tds_amount:,.2f}"),
                ("Net Payable", f"{rec.net_payable:,.2f}"),
            ]
            tr = []
            for label, value in rows:
                tr.append(
                    "<tr style='transition: all .15s ease;'>"
                    f"<th style='width:32%; padding:10px; border-bottom:1px solid #eef1f4;'>{label}</th>"
                    f"<td style='padding:10px; border-bottom:1px solid #eef1f4;'>{escape(value)}</td>"
                    f"<td style='width:48px; text-align:center; padding:10px; border-bottom:1px solid #eef1f4;'>{verify_btn(value)}</td>"
                    "</tr>"
                )
            rec.financial_data_html = (
                "<style>.o_financial_data_table tbody tr:hover{background:#f3f7ff;}</style>"
                "<table class='table table-sm o_financial_data_table' style='border:1px solid #eef1f4; border-radius:8px; overflow:hidden;'>"
                "<tbody>" + "".join(tr) + "</tbody></table>"
            )

    @api.depends('extracted_data')
    def _compute_extracted_booleans(self):
        bool_keys = {
            'is_foreign_invoice': 'is_foreign_invoice',
            'is_tds_applicable': 'is_tds_applicable',
            'is_gst_applicable': 'is_gst_applicable',
            'is_rcm_applicable': 'is_rcm_applicable',
            'is_services_invoice': 'is_services_invoice',
            'is_capex': 'is_capex',
            'is_prepaid': 'is_prepaid',
            'belongs_to_next_period': 'belongs_to_next_period',
            'is_proforma_invoice': 'is_proforma_invoice',
        }

        def to_bool(val):
            if isinstance(val, bool):
                return val
            sval = str(val or '').strip().lower()
            return sval in {'1', 'true', 'yes', 'y'}

        for rec in self:
            source = {}
            try:
                if rec.extracted_data:
                    raw = json.loads(rec.extracted_data)
                    for k, v in raw.items():
                        source[str(k).lower()] = v.get('value') if isinstance(v, dict) else v
            except Exception:
                source = {}
            for field_name, key in bool_keys.items():
                setattr(rec, field_name, to_bool(source.get(key)))

    @api.depends(
        'is_validated', 'is_on_hold', 'is_manager_approved', 'is_ready_for_tally', 'is_posted_to_tally',
        'is_foreign_invoice', 'is_tds_applicable', 'is_gst_applicable', 'is_rcm_applicable',
        'is_services_invoice', 'is_capex', 'is_prepaid', 'belongs_to_next_period', 'is_proforma_invoice'
    )
    def _compute_boolean_data_html(self):
        for rec in self:
            rows = [
                ("Is Validated", rec.is_validated),
                ("Is On Hold", rec.is_on_hold),
                ("Is Manager Approved", rec.is_manager_approved),
                ("Is Ready For Tally", rec.is_ready_for_tally),
                ("Is Posted To Tally", rec.is_posted_to_tally),
                ("Is Foreign Invoice", rec.is_foreign_invoice),
                ("Is TDS Applicable", rec.is_tds_applicable),
                ("Is GST Applicable", rec.is_gst_applicable),
                ("Is RCM Applicable", rec.is_rcm_applicable),
                ("Is Services Invoice", rec.is_services_invoice),
                ("Is CapEx", rec.is_capex),
                ("Is Prepaid", rec.is_prepaid),
                ("Belongs To Next Period", rec.belongs_to_next_period),
                ("Is Proforma Invoice", rec.is_proforma_invoice),
            ]
            tr = []
            for label, val in rows:
                badge = (
                    "<span class='badge rounded-pill text-bg-success'>Yes</span>"
                    if val else
                    "<span class='badge rounded-pill text-bg-secondary'>No</span>"
                )
                tr.append(
                    "<tr style='transition: all .15s ease;'>"
                    f"<th style='width:55%; padding:10px; border-bottom:1px solid #eef1f4;'>{label}</th>"
                    f"<td style='padding:10px; border-bottom:1px solid #eef1f4;'>{badge}</td>"
                    "</tr>"
                )
            rec.boolean_data_html = (
                "<style>.o_boolean_data_table tbody tr:hover{background:#f3f7ff;}</style>"
                "<table class='table table-sm o_boolean_data_table' style='border:1px solid #eef1f4; border-radius:8px; overflow:hidden;'>"
                "<tbody>" + "".join(tr) + "</tbody></table>"
            )

    @api.depends('state', 'workflow_status', 'approval_state')
    def _compute_overall_status(self):
        hold_statuses = {
            'hold_vrf_vendor_missing',
            'hold_last_provision',
            'hold_foreign_invoice',
            'hold_advance_proforma',
        }
        for rec in self:
            if rec.state == 'posted':
                rec.overall_status = 'posted'
            elif rec.state == 'cancel':
                rec.overall_status = 'cancelled'
            elif rec.state == 'failed':
                rec.overall_status = 'validation_failed'
            elif rec.workflow_status in hold_statuses:
                rec.overall_status = rec.workflow_status
            elif rec.approval_state == 'rejected' or rec.workflow_status == 'manager_rejected':
                rec.overall_status = 'manager_rejected'
            elif rec.workflow_status:
                rec.overall_status = rec.workflow_status
            else:
                rec.overall_status = 'draft_extracted'

    @api.depends('overall_status', 'approval_state', 'state')
    def _compute_boolean_flags(self):
        hold_statuses = {
            'hold_vrf_vendor_missing',
            'hold_last_provision',
            'hold_foreign_invoice',
            'hold_advance_proforma',
        }
        for rec in self:
            rec.is_on_hold = rec.overall_status in hold_statuses
            rec.is_manager_approved = rec.approval_state == 'approved'
            rec.is_ready_for_tally = rec.overall_status == 'ready_for_tally'
            rec.is_posted_to_tally = rec.state == 'posted' or rec.overall_status == 'posted'

    @api.depends('overall_status')
    def _compute_status_with_icon(self):
        icon_map = {
            'draft_extracted': '📝',
            'pending_vrf_field_mapping': '📌',
            'gl_decision_in_progress': '⚙️',
            'waiting_fa_schedule_update': '🏗️',
            'waiting_prepaid_review': '📅',
            'pending_manager_approval': '⏳',
            'manager_approved': '✅',
            'manager_rejected': '❌',
            'ready_for_tally': '📤',
            'hold_vrf_vendor_missing': '⛔',
            'hold_last_provision': '⛔',
            'hold_foreign_invoice': '⛔',
            'hold_advance_proforma': '⛔',
            'validation_failed': '⚠️',
            'posted': '✅',
            'cancelled': '🚫',
        }
        labels = dict(self._fields['overall_status'].selection)
        for rec in self:
            label = labels.get(rec.overall_status, rec.overall_status or '')
            rec.status_with_icon = f"{icon_map.get(rec.overall_status, '•')} {label}" if label else '•'

    def action_mark_reconciled(self):
        now = fields.Datetime.now()
        for rec in self:
            rec.write({
                'reconciliation_state': 'reconciled',
                'reconciled_by': self.env.user.id,
                'reconciled_on': now,
            })
        return True

    def action_reopen_reconciliation(self):
        for rec in self:
            rec.write({
                'reconciliation_state': 'reopened',
            })
        return True

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

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('process_id') or vals.get('process_id') == 'New':
                vals['process_id'] = self.env['ir.sequence'].next_by_code('purple_ai.invoice_processor') or 'New'
        return super().create(vals_list)

    @api.constrains('process_id')
    def _check_process_id_unique(self):
        for rec in self:
            if not rec.process_id or rec.process_id == 'New':
                continue
            dup = self.search_count([('id', '!=', rec.id), ('process_id', '=', rec.process_id)])
            if dup:
                raise UserError(_("Process ID must be unique."))

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
        self.ensure_one()
        self._check_manager_permission()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Reject Invoice'),
            'res_model': 'purple_ai.invoice_reject_reason_wizard',
            'view_mode': 'form',
            'view_id': self.env.ref('invoiceai.view_invoice_reject_reason_wizard_form').id,
            'target': 'new',
            'context': {
                'default_invoice_processor_id': self.id,
                'active_id': self.id,
                'active_model': 'purple_ai.invoice_processor',
            },
        }

    def action_manager_reject_with_reason(self, reason):
        self.ensure_one()
        self._check_manager_permission()
        clean_reason = (reason or '').strip()
        if not clean_reason:
            raise UserError(_("Please enter Rejection Reason before rejecting."))

        now = fields.Datetime.now()
        self.write({
            'approval_state': 'rejected',
            'rejected_by': self.env.user.id,
            'rejected_on': now,
            'approved_by': False,
            'approved_on': False,
            'rejection_reason': clean_reason,
            'workflow_status': 'manager_rejected',
        })
        self.message_post(
            body=_(
                "<b>Invoice Rejected</b><br/>"
                "By: %s<br/>"
                "Reason: %s"
            ) % (self.env.user.display_name, escape(clean_reason))
        )
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
