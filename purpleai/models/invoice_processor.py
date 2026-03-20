# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from markupsafe import Markup
from odoo.exceptions import UserError
import json
import logging
import io
import csv
import base64

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

    def action_validate(self):
        """Dynamic Validation Engine: Runs active rules from the template."""
        for rec in self:
            template = rec.client_id.extraction_master_id
            active_rules = template.rule_ids.filtered(lambda r: r.active)
            
            rules_html = ["""
                <table class="table table-sm table-hover" style="border-collapse: separate; border-spacing: 0 4px;">
                    <thead style="background: #f8f9fa;">
                        <tr>
                            <th style="width: 50px; text-align: center; border-bottom: 2px solid #dee2e6;">Status</th>
                            <th style="border-bottom: 2px solid #dee2e6;">Rule Name</th>
                            <th style="border-bottom: 2px solid #dee2e6;">Description</th>
                            <th style="border-bottom: 2px solid #dee2e6;">Conclusion</th>
                        </tr>
                    </thead>
                    <tbody>
            """]
            failed_rules = []
            
            def log_rule(rule_obj, status, msg="", field_key=None, skipped=False):
                if skipped:
                    icon = "fa-exclamation-triangle"
                    color = "#fd7e14" # orange
                    bg = "#fff3cd"
                    status_text = "SKIPPED"
                else:
                    icon = "fa-check-circle" if status else "fa-times-circle"
                    color = "#28a745" if status else "#dc3545"
                    bg = "#d4edda" if status else "#f8d7da"
                    status_text = "PASSED" if status else "FAILED"

                rules_html.append(f"""
                    <tr style="vertical-align: middle;">
                        <td style="text-align: center; padding: 10px;">
                            <i class="fa {icon}" style="color: {color}; font-size: 1.2rem;" title="{status_text}"></i>
                        </td>
                        <td style="padding: 10px;"><b>{rule_obj.name}</b><br/><small class="text-muted">{rule_obj.rule_code}</small></td>
                        <td style="padding: 10px; font-size: 0.9rem;">{rule_obj.description}</td>
                        <td style="padding: 10px; color: {color}; font-weight: 500;">{msg}</td>
                    </tr>
                """)
                if not status and not skipped:
                    failed_rules.append({'field': field_key or 'id', 'msg': f"{rule_obj.rule_code}: {msg}"})

            # Parse AI Validations from JSON
            ai_data = {}
            if rec.extraction_result_id.extracted_data:
                try:
                    full_json = json.loads(rec.extraction_result_id.extracted_data)
                    vals = full_json.get('validations', [])
                    if isinstance(vals, list):
                        ai_data = {v.get('rule'): v for v in vals if v.get('rule')}
                    else:
                        ai_data = vals
                except:
                    pass

            for rule in active_rules:
                code = rule.rule_code
                
                # AI Rules
                if rule.eval_type == 'ai':
                    ai_res = ai_data.get(code)
                    if ai_res:
                        log_rule(rule, ai_res.get('status', False), ai_res.get('msg', 'Reasoning captured'))
                    else:
                        log_rule(rule, False, "Evidence not found by AI", skipped=True)
                    continue

                # Python Rules
                if code == 'RULE_1': # Unique Invoice
                    dup = self.env['account.move'].search([('ref', '=', rec.invoice_number), ('partner_id', '=', rec.partner_id.id)], limit=1)
                    dup_proc = self.env['purple_ai.invoice_processor'].search([('invoice_number', '=', rec.invoice_number), ('partner_id', '=', rec.partner_id.id), ('id', '!=', rec.id)], limit=1)
                    log_rule(rule, not (dup or dup_proc), "Invoice already exists in Odoo" if (dup or dup_proc) else "Unique reference confirmed", "invoice_number")
                
                elif code == 'RULE_2': # GST Format
                    gstin = (rec.supplier_gstin or '').strip()
                    is_ok = len(gstin) == 15
                    log_rule(rule, is_ok, "GSTIN format invalid (must be 15 chars)" if not is_ok else "Format verified", "supplier_gstin")

                elif code == 'RULE_3': # Tax Math
                    calc_gst = round(rec.untaxed_amount * (rec.gst_rate / 100.0), 2)
                    is_ok = abs(rec.gst_amount - calc_gst) < 1.0
                    log_rule(rule, is_ok, f"Calculated GST ({calc_gst}) differs from Extracted ({rec.gst_amount})" if not is_ok else "Mathematical accuracy verified", "gst_amount")

                elif code == 'RULE_4': # PO Amount
                    POModel = self.env.get('purchase.order')
                    po = POModel.search([('name', '=', rec.po_number)], limit=1) if (POModel and rec.po_number) else False
                    if po:
                        log_rule(rule, rec.total_amount <= po.amount_total, f"Invoice amount exceeds PO limit ({po.amount_total})" if rec.total_amount > po.amount_total else "Within PO threshold", "total_amount")
                    else:
                        msg = "PO Number not found in Odoo database" if POModel else "Purchase module not installed"
                        log_rule(rule, False, msg, skipped=True)

                elif code == 'RULE_6': # PO Date
                    POModel = self.env.get('purchase.order')
                    po = POModel.search([('name', '=', rec.po_number)], limit=1) if (POModel and rec.po_number) else False
                    if po and rec.invoice_date:
                        log_rule(rule, po.date_order.date() <= rec.invoice_date, f"Invoice date is prior to PO date ({po.date_order.date()})" if po.date_order.date() > rec.invoice_date else "Date sequence valid", "invoice_date")
                    else:
                        msg = "Date information or PO missing" if POModel else "Purchase module not installed"
                        log_rule(rule, False, msg, skipped=True)

                elif code == 'RULE_5': # Bank Match
                    if rec.partner_id and rec.vendor_bank_account:
                        bank = self.env['res.partner.bank'].search([('partner_id', '=', rec.partner_id.id), ('acc_number', 'ilike', rec.vendor_bank_account.replace(' ', ''))], limit=1)
                        log_rule(rule, bool(bank), "Extracted bank account not found in Vendor Master" if not bank else "Bank account verified", "vendor_bank_account")
                    else:
                        log_rule(rule, False, "Vendor or Bank info missing for cross-check", skipped=True)


                elif code == 'RULE_7': # TDS Accuracy
                    tds_mapping = {'Professional Services': 10.0, 'Technical Services': 10.0, 'Rent': 10.0, 'Contractor': 2.0}
                    expected = tds_mapping.get(rec.service_type, 10.0)
                    log_rule(rule, rec.tds_rate == expected, f"TDS rate {rec.tds_rate}% does not match expected {expected}% for {rec.service_type}" if rec.tds_rate != expected else "TDS Compliance verified", "service_type")

            rules_html.append("</tbody></table>")
            rec.validation_log = "".join(rules_html)
            rec.is_validated = True
            rec.state = 'failed' if failed_rules else 'draft'
            return failed_rules

    def action_export_validation_excel(self):
        """Exports the validation summary as a CSV (Excel compatible) file."""
        self.ensure_one()
        output = io.StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_NONNUMERIC)
        
        # Header
        writer.writerow(['Audit Report for Invoice', self.invoice_number or 'New'])
        writer.writerow(['Vendor', self.partner_id.name or self.vendor_name or 'Unknown'])
        writer.writerow([])
        writer.writerow(['Rule Code', 'Rule Name', 'Status', 'Observation / Description'])

        # Data rows (we parse the HTML or rerun logic, but simpler to parse rule results)
        template = self.client_id.extraction_master_id if self.client_id else False
        # Since we don't store rule-by-rule status in DB yet, we just provide the basic summary or rerun logic
        # For simplicity and accuracy, let's just export the main fields and the state
        writer.writerow(['OVERALL_STATUS', 'Policy Compliance', self.state.upper(), 'Total invoice validation result'])
        writer.writerow(['INV_NUM', 'Invoice Number', 'DONE', self.invoice_number])
        writer.writerow(['INV_DATE', 'Invoice Date', 'DONE', self.invoice_date])
        writer.writerow(['AMT_UNT', 'Untaxed Amount', 'DONE', self.untaxed_amount])
        writer.writerow(['AMT_TAX', 'Tax Amount', 'DONE', self.gst_amount])
        writer.writerow(['AMT_TOT', 'Total Amount', 'DONE', self.total_amount])

        data = output.getvalue()
        output.close()
        
        attachment = self.env['ir.attachment'].create({
            'name': f"validation_report_{self.invoice_number}.csv",
            'type': 'binary',
            'datas': base64.b64encode(data.encode('utf-8')),
            'res_model': 'purple_ai.invoice_processor',
            'res_id': self.id,
            'mimetype': 'text/csv'
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'new',
        }

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

    def update_extracted_evidence(self, key, new_value):
        """Saves manual corrections and logs audit trail to chatter."""
        self.ensure_one()
        try:
            data = json.loads(self.extraction_result_id.extracted_data or '{}')
            old_item = data.get(key)
            old_value = ""
            
            if isinstance(old_item, dict):
                old_value = old_item.get('value', '')
                data[key]['value'] = new_value
            else:
                old_value = str(old_item) if old_item is not None else ""
                data[key] = new_value
            
            # Update source record
            self.extraction_result_id.extracted_data = json.dumps(data)
            
            # Post Audit Log to Chatter
            field_label = key.replace('_', ' ').title()
            msg = Markup(
                "<strong>Audit Correction</strong>: %s updated.<br/>"
                "• Old: <span style='color: #dc3545; font-weight: bold;'>%s</span><br/>"
                "• New: <span style='color: #28a745; font-weight: bold;'>%s</span>"
            ) % (field_label, old_value or 'Empty', new_value)
            
            self.message_post(body=msg)
            
            # Re-run mathematical validations if amount changed
            if 'amount' in key or 'total' in key:
                self.action_validate()
                
            return True
        except Exception as e:
            _logger.error("Evidence update failed: %s", str(e))
            return False

    def update_evidence_comment(self, key, comment):
        """Saves a comment for a specific extracted field."""
        self.ensure_one()
        try:
            data = json.loads(self.extraction_result_id.extracted_data or '{}')
            if key not in data:
                return False
            
            if not isinstance(data[key], dict):
                # Convert primitive to dict if needed to support comment
                data[key] = {'value': data[key], 'page_number': 1}
            
            data[key]['comment'] = comment
            self.extraction_result_id.extracted_data = json.dumps(data)
            
            field_label = key.replace('_', ' ').title()
            self.message_post(body=Markup(
                "<strong>Note Added</strong>: [%s] <br/><i>%s</i>"
            ) % (field_label, comment))
            return True
        except Exception as e:
            _logger.error("Comment update failed: %s", str(e))
            return False

    def action_push_to_tally(self):
        """Pushes the current invoice details to Tally via XML API."""
        self.ensure_one()
        from ..services.tally_service import push_voucher_to_tally
        
        if not self.partner_id and not self.vendor_name:
            raise UserError(_("No Vendor info found to push."))
        
        # Prepare invoice data for Tally
        inv_date = self.invoice_date or fields.Date.today()
        tally_date_str = inv_date.strftime('%Y%m%d')
        
        # Determine voucher type in Tally (usually "Purchase" for vendor bills)
        voucher_type = 'Purchase' 
        party_ledger = self.partner_id.name or self.vendor_name
        
        # Narration like the user example: "Online Adv_Inv INVNO_Facebook for Business..."
        narration = f"AI PUSH: Inv {self.invoice_number or '?'}"
        if self.po_number:
            narration += f" | PO: {self.po_number}"
        if self.service_type:
            narration += f" | {self.service_type}"

        # Ledger Entry logic: 
        # Follow user's image exactly: Cr Party, Dr Expense, Dr Tax, Cr TDS
        # ISDEEMEDPOSITIVE=No means Credit | Yes means Debit
        
        ledger_entries = [
             # Party (Credit Total)
             {'name': party_ledger, 'amount': self.total_amount, 'is_debit': False},
             
             # Expense (Debit Untaxed)
             {'name': self.expense_account_id.name if self.expense_account_id else 'Purchase Accounts', 
              'amount': self.untaxed_amount, 'is_debit': True},
        ]
        
        # Taxes (Debit Input GST)
        if self.gst_amount:
            ledger_entries.append({'name': self.gst_account_id.name if self.gst_account_id else 'Input GST', 
                                   'amount': self.gst_amount, 'is_debit': True})
        
        # TDS (Credit Deduction)
        if self.tds_amount:
            ledger_entries.append({'name': self.tds_account_id.name if self.tds_account_id else 'TDS on Contract', 
                                   'amount': self.tds_amount, 'is_debit': False})

        tally_data = {
            'voucher_type': voucher_type,
            'date': tally_date_str,
            'number': self.invoice_number or 'INV-AI',
            'reference': self.invoice_number,
            'party_name': party_ledger,
            'amount': self.total_amount,
            'narration': narration,
            'ledger_entries': ledger_entries,
        }
        
        res = push_voucher_to_tally(self.env, tally_data)
        
        if res['status'] == 'success':
            self.message_post(body=f"✅ <b>Successfully pushed to Tally</b>.<br/>VOUCHER: {tally_data['number']}<br/>PARTY: {party_ledger}")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('✅ Pushed to Tally'),
                    'message': _('Invoice pushed successfully as %s voucher') % voucher_type,
                    'type': 'success',
                    'sticky': False,
                },
            }
        else:
            raise UserError(_("Tally Push Failed: %s") % res['message'])

    def action_export_tally_excel(self):
        """Exports selected invoices in a colorful Tally-compatible Excel format."""
        if not self:
            return
            
        try:
            import xlsxwriter
        except ImportError:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {'title': _('Error'), 'message': _('XlsxWriter not installed.'), 'type': 'danger'}
            }

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output)
        sheet = workbook.add_worksheet('Tally Bulk Export')

        # Define Formats
        fmt_red = workbook.add_format({'bg_color': '#FF0000', 'font_color': '#FFFFFF', 'bold': True, 'border': 1, 'align': 'center'})
        fmt_yellow = workbook.add_format({'bg_color': '#FFFF00', 'font_color': '#000000', 'bold': True, 'border': 1, 'align': 'center'})
        fmt_lyellow = workbook.add_format({'bg_color': '#FFFFA0', 'font_color': '#000000', 'bold': True, 'border': 1, 'align': 'center'})
        fmt_green = workbook.add_format({'bg_color': '#90EE90', 'border': 1, 'align': 'right', 'num_format': '#,##0.00'})
        fmt_std = workbook.add_format({'border': 1})
        fmt_amt_red = workbook.add_format({'bg_color': '#FF0000', 'font_color': '#FFFFFF', 'border': 1, 'align': 'right', 'num_format': '#,##0.00'})
        fmt_amt_yellow = workbook.add_format({'bg_color': '#FFFF00', 'font_color': '#000000', 'border': 1, 'align': 'right', 'num_format': '#,##0.00'})
        fmt_date = workbook.add_format({'num_format': 'dd/mmm/yyyy', 'border': 1})

        # --- Write Headers ---
        sheet.write(0, 0, 'UNIQUE ID', fmt_red)
        sheet.merge_range(0, 1, 0, 4, 'VOUCHER DETAILS', fmt_yellow)
        sheet.merge_range(0, 5, 0, 7, 'PARTY DETAILS', fmt_yellow)
        sheet.merge_range(0, 8, 0, 14, 'ITEM DETAILS', fmt_yellow)
        sheet.merge_range(0, 15, 0, 17, 'IGST', fmt_yellow)
        sheet.merge_range(0, 18, 0, 20, 'CGST', fmt_yellow)
        sheet.merge_range(0, 21, 0, 23, 'SGST', fmt_yellow)
        sheet.merge_range(0, 24, 0, 26, 'TDS', fmt_yellow)
        sheet.write(0, 27, 'LEDGER', fmt_red)
        sheet.write(0, 28, 'NARRATION', fmt_yellow)

        cols = ['', 'VCH TYPE', 'VCH DATE', 'Invoice NO', 'Invoice Date', 'PARTY', 'GSTIN', 'State', 'ITEM NAME', 'HSN CODE', 'UNITS', 'QTY', 'RATE', 'Disc (%)', 'AMOUNT', '%', 'Ledger Name', 'Amt', '%', 'Ledger Name', 'Amt', '%', 'Ledger Name', 'Amt', '%', 'Ledger Name', 'Amt', 'SALES/PURCHASE LEDGER', '']
        for idx, col in enumerate(cols):
            sheet.write(1, idx, col, fmt_lyellow)

        # --- Write Data Rows ---
        row = 2
        for rec in self:
            inv_date = rec.invoice_date or fields.Date.today()
            vch_date = fields.Date.today()
            state_map = {'06': 'Haryana', '07': 'Delhi', '09': 'Uttar Pradesh', '27': 'Maharashtra', '33': 'Tamil Nadu'}
            gstin_prefix = (rec.supplier_gstin or '')[:2]
            state = state_map.get(gstin_prefix, 'Unknown')
            narration = f"AI PUSH: Inv {rec.invoice_number or '?'} | PO: {rec.po_number or 'N/A'}"

            sheet.write(row, 0, row - 1, fmt_std)
            sheet.write(row, 1, 'Purchase Noida', fmt_std)
            sheet.write_datetime(row, 2, vch_date, fmt_date)
            sheet.write(row, 3, rec.invoice_number or 'INV-AI', fmt_std)
            sheet.write_datetime(row, 4, inv_date, fmt_date)
            sheet.write(row, 5, rec.partner_id.name or rec.vendor_name or 'Unknown', fmt_std)
            sheet.write(row, 6, rec.supplier_gstin or '', fmt_green)
            sheet.write(row, 7, state, fmt_green)
            
            sheet.write(row, 8, '', fmt_std)
            sheet.write(row, 9, '998365', fmt_green)
            sheet.write(row, 10, '', fmt_std)
            sheet.write(row, 11, '', fmt_std)
            sheet.write(row, 12, '', fmt_std)
            sheet.write(row, 13, '', fmt_std)
            sheet.write(row, 14, rec.untaxed_amount, fmt_amt_red)

            sheet.write(row, 15, rec.gst_rate if rec.gst_amount else '', fmt_std)
            sheet.write(row, 16, rec.gst_account_id.name if rec.gst_account_id else 'Input IGST', fmt_std)
            sheet.write(row, 17, rec.gst_amount, fmt_green)

            for i in range(18, 24): sheet.write(row, i, '', fmt_std)

            sheet.write(row, 24, rec.tds_rate if rec.tds_amount else '', fmt_std)
            sheet.write(row, 25, rec.tds_account_id.name if rec.tds_account_id else 'TDS on Contract', fmt_std)
            sheet.write(row, 26, rec.tds_amount, fmt_amt_yellow)

            sheet.write(row, 27, rec.expense_account_id.name if rec.expense_account_id else 'Marketing Cost', fmt_red)
            sheet.write(row, 28, narration, fmt_std)
            row += 1

        workbook.close()
        data = base64.b64encode(output.getvalue())
        
        attachment = self.env['ir.attachment'].create({
            'name': f"tally_bulk_export_{fields.Date.today()}.xlsx",
            'type': 'binary',
            'datas': data,
            'res_model': 'purple_ai.invoice_processor',
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        })
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'new',
        }
