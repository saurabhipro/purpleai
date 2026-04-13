# -*- coding: utf-8 -*-
import os
import shutil
import logging
import re
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)
DEFAULT_ROOT_PATH = '/home/odoo18'

class ClientMaster(models.Model):
    _name = 'purple_ai.client'
    _description = 'Client Folder Mapping'
    _order = 'name'

    name = fields.Char(string='Client Name', required=True)
    folder_path = fields.Char(string='Watch Folder Path', help="Automatically generated path on the server")
    extraction_master_id = fields.Many2one('purple_ai.extraction_master', string='Extraction Template', required=True)
    company_id = fields.Many2one('res.company', string='Linked Company', readonly=True)
    manager_user_id = fields.Many2one('res.users', string='Client Manager')
    active = fields.Boolean(default=True)
    
    # Progress Tracking
    scan_status = fields.Selection([
        ('idle', 'Idle'),
        ('scanning', 'Scanning'),
    ], default='idle', string='Scan Status')
    scan_count = fields.Integer(string='Processed Index', default=0)
    scan_total = fields.Integer(string='Total Files', default=0)
    scan_current_file = fields.Char(string='Processing File')
    scan_progress = fields.Float(string='Progress Percentage', compute='_compute_scan_progress')
    
    last_scan = fields.Datetime(string='Last Scanned At', readonly=True)
    processed_count = fields.Integer(string='Processed Files', compute='_compute_counts')
    extraction_result_ids = fields.One2many('purple_ai.extraction_result', 'client_id', string='Extraction Results')

    # Computed HTML listing of files in the watch folder
    folder_files_html = fields.Html(string='Folder Contents', compute='_compute_folder_files', sanitize=False)

    def _compute_counts(self):
        for rec in self:
            rec.processed_count = self.env['purple_ai.extraction_result'].search_count([('client_id', '=', rec.id)])

    def _compute_folder_files(self):
        """List all PDF/image files inside the client's watch folder."""
        import datetime
        SUPPORTED_EXT = {'.pdf', '.jpg', '.jpeg', '.png', '.webp', '.tiff'}
        for rec in self:
            path = (rec.folder_path or '').strip()
            if not path or not os.path.isdir(path):
                rec.folder_files_html = (
                    '<div class="alert alert-warning py-2">'
                    '<i class="fa fa-folder-open me-2"></i>'
                    'Watch folder not found or not configured.</div>'
                )
                continue

            try:
                entries = []
                for fname in sorted(os.listdir(path)):
                    ext = os.path.splitext(fname)[1].lower()
                    if ext not in SUPPORTED_EXT:
                        continue
                    fpath = os.path.join(path, fname)
                    stat = os.stat(fpath)
                    size_kb = round(stat.st_size / 1024, 1)
                    mtime = datetime.datetime.fromtimestamp(stat.st_mtime).strftime('%d %b %Y %H:%M')
                    entries.append((fname, size_kb, mtime, ext))

                if not entries:
                    rec.folder_files_html = (
                        '<div class="alert alert-info py-2">'
                        '<i class="fa fa-inbox me-2"></i>'
                        'No PDF or image files found in the watch folder.</div>'
                    )
                    continue

                icon_map = {'.pdf': 'fa-file-pdf-o text-danger', '.jpg': 'fa-file-image-o text-info',
                            '.jpeg': 'fa-file-image-o text-info', '.png': 'fa-file-image-o text-info',
                            '.webp': 'fa-file-image-o text-info', '.tiff': 'fa-file-image-o text-info'}

                rows = ''.join(
                    f'<tr>'
                    f'<td><i class="fa {icon_map.get(ext, "fa-file-o")} me-2"></i>{fname}</td>'
                    f'<td class="text-muted text-end">{size_kb} KB</td>'
                    f'<td class="text-muted text-end">{mtime}</td>'
                    f'</tr>'
                    for fname, size_kb, mtime, ext in entries
                )
                rec.folder_files_html = f'''
                    <div class="mb-2 text-muted" style="font-size:0.85rem;">
                        <i class="fa fa-folder-open me-1"></i>
                        <strong>{len(entries)}</strong> file(s) &nbsp;·&nbsp;
                        <code style="font-size:0.8rem;">{path}</code>
                    </div>
                    <table class="table table-sm table-hover table-bordered mb-0" style="font-size:0.9rem;">
                        <thead class="table-light">
                            <tr>
                                <th><i class="fa fa-file me-1"></i> File Name</th>
                                <th class="text-end">Size</th>
                                <th class="text-end">Last Modified</th>
                            </tr>
                        </thead>
                        <tbody>{rows}</tbody>
                    </table>'''
            except Exception as e:
                rec.folder_files_html = f'<div class="alert alert-danger py-2">Error reading folder: {e}</div>'

    @api.depends('scan_count', 'scan_total')
    def _compute_scan_progress(self):
        for rec in self:
            if rec.scan_total > 0:
                rec.scan_progress = min(100.0, (rec.scan_count / rec.scan_total) * 100.0)
            else:
                rec.scan_progress = 0.0

    @api.model_create_multi
    def create(self, vals_list):
        new_company_ids = []
        for vals in vals_list:
            if 'folder_path' not in vals or not vals['folder_path']:
                vals['folder_path'] = self._generate_auto_path(vals)

            if 'company_id' not in vals:
                new_company = self.env['res.company'].sudo().create({
                    'name': vals.get('name', 'New Client Company'),
                    'currency_id': (self.env.ref('base.INR').id if self.env.ref('base.INR', raise_if_not_found=False) else self.env.company.currency_id.id)
                })
                vals['company_id'] = new_company.id
                new_company_ids.append(new_company.id)
                self.env.user.sudo().write({'company_ids': [(4, new_company.id)]})

        if new_company_ids:
            current_allowed = list(self.env.context.get('allowed_company_ids', self.env.user.company_ids.ids))
            patched_allowed = list(set(current_allowed + new_company_ids))
            self = self.with_context(allowed_company_ids=patched_allowed)

        res = super(ClientMaster, self).create(vals_list)
        for rec in res:
            rec._ensure_folder_exists()
        return res

    def write(self, vals):
        root_path = self._get_root_path()
        if 'name' in vals or 'extraction_master_id' in vals:
            for rec in self:
                if root_path and (not rec.folder_path or rec.folder_path.startswith(root_path)):
                    vals['folder_path'] = self._generate_auto_path({
                        'name': vals.get('name', rec.name),
                        'extraction_master_id': vals.get('extraction_master_id', rec.extraction_master_id.id)
                    })
        res = super().write(vals)
        self._ensure_folder_exists()
        return res

    def _generate_auto_path(self, vals):
        """Generates a sanitized path: {root_path}/{template}/{client}"""
        root_path = self._get_root_path()
             
        def slugify(text):
            if not text: return "unknown"
            return re.sub(r'[^a-z0-9]+', '_', str(text).lower()).strip('_')
        client_name = slugify(vals.get('name', 'default'))
        template_id = vals.get('extraction_master_id')
        template_name = "invoices"
        if template_id:
            template = self.env['purple_ai.extraction_master'].browse(template_id)
            if template.exists(): template_name = slugify(template.name)
        return os.path.join(root_path, template_name, client_name)

    def _get_root_path(self):
        """Return normalized root path with install-time fallback."""
        configured = self.env['ir.config_parameter'].sudo().get_param('purple_ai.root_path')
        root_path = (configured or DEFAULT_ROOT_PATH or '').strip()
        if not root_path:
            raise UserError(_("Please define the 'Root Folder Path' in Purple AI settings first."))
        return os.path.normpath(root_path)

    def _ensure_folder_exists(self):
        """Creates the directory structure on the server with 777 permissions."""
        root_path = self._get_root_path()
        if not root_path:
            return
            
        for rec in self:
            if rec.folder_path:
                path = rec.folder_path.strip()
                try:
                    if not os.path.exists(path):
                        os.makedirs(path, mode=0o777, exist_ok=True)
                    os.chmod(path, 0o777)
                    parent = os.path.dirname(path)
                    if parent != root_path and parent.startswith(root_path):
                        os.chmod(parent, 0o777)
                except Exception as e:
                    _logger.error("Failed to create/chmod folder %s: %s", path, str(e))

    @api.constrains('folder_path')
    def _check_folder_path(self):
        for rec in self:
            if not rec.folder_path: continue
            path = rec.folder_path.strip()
            if not os.path.exists(path): rec._ensure_folder_exists()
            if not os.path.exists(path):
                raise UserError(_("The folder path '%s' is not accessible.") % path)
            if not os.path.isdir(path):
                raise UserError(_("The path '%s' is not a directory.") % path)

    def action_view_results(self):
        self.ensure_one()
        return {
            'name': _('Extraction Results'),
            'type': 'ir.actions.act_window',
            'res_model': 'purple_ai.extraction_result',
            'view_mode': 'list,form',
            'domain': [('client_id', '=', self.id)],
            'context': {'default_client_id': self.id},
        }

    def action_generate_demo_invoices(self):
        """Generate sample PDF invoices directly into this client's watch folder."""
        self.ensure_one()
        self._ensure_folder_exists()
        folder = (self.folder_path or '').strip()
        if not folder:
            raise UserError(_("Watch folder path is not configured for this client."))

        def _esc(txt):
            return (txt or "").replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

        def _make_pdf(path, invoice):
            lines = [
                "TAX INVOICE",
                "",
                f"Invoice No: {invoice['inv_no']}    Date: {invoice['date']}    Due: {invoice['due_date']}",
                f"PO Number: {invoice['po']}    Place of Supply: {invoice['place_of_supply']}",
                "",
                "Vendor (Supplier):",
                f"{invoice['vendor']}",
                f"{invoice['vendor_addr']}",
                f"GSTIN: {invoice['vendor_gstin']}    PAN: {invoice['vendor_pan']}",
                "",
                "Bill To:",
                f"{invoice['bill_to']}",
                f"{invoice['bill_addr']}",
                f"GSTIN: {invoice['bill_gstin']}",
                "",
                "Line Items",
                "---------------------------------------------------------------------",
                "Description                               Qty   Rate      Amount",
                "---------------------------------------------------------------------",
            ]
            for item in invoice["items"]:
                desc = item["desc"][:38]
                qty = item["qty"]
                rate = item["rate"]
                amount = item["amount"]
                lines.append(f"{desc:<38} {qty:>3} {rate:>8} {amount:>11}")
            lines.extend([
                "---------------------------------------------------------------------",
                f"Taxable Value: {invoice['taxable_value']}",
                f"CGST @9%: {invoice['cgst']}",
                f"SGST @9%: {invoice['sgst']}",
                f"IGST: {invoice['igst']}",
                f"Total Invoice Value: {invoice['total']}",
                f"TDS: {invoice['tds']}    Net Payable: {invoice['net_payable']}",
                "",
                f"Payment Terms: {invoice['payment_terms']}",
                f"Bank Details: {invoice['bank_details']}",
                f"Service Period: {invoice['service_period']}",
                f"Remarks: {invoice['remarks']}",
                "",
                "Authorized Signatory",
            ])

            y = 800
            body_parts = ["BT", "/F1 10 Tf"]
            for line in lines:
                body_parts.append(f"1 0 0 1 40 {y} Tm ({_esc(line)}) Tj")
                y -= 14
                if y < 40:
                    break
            body_parts.append("ET")
            body = "\n".join(body_parts) + "\n"
            pdf = (
                "%PDF-1.1\n"
                "1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
                "2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
                "3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R "
                "/Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n"
                f"4 0 obj\n<< /Length {len(body.encode('utf-8'))} >>\nstream\n{body}endstream\nendobj\n"
                "5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"
                "xref\n0 6\n"
                "0000000000 65535 f \n"
                "0000000009 00000 n \n"
                "0000000058 00000 n \n"
                "0000000115 00000 n \n"
                "0000000241 00000 n \n"
                "0000000461 00000 n \n"
                "trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n531\n%%EOF\n"
            )
            with open(path, 'wb') as f:
                f.write(pdf.encode('utf-8'))

        samples = [
            {
                "file": "INV-APPROVAL-001.pdf",
                "inv_no": "INV-APPROVAL-001",
                "date": "2026-04-01",
                "due_date": "2026-04-15",
                "po": "PO-1001",
                "place_of_supply": "Karnataka",
                "vendor": "Acme Services Pvt Ltd",
                "vendor_addr": "12 Residency Road, Bengaluru",
                "vendor_gstin": "29ABCDE1234F1Z5",
                "vendor_pan": "ABCDE1234F",
                "bill_to": "GT Bharat Technologies Pvt Ltd",
                "bill_addr": "Whitefield, Bengaluru",
                "bill_gstin": "29AAACG9999K1Z7",
                "items": [
                    {"desc": "Consulting Services - Monthly Retainer", "qty": 1, "rate": "10000.00", "amount": "10000.00"},
                ],
                "taxable_value": "10000.00",
                "cgst": "900.00",
                "sgst": "900.00",
                "igst": "0.00",
                "total": "11800.00",
                "tds": "1000.00",
                "net_payable": "10800.00",
                "payment_terms": "Net 15 days",
                "bank_details": "HDFC 50200012345678 IFSC HDFC0001234",
                "service_period": "01-Apr-2026 to 30-Apr-2026",
                "remarks": "For approval workflow demo",
            },
            {
                "file": "INV-READY-002.pdf",
                "inv_no": "INV-READY-002",
                "date": "2026-04-02",
                "due_date": "2026-04-12",
                "po": "PO-1002",
                "place_of_supply": "Karnataka",
                "vendor": "Northwind Traders",
                "vendor_addr": "44 Industrial Area, Peenya, Bengaluru",
                "vendor_gstin": "29AACCN5678M1Z2",
                "vendor_pan": "AACCN5678M",
                "bill_to": "GT Bharat Technologies Pvt Ltd",
                "bill_addr": "Whitefield, Bengaluru",
                "bill_gstin": "29AAACG9999K1Z7",
                "items": [
                    {"desc": "Hardware Procurement - Network Equipment", "qty": 2, "rate": "12000.00", "amount": "24000.00"},
                ],
                "taxable_value": "24000.00",
                "cgst": "2160.00",
                "sgst": "2160.00",
                "igst": "0.00",
                "total": "28320.00",
                "tds": "0.00",
                "net_payable": "28320.00",
                "payment_terms": "Immediate",
                "bank_details": "ICICI 001234567890 IFSC ICIC0000456",
                "service_period": "NA",
                "remarks": "Ready for tally demo",
            },
            {
                "file": "INV-FAILED-003.pdf",
                "inv_no": "INV-FAILED-003",
                "date": "2026-04-03",
                "due_date": "2026-04-20",
                "po": "PO-1003",
                "place_of_supply": "Maharashtra",
                "vendor": "Beta Enterprises",
                "vendor_addr": "Andheri East, Mumbai",
                "vendor_gstin": "27AABCB2222P1ZZ",
                "vendor_pan": "AABCB2222P",
                "bill_to": "GT Bharat Technologies Pvt Ltd",
                "bill_addr": "Whitefield, Bengaluru",
                "bill_gstin": "29AAACG9999K1Z7",
                "items": [
                    {"desc": "Professional Services - Design and Review", "qty": 1, "rate": "18500.00", "amount": "18500.00"},
                ],
                "taxable_value": "18500.00",
                "cgst": "0.00",
                "sgst": "0.00",
                "igst": "1500.00",
                "total": "20000.00",
                "tds": "1850.00",
                "net_payable": "18150.00",
                "payment_terms": "Net 30 days",
                "bank_details": "SBI 334455667788 IFSC SBIN0007788",
                "service_period": "03-Apr-2026",
                "remarks": "Intentional tax mismatch for failed validation",
            },
            {
                "file": "INV-FOREIGN-004.pdf",
                "inv_no": "INV-FOREIGN-004",
                "date": "2026-04-04",
                "due_date": "2026-04-14",
                "po": "PO-1004",
                "place_of_supply": "Outside India",
                "vendor": "Global Cloud Inc",
                "vendor_addr": "120 Market St, San Francisco, USA",
                "vendor_gstin": "NA",
                "vendor_pan": "NA",
                "bill_to": "GT Bharat Technologies Pvt Ltd",
                "bill_addr": "Whitefield, Bengaluru",
                "bill_gstin": "29AAACG9999K1Z7",
                "items": [
                    {"desc": "Cloud Subscription - Enterprise Plan", "qty": 1, "rate": "600.00 USD", "amount": "600.00 USD"},
                ],
                "taxable_value": "600.00 USD",
                "cgst": "0.00",
                "sgst": "0.00",
                "igst": "0.00",
                "total": "600.00 USD",
                "tds": "0.00",
                "net_payable": "600.00 USD",
                "payment_terms": "Advance",
                "bank_details": "Wire Transfer SWIFT GCLDUS33",
                "service_period": "Apr-2026",
                "remarks": "Foreign invoice hold scenario",
            },
            {
                "file": "INV-REJECT-005.pdf",
                "inv_no": "INV-REJECT-005",
                "date": "2026-04-05",
                "due_date": "2026-04-18",
                "po": "PO-1005",
                "place_of_supply": "Karnataka",
                "vendor": "Zenith Supplies",
                "vendor_addr": "Mysore Road, Bengaluru",
                "vendor_gstin": "29AAACZ7654R1Z0",
                "vendor_pan": "AAACZ7654R",
                "bill_to": "GT Bharat Technologies Pvt Ltd",
                "bill_addr": "Whitefield, Bengaluru",
                "bill_gstin": "29AAACG9999K1Z7",
                "items": [
                    {"desc": "Office Consumables - Bulk Supply", "qty": 1, "rate": "9000.00", "amount": "9000.00"},
                ],
                "taxable_value": "9000.00",
                "cgst": "810.00",
                "sgst": "810.00",
                "igst": "0.00",
                "total": "10620.00",
                "tds": "0.00",
                "net_payable": "10620.00",
                "payment_terms": "Net 10 days",
                "bank_details": "Axis 918273645001 IFSC UTIB0001789",
                "service_period": "05-Apr-2026",
                "remarks": "Contains HSN mismatch for manager rejection demo",
            },
        ]
        created = 0
        for invoice in samples:
            fpath = os.path.join(folder, invoice["file"])
            _make_pdf(fpath, invoice)
            created += 1

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Demo invoices created'),
                'message': _('Created %d sample PDF invoices in %s') % (created, folder),
                'type': 'success',
                'sticky': False,
            },
        }

    def unlink(self):
        """Delete client row + client folder + linked company."""
        to_cleanup = []
        for rec in self:
            to_cleanup.append({
                'folder_path': (rec.folder_path or '').strip(),
                'company_id': rec.company_id.id if rec.company_id else False,
            })

        res = super().unlink()

        root_path = self._get_root_path()
        root_real = os.path.realpath(root_path)

        # 1) Delete client watch folder from OS
        for item in to_cleanup:
            folder_path = item.get('folder_path')
            if not folder_path:
                continue
            try:
                folder_real = os.path.realpath(folder_path)
                # Safety: only remove folders inside configured root path.
                if os.path.commonpath([root_real, folder_real]) != root_real:
                    _logger.warning(
                        "Skipped deleting folder outside root path: %s (root=%s)",
                        folder_real,
                        root_real,
                    )
                    continue
                if os.path.isdir(folder_real):
                    shutil.rmtree(folder_real, ignore_errors=False)
            except Exception as e:
                _logger.error("Failed to delete client folder %s: %s", folder_path, str(e))

        # 2) Delete linked company if no other client uses it
        company_ids = {item.get('company_id') for item in to_cleanup if item.get('company_id')}
        if company_ids:
            Client = self.env['purple_ai.client'].sudo()
            Company = self.env['res.company'].sudo()
            for company in Company.browse(list(company_ids)).exists():
                try:
                    if Client.search_count([('company_id', '=', company.id)]) == 0:
                        company.unlink()
                except Exception as e:
                    # If deletion is blocked by other dependencies, archive it.
                    _logger.warning(
                        "Could not delete company %s (%s). Archiving instead. Reason: %s",
                        company.display_name,
                        company.id,
                        str(e),
                    )
                    try:
                        company.write({'active': False})
                    except Exception as sub_e:
                        _logger.error(
                            "Could not archive company %s (%s): %s",
                            company.display_name,
                            company.id,
                            str(sub_e),
                        )

        return res
