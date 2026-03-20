# -*- coding: utf-8 -*-
import json
import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class InvoiceProcessor(models.Model):
    _name = 'purple_ai.invoice_processor'
    _description = 'Invoice Processor to Journal Entries'
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
    journal_id = fields.Many2one('account.journal', string='Journal', domain="[('company_id', '=', company_id), ('type', 'in', ('general', 'purchase'))]")

    # Account Overrides
    expense_account_id = fields.Many2one('account.account', string='Expense Account', domain="[('company_id', '=', company_id), ('account_type', '=', 'expense')]")
    gst_account_id = fields.Many2one('account.account', string='GST Account', domain="[('company_id', '=', company_id), ('account_type', 'in', ('asset_current', 'liability_current'))]")
    tds_account_id = fields.Many2one('account.account', string='TDS Account', domain="[('company_id', '=', company_id), ('account_type', 'in', ('liability_current', 'asset_current'))]")
    payable_account_id = fields.Many2one('account.account', string='Payable Account', domain="[('company_id', '=', company_id), ('account_type', '=', 'liability_payable')]")
    
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
        ('cancel', 'Cancelled')
    ], string='Status', default='draft', tracking=True)

    validation_log = fields.Html(string='Validation Report')
    is_validated = fields.Boolean(default=False)

    move_id = fields.Many2one('account.move', string='Journal Entry', readonly=True)

    @api.depends('untaxed_amount', 'gst_rate', 'tds_rate')
    def _compute_totals(self):
        for rec in self:
            # Only update if in draft or failed state
            if rec.state in ('draft', 'failed'):
                rec.gst_amount = rec.untaxed_amount * (rec.gst_rate / 100.0)
                rec.tds_amount = rec.untaxed_amount * (rec.tds_rate / 100.0)
                rec.total_amount = rec.untaxed_amount + rec.gst_amount
                rec.net_payable = rec.total_amount - rec.tds_amount

    def action_post(self):
        self.ensure_one()
        if self.move_id:
            raise UserError(_("Journal entry already created."))
        
        # Partner Logic: Try to find or create the vendor
        if not self.partner_id and self.vendor_name:
            partner = self.env['res.partner'].search([('name', '=', self.vendor_name)], limit=1)
            if not partner:
                partner = self.env['res.partner'].create({'name': self.vendor_name, 'supplier_rank': 1})
            self.partner_id = partner

        if not self.partner_id:
            raise UserError(_("Please select or specify a Vendor."))

        # Journal and Account Logic (Company Scoped)
        journal = self.journal_id or self.env['account.journal'].search([
            ('type', 'in', ('purchase', 'general')),
            ('company_id', '=', self.company_id.id)
        ], limit=1)
        if not journal:
             raise UserError(_("Please define a Purchase or General journal for company %s.") % self.company_id.name)

        # Smart defaults if fields are empty
        domain = [('company_id', '=', self.company_id.id)]
        expense_acc = self.expense_account_id or self.env['account.account'].search(domain + [('account_type', '=', 'expense')], limit=1)
        gst_acc = self.gst_account_id or self.env['account.account'].search(domain + [('name', 'ilike', 'GST')], limit=1)
        tds_acc = self.tds_account_id or self.env['account.account'].search(domain + [('name', 'ilike', 'TDS')], limit=1)
        payable_acc = (
            self.payable_account_id or 
            self.partner_id.with_company(self.company_id).property_account_payable_id or 
            self.env['account.account'].search(domain + [('account_type', '=', 'liability_payable')], limit=1)
        )

        if not expense_acc: raise UserError(_("Could not find an Expense account. Please specify one."))
        if not payable_acc: raise UserError(_("Could not find a Payable account. Please specify one."))

        line_ids = [
            (0, 0, {
                'name': _('Invoice %s - Purchase') % self.invoice_number,
                'debit': self.untaxed_amount,
                'credit': 0.0,
                'account_id': expense_acc.id,
                'partner_id': self.partner_id.id,
            }),
            (0, 0, {
                'name': _('Invoice %s - GST Input') % self.invoice_number,
                'debit': self.gst_amount,
                'credit': 0.0,
                'account_id': gst_acc.id if gst_acc else expense_acc.id, # Fallback to expense if no GST acc found
                'partner_id': self.partner_id.id,
            }),
            (0, 0, {
                'name': _('Invoice %s - TDS Deduction') % self.invoice_number,
                'debit': 0.0,
                'credit': self.tds_amount,
                'account_id': tds_acc.id if tds_acc else payable_acc.id, # Fallback to payable if no TDS acc found
                'partner_id': self.partner_id.id,
            }),
            (0, 0, {
                'name': _('Invoice %s - Vendor Net Payable') % self.invoice_number,
                'debit': 0.0,
                'credit': self.net_payable,
                'account_id': payable_acc.id,
                'partner_id': self.partner_id.id,
            }),
        ]

        move = self.env['account.move'].create({
            'company_id': self.company_id.id,
            'journal_id': journal.id,
            'date': self.invoice_date or fields.Date.today(),
            'ref': self.invoice_number,
            'line_ids': line_ids,
        })
        move.action_post()
        self.move_id = move.id
        self.state = 'posted'
        return True

    @api.model
    def create_from_extraction(self, extraction_id):
        extraction = self.env['purple_ai.extraction_result'].browse(extraction_id)
        data = {}
        if extraction.extracted_data:
            try:
                raw_data = json.loads(extraction.extracted_data)
                for key, val in raw_data.items():
                    data[key] = val.get('value') if isinstance(val, dict) else val
            except:
                pass
        
        # Clean numeric strings
        def to_float(val):
            if not val: return 0.0
            try:
                return float(str(val).replace(',', '').replace('$', '').replace('₹', '').strip())
            except:
                return 0.0

        # Try to find partner
        vendor = data.get('vendor_name') or data.get('supplier_name')
        partner = False
        if vendor:
            partner = self.env['res.partner'].search([('name', '=', vendor)], limit=1)

        vals = {
            'extraction_result_id': extraction.id,
            'vendor_name': vendor,
            'partner_id': partner.id if partner else False,
            'invoice_number': data.get('invoice_number') or data.get('bill_no'),
            'invoice_date': fields.Date.to_date(data.get('invoice_date')) if data.get('invoice_date') else False,
            'untaxed_amount': to_float(data.get('untaxed_amount') or data.get('subtotal')),
            'supplier_gstin': data.get('supplier_gstin'),
            'vendor_bank_account': data.get('vendor_bank_account'),
            'po_number': data.get('po_number'),
            'service_type': data.get('service_type'),
        }
        proc = self.create(vals)
        proc.action_validate()
        return proc
