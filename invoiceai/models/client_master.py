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
                    'currency_id': (self.env.ref('base.INR').id if self.env.ref('base.INR', raise_if_not_found=False) else self.env.company.currency_id.id),
                    'backend_theme_level': 'global_level'  # Default value for backend_theme_level
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
                    # Ensure a 'processed' subfolder exists for moved/archived files
                    try:
                        proc_dir = os.path.join(path, 'processed')
                        if not os.path.exists(proc_dir):
                            os.makedirs(proc_dir, mode=0o777, exist_ok=True)
                        os.chmod(proc_dir, 0o777)
                    except Exception as e:
                        _logger.debug("Could not create processed subfolder for %s: %s", path, e)
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

        today = fields.Date.context_today(self)
        fy_start = today.year if today.month >= 4 else today.year - 1
        fy_tag = f"{str(fy_start)[-2:]}{str(fy_start + 1)[-2:]}"
        prefix = f"INV-{fy_tag}-"
        generator_folder = os.path.join(folder, "invoice_generator")
        os.makedirs(generator_folder, exist_ok=True)

        existing_max = 0
        seq_pattern = re.compile(rf"^{re.escape(prefix)}(\d{{3}})")
        for fname in os.listdir(generator_folder):
            if not fname.lower().endswith(".pdf"):
                continue
            m = seq_pattern.match(fname)
            if m:
                existing_max = max(existing_max, int(m.group(1)))

        base = {
            "bill_to": "GT Bharat Technologies Pvt Ltd",
            "bill_addr": "Whitefield, Bengaluru",
            "bill_gstin": "29AAACG9999K1Z7",
        }
        scenarios = [
            {"suffix": "domestic_services", "vendor": "Acme Services Pvt Ltd", "vendor_addr": "Residency Road, Bengaluru", "vendor_gstin": "29ABCDE1234F1Z5", "vendor_pan": "ABCDE1234F", "place_of_supply": "Karnataka", "po": "PO-2001", "item_desc": "Consulting services retainer", "rate": "10000.00", "taxable": "10000.00", "cgst": "900.00", "sgst": "900.00", "igst": "0.00", "tds": "1000.00", "remarks": "Domestic service with TDS"},
            {"suffix": "domestic_goods", "vendor": "Northwind Traders", "vendor_addr": "Peenya, Bengaluru", "vendor_gstin": "29AACCN5678M1Z2", "vendor_pan": "AACCN5678M", "place_of_supply": "Karnataka", "po": "PO-2002", "item_desc": "Network switch procurement", "rate": "24000.00", "taxable": "24000.00", "cgst": "2160.00", "sgst": "2160.00", "igst": "0.00", "tds": "0.00", "remarks": "Domestic goods"},
            {"suffix": "interstate_igst", "vendor": "Beta Enterprises", "vendor_addr": "Andheri East, Mumbai", "vendor_gstin": "27AABCB2222P1ZZ", "vendor_pan": "AABCB2222P", "place_of_supply": "Maharashtra", "po": "PO-2003", "item_desc": "Professional design services", "rate": "18500.00", "taxable": "18500.00", "cgst": "0.00", "sgst": "0.00", "igst": "3330.00", "tds": "1850.00", "remarks": "Inter-state IGST with TDS"},
            {"suffix": "foreign_invoice", "vendor": "Global Cloud Inc", "vendor_addr": "San Francisco, USA", "vendor_gstin": "NA", "vendor_pan": "NA", "place_of_supply": "Outside India", "po": "PO-2004", "item_desc": "Cloud subscription annual plan", "rate": "600.00 USD", "taxable": "600.00 USD", "cgst": "0.00", "sgst": "0.00", "igst": "0.00", "tds": "0.00", "remarks": "Foreign currency invoice"},
            {"suffix": "proforma_invoice", "vendor": "Zenith Supplies", "vendor_addr": "Mysore Road, Bengaluru", "vendor_gstin": "29AAACZ7654R1Z0", "vendor_pan": "AAACZ7654R", "place_of_supply": "Karnataka", "po": "PO-2005", "item_desc": "Advance billing for annual support", "rate": "15000.00", "taxable": "15000.00", "cgst": "1350.00", "sgst": "1350.00", "igst": "0.00", "tds": "0.00", "remarks": "PROFORMA INVOICE - Advance request"},
            {"suffix": "prepaid_expense", "vendor": "Orbit Tech Services", "vendor_addr": "HSR Layout, Bengaluru", "vendor_gstin": "29AAACO1234K1Z2", "vendor_pan": "AAACO1234K", "place_of_supply": "Karnataka", "po": "PO-2006", "item_desc": "AMC for 12 months prepaid", "rate": "36000.00", "taxable": "36000.00", "cgst": "3240.00", "sgst": "3240.00", "igst": "0.00", "tds": "3600.00", "remarks": "Prepaid service for next period"},
            {"suffix": "capex_asset", "vendor": "Prime Machinery Pvt Ltd", "vendor_addr": "Pune", "vendor_gstin": "27AACCP7788M1Z9", "vendor_pan": "AACCP7788M", "place_of_supply": "Maharashtra", "po": "PO-2007", "item_desc": "High-end workstation asset", "rate": "125000.00", "taxable": "125000.00", "cgst": "0.00", "sgst": "0.00", "igst": "22500.00", "tds": "0.00", "remarks": "Capital asset procurement"},
            {"suffix": "rcm_case", "vendor": "Unregistered Transporter", "vendor_addr": "Tumkur, Karnataka", "vendor_gstin": "NA", "vendor_pan": "AVUPT1122Q", "place_of_supply": "Karnataka", "po": "PO-2008", "item_desc": "Freight inward charges", "rate": "8000.00", "taxable": "8000.00", "cgst": "0.00", "sgst": "0.00", "igst": "0.00", "tds": "0.00", "remarks": "RCM applicable freight service"},
        ]

        samples = []
        for idx, sc in enumerate(scenarios, start=1):
            seq_no = existing_max + idx
            inv_no = f"{prefix}{seq_no:03d}"
            taxable_val = sc["taxable"]
            total_val = (
                f"{float(sc['taxable']) + float(sc['cgst']) + float(sc['sgst']) + float(sc['igst']):.2f}"
                if "USD" not in taxable_val
                else taxable_val
            )
            net_payable = (
                f"{float(total_val) - float(sc['tds']):.2f}"
                if "USD" not in total_val
                else total_val
            )
            samples.append({
                "file": f"{inv_no}_{sc['suffix']}.pdf",
                "inv_no": inv_no,
                "date": str(today),
                "due_date": str(today),
                "po": sc["po"],
                "place_of_supply": sc["place_of_supply"],
                "vendor": sc["vendor"],
                "vendor_addr": sc["vendor_addr"],
                "vendor_gstin": sc["vendor_gstin"],
                "vendor_pan": sc["vendor_pan"],
                "bill_to": base["bill_to"],
                "bill_addr": base["bill_addr"],
                "bill_gstin": base["bill_gstin"],
                "items": [{"desc": sc["item_desc"], "qty": 1, "rate": sc["rate"], "amount": sc["taxable"]}],
                "taxable_value": taxable_val,
                "cgst": sc["cgst"],
                "sgst": sc["sgst"],
                "igst": sc["igst"],
                "total": total_val,
                "tds": sc["tds"],
                "net_payable": net_payable,
                "payment_terms": "Net 15 days",
                "bank_details": "HDFC 50200012345678 IFSC HDFC0001234",
                "service_period": str(today),
                "remarks": sc["remarks"],
            })
        created = 0
        for invoice in samples:
            fpath = os.path.join(generator_folder, invoice["file"])
            _make_pdf(fpath, invoice)
            created += 1

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Demo invoices created'),
                'message': _('Created %d sample PDF invoices in %s') % (created, generator_folder),
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
