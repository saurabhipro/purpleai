# -*- coding: utf-8 -*-
import json
import io
import csv
import base64
from odoo import models, api, fields, _
from markupsafe import Markup

class InvoiceProcessor(models.Model):
    _inherit = 'purple_ai.invoice_processor'

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
                if code == 'RULE_1':  # Unique Invoice
                    Move = self.env.get('account.move')
                    if not Move:
                        log_rule(
                            rule,
                            False,
                            _("Accounting app is not installed — cannot check existing journal entries"),
                            skipped=True,
                        )
                    else:
                        dup = Move.search(
                            [
                                ('ref', '=', rec.invoice_number),
                                ('partner_id', '=', rec.partner_id.id),
                            ],
                            limit=1,
                        )
                        dup_proc = self.env['purple_ai.invoice_processor'].search(
                            [
                                ('invoice_number', '=', rec.invoice_number),
                                ('partner_id', '=', rec.partner_id.id),
                                ('id', '!=', rec.id),
                            ],
                            limit=1,
                        )
                        log_rule(
                            rule,
                            not (dup or dup_proc),
                            _("Invoice already exists in Odoo")
                            if (dup or dup_proc)
                            else _("Unique reference confirmed"),
                            "invoice_number",
                        )
                
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
        # Since we don't store rule-by-rule status in DB yet, we just provide the basic summary or rerun logic
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
            from logging import getLogger
            getLogger(__name__).error("Evidence update failed: %s", str(e))
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
            from logging import getLogger
            getLogger(__name__).error("Comment update failed: %s", str(e))
            return False
