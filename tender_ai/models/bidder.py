# -*- coding: utf-8 -*-

import base64
import os
import re

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class Bidder(models.Model):
    _name = 'tende_ai.bidder'
    _description = 'Bidder/Company Information'
    _rec_name = 'vendor_company_name'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'vendor_company_name'

    job_id = fields.Many2one('tende_ai.job', string='Job', required=True, ondelete='cascade', readonly=True)
    
    # Company Information
    vendor_company_name = fields.Char(string='Company Name', required=True, tracking=True, index=True)
    company_address = fields.Text(string='Company Address', tracking=True)
    email_id = fields.Char(string='Email ID', tracking=True)
    contact_person = fields.Char(string='Contact Person', tracking=True)
    contact_no = fields.Char(string='Contact Number', tracking=True)
    
    # Registration Information
    pan = fields.Char(string='PAN', tracking=True)
    gstin = fields.Char(string='GSTIN', tracking=True)
    pan_validation_status = fields.Selection(
        [('unknown', 'Unknown'), ('valid', 'Valid'), ('invalid', 'Invalid')],
        string="PAN Status",
        default="unknown",
        tracking=True,
        readonly=True,
    )
    gstin_validation_status = fields.Selection(
        [('unknown', 'Unknown'), ('valid', 'Valid'), ('invalid', 'Invalid')],
        string="GSTIN Status",
        default="unknown",
        tracking=True,
        readonly=True,
    )
    pan_validated_on = fields.Datetime(string="PAN Checked On", tracking=True, readonly=True)
    gstin_validated_on = fields.Datetime(string="GSTIN Checked On", tracking=True, readonly=True)
    place_of_registration = fields.Char(string='Place of Registration', tracking=True)
    offer_validity_days = fields.Char(string='Offer Validity (Days)', tracking=True)
    
    # Related Records
    payments = fields.One2many('tende_ai.payment', 'bidder_id', string='Payments')
    work_experiences = fields.One2many('tende_ai.work_experience', 'bidder_id', string='Work Experiences')
    check_ids = fields.One2many('tende_ai.bidder_check', 'bidder_id', string='Eligibility Checks', readonly=True)

    # Attachments linked via chatter / res_model+res_id
    attachment_ids = fields.Many2many(
        'ir.attachment',
        compute='_compute_attachment_ids',
        string='Attachments',
        readonly=True,
        store=False,
    )

    @api.depends('message_ids')
    def _compute_attachment_ids(self):
        # Do NOT sudo here; we want to respect attachment access rules in UI.
        Attachment = self.env['ir.attachment']
        for rec in self:
            if not rec.id:
                rec.attachment_ids = False
                continue
            rec.attachment_ids = Attachment.search([
                ('res_model', '=', 'tende_ai.bidder'),
                ('res_id', '=', rec.id),
            ])

    def action_open_attachments(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Attachments'),
            'res_model': 'ir.attachment',
            'view_mode': 'list,form',
            'domain': [('res_model', '=', 'tende_ai.bidder'), ('res_id', '=', self.id)],
            'context': {
                'default_res_model': 'tende_ai.bidder',
                'default_res_id': self.id,
            },
            'target': 'current',
        }

    def action_generate_attachments(self):
        """Create one ir.attachment per extracted PDF for this bidder (downloadable)."""
        self.ensure_one()
        if not self.job_id or not self.job_id.extract_dir:
            raise ValidationError(_("No extracted folder found for this bidder's job. Please reprocess the ZIP."))

        extract_dir = self.job_id.extract_dir
        if not os.path.isdir(extract_dir):
            raise ValidationError(_("Extract directory not found on server. Please reprocess the ZIP."))

        # Find company folder in extract_dir (best effort, case-insensitive)
        wanted = (self.vendor_company_name or '').strip().lower()
        company_dir = None
        for name in os.listdir(extract_dir):
            p = os.path.join(extract_dir, name)
            if os.path.isdir(p) and name.strip().lower() == wanted:
                company_dir = p
                break
        if not company_dir:
            raise ValidationError(_("Company folder not found in extracted ZIP for this bidder."))

        pdf_paths = []
        for root, _, files in os.walk(company_dir):
            for fn in files:
                if fn.lower().endswith('.pdf') and fn.lower() != 'tender.pdf':
                    pdf_paths.append(os.path.join(root, fn))

        if not pdf_paths:
            raise ValidationError(_("No PDF files found for this bidder in the extracted folder."))

        Attachment = self.env['ir.attachment'].sudo()
        # Use relative path for deterministic names
        names = []
        for p in pdf_paths:
            try:
                rel = os.path.relpath(p, extract_dir)
            except Exception:
                rel = os.path.basename(p)
            names.append(rel)

        existing = set(Attachment.search([
            ('res_model', '=', 'tende_ai.bidder'),
            ('res_id', '=', self.id),
            ('name', 'in', names),
        ]).mapped('name'))

        to_create = []
        for p, name in zip(pdf_paths, names):
            if name in existing:
                continue
            try:
                with open(p, 'rb') as f:
                    content = f.read()
            except Exception:
                continue
            if not content:
                continue
            to_create.append({
                'name': name,
                'res_model': 'tende_ai.bidder',
                'res_id': self.id,
                'type': 'binary',
                'mimetype': 'application/pdf',
                'datas': base64.b64encode(content),
            })

        if to_create:
            Attachment.create(to_create)

        return {'type': 'ir.actions.client', 'tag': 'reload'}

    @staticmethod
    def _is_valid_pan(value: str) -> bool:
        v = (value or "").strip().upper()
        return bool(re.fullmatch(r"[A-Z]{5}[0-9]{4}[A-Z]", v))

    @staticmethod
    def _is_valid_gstin(value: str) -> bool:
        v = (value or "").strip().upper()
        # 15 chars: 2 digits + PAN + 1 entity + Z + checksum
        return bool(re.fullmatch(r"\d{2}[A-Z]{5}[0-9]{4}[A-Z][A-Z0-9]Z[A-Z0-9]", v))

    def _notify(self, title: str, message: str, notif_type: str = "info"):
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": title,
                "message": message,
                "type": notif_type,  # info/success/warning/danger
                "sticky": False,
            },
        }

    def action_validate_pan(self):
        self.ensure_one()
        if not self.pan:
            self.write({"pan_validation_status": "unknown", "pan_validated_on": fields.Datetime.now()})
            return self._notify(_("PAN Validation"), _("No PAN found to validate."), "warning")
        ok = self._is_valid_pan(self.pan)
        self.write({
            "pan": (self.pan or "").strip().upper(),
            "pan_validation_status": "valid" if ok else "invalid",
            "pan_validated_on": fields.Datetime.now(),
        })
        return self._notify(_("PAN Validation"), _("PAN format looks valid.") if ok else _("PAN format looks invalid."), "success" if ok else "danger")

    def action_validate_gstin(self):
        self.ensure_one()
        if not self.gstin:
            self.write({"gstin_validation_status": "unknown", "gstin_validated_on": fields.Datetime.now()})
            return self._notify(_("GSTIN Validation"), _("No GSTIN found to validate."), "warning")
        ok = self._is_valid_gstin(self.gstin)
        self.write({
            "gstin": (self.gstin or "").strip().upper(),
            "gstin_validation_status": "valid" if ok else "invalid",
            "gstin_validated_on": fields.Datetime.now(),
        })
        return self._notify(_("GSTIN Validation"), _("GSTIN format looks valid.") if ok else _("GSTIN format looks invalid."), "success" if ok else "danger")

