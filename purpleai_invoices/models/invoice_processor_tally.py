# -*- coding: utf-8 -*-
import io
import base64
from odoo import models, fields, _, api
from odoo.exceptions import UserError

class InvoiceProcessor(models.Model):
    _inherit = 'purple_ai.invoice_processor'

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
