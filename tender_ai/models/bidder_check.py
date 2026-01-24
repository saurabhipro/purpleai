# -*- coding: utf-8 -*-

import base64
import io
import re
import logging
from collections import OrderedDict

from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)

# Small in-process cache to avoid repeatedly extracting text from the same PDFs
# Key: (attachment_id, write_date_str) -> list[str] page_texts
_PDF_TEXT_CACHE: "OrderedDict[tuple, list]" = OrderedDict()
_PDF_TEXT_CACHE_MAX = 32


class TenderBidderCheck(models.Model):
    _name = 'tende_ai.bidder_check'
    _description = 'Bidder Eligibility Check'
    _rec_name = 'name'
    _order = 'create_date desc'

    name = fields.Char(string="Name", compute="_compute_name", store=True, readonly=True)

    job_id = fields.Many2one('tende_ai.job', string='Job', required=True, ondelete='cascade', readonly=True, index=True)
    tender_id = fields.Many2one('tende_ai.tender', string='Tender', readonly=True, related='job_id.tender_id', store=True)
    bidder_id = fields.Many2one('tende_ai.bidder', string='Bidder', required=True, ondelete='cascade', readonly=True, index=True)

    overall_result = fields.Selection([
        ('pass', 'Pass'),
        ('fail', 'Fail'),
        ('unknown', 'Unknown'),
    ], string='Overall Result', default='unknown', readonly=True, index=True)

    total_criteria = fields.Integer(string='Total Criteria', readonly=True)
    passed_criteria = fields.Integer(string='Passed', readonly=True)
    failed_criteria = fields.Integer(string='Failed', readonly=True)
    unknown_criteria = fields.Integer(string='Unknown', readonly=True)

    duration_seconds = fields.Float(string='Duration (sec)', readonly=True)
    processed_on = fields.Datetime(string='Processed On', readonly=True)
    error_message = fields.Text(string='Error', readonly=True)

    line_ids = fields.One2many('tende_ai.bidder_check_line', 'check_id', string='Criteria Results', readonly=True)
    client_query_ids = fields.One2many('tende_ai.client_query', 'check_id', string='Client Queries')

    @api.depends("job_id", "bidder_id", "overall_result")
    def _compute_name(self):
        for rec in self:
            job = rec.job_id.name if rec.job_id else ""
            bidder = rec.bidder_id.vendor_company_name if rec.bidder_id else ""
            res = rec.overall_result or ""
            parts = [p for p in [job, bidder, res] if p]
            rec.name = " / ".join(parts) if parts else _("Eligibility Check")

    def action_export_issues_excel(self):
        """Export all criteria lines where Result is Fail/Unknown."""
        self.ensure_one()
        try:
            import xlsxwriter  # type: ignore
        except Exception:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Excel export"),
                    "message": _("xlsxwriter is not installed on the server."),
                    "type": "warning",
                    "sticky": False,
                },
            }

        lines = self.line_ids.filtered(lambda l: l.result in ("fail", "unknown"))
        out = io.BytesIO()
        wb = xlsxwriter.Workbook(out, {"in_memory": True})
        ws = wb.add_worksheet("Issues")

        fmt_head = wb.add_format({"bold": True, "bg_color": "#7b4b3a", "font_color": "#ffffff", "border": 1})
        fmt_wrap = wb.add_format({"text_wrap": True, "valign": "top", "border": 1})
        fmt_fail = wb.add_format({"text_wrap": True, "valign": "top", "border": 1, "bg_color": "#fde2e7"})
        fmt_unk = wb.add_format({"text_wrap": True, "valign": "top", "border": 1, "bg_color": "#fff3cd"})

        headers = [
            "Sl No",
            "Result",
            "Criteria",
            "Supporting Document",
            "Missing Documents",
            "Reason",
            "Evidence",
            "Proof Link",
            "Proof Page",
            "Proof Excerpt",
        ]
        for c, h in enumerate(headers):
            ws.write(0, c, h, fmt_head)

        ws.set_column(0, 0, 8)
        ws.set_column(1, 1, 10)
        ws.set_column(2, 2, 55)
        ws.set_column(3, 3, 35)
        ws.set_column(4, 4, 25)
        ws.set_column(5, 6, 35)
        ws.set_column(7, 7, 30)
        ws.set_column(8, 8, 10)
        ws.set_column(9, 9, 45)

        r = 1
        for line in lines:
            fmt = fmt_fail if line.result == "fail" else fmt_unk if line.result == "unknown" else fmt_wrap
            ws.write(r, 0, line.sl_no or "", fmt)
            ws.write(r, 1, dict(line._fields["result"].selection).get(line.result, line.result), fmt)
            ws.write(r, 2, line.criteria or "", fmt)
            ws.write(r, 3, line.supporting_document or "", fmt)
            ws.write(r, 4, line.missing_documents or "", fmt)
            ws.write(r, 5, line.reason or "", fmt)
            ws.write(r, 6, line.evidence or "", fmt)
            ws.write(r, 7, line.proof_url or "", fmt)
            ws.write_number(r, 8, line.proof_page or 0, fmt)
            ws.write(r, 9, line.proof_excerpt or "", fmt)
            r += 1

        wb.close()
        data = out.getvalue()
        out.close()

        filename = f"{(self.job_id.name or 'JOB')}_{(self.bidder_id.vendor_company_name or 'BIDDER')}_issues.xlsx"
        Attachment = self.env["ir.attachment"].sudo()
        att = Attachment.create({
            "name": filename,
            "type": "binary",
            "mimetype": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "datas": base64.b64encode(data),
            "res_model": "tende_ai.bidder_check",
            "res_id": self.id,
        })

        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/ir.attachment/{att.id}/datas/{filename}?download=true",
            "target": "self",
        }

    def action_add_client_query(self):
        """Open a modal to create a client query even when this check form is read-only."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Add Client Query"),
            "res_model": "tende_ai.client_query",
            "view_mode": "form",
            "target": "new",
            "context": {"default_check_id": self.id},
        }


class TenderBidderCheckLine(models.Model):
    _name = 'tende_ai.bidder_check_line'
    _description = 'Bidder Eligibility Check Line'
    _order = 'sl_no, id'

    check_id = fields.Many2one('tende_ai.bidder_check', string='Check', required=True, ondelete='cascade', readonly=True, index=True)
    job_id = fields.Many2one('tende_ai.job', string='Job', related='check_id.job_id', store=True, readonly=True, index=True)
    bidder_id = fields.Many2one('tende_ai.bidder', string='Bidder', related='check_id.bidder_id', store=True, readonly=True, index=True)
    criteria_id = fields.Many2one('tende_ai.eligibility_criteria', string='Criteria', readonly=True)

    sl_no = fields.Char(string='Sl. No.', readonly=True)
    criteria = fields.Text(string='Criteria', readonly=True)
    supporting_document = fields.Text(string='Supporting Document', readonly=True)

    result = fields.Selection([
        ('pass', 'Pass'),
        ('fail', 'Fail'),
        ('unknown', 'Unknown'),
    ], string='Result', default='unknown', readonly=True, index=True)

    reason = fields.Text(string='Reason', readonly=True)
    evidence = fields.Text(string='Evidence', readonly=True)
    missing_documents = fields.Text(string='Missing Documents', readonly=True)

    # --------
    # Proof UI
    # --------
    proof_attachment_id = fields.Many2one(
        "ir.attachment",
        string="Proof Document",
        compute="_compute_proof",
        store=False,
        readonly=True,
    )
    proof_page = fields.Integer(string="Proof Page", compute="_compute_proof", store=False, readonly=True)
    proof_excerpt = fields.Text(string="Proof Excerpt", compute="_compute_proof", store=False, readonly=True)
    proof_url = fields.Char(string="Proof Link", compute="_compute_proof", store=False, readonly=True)

    @staticmethod
    def _tokenize(text: str):
        """
        Extract tokens likely to appear in PDF text/filenames:
        - long numbers (PO/Ref)
        - longer words (>=4 chars)
        """
        t = (text or "").lower()
        nums = re.findall(r"\b\d{4,}\b", t)
        words = re.findall(r"\b[a-z][a-z0-9_-]{3,}\b", t)
        stop = {
            "the", "and", "with", "from", "that", "this", "have", "has", "for", "are", "was", "were",
            "bidder", "document", "documents", "attachment", "attachments", "proof", "evidence",
            "criteria", "supporting", "required", "format", "prescribed", "order", "agreement",
        }
        words = [w for w in words if w not in stop]
        out = []
        out.extend(nums)
        out.extend([w for w in words if w not in out])
        return out[:20]

    def _pick_best_attachment(self, bidder, hint_text: str):
        """
        Best-effort pick of a relevant PDF attachment for a bidder based on hint text.
        Respects attachment access rules (no sudo).
        """
        if not bidder:
            return False
        atts = bidder.attachment_ids
        if not atts:
            return False
        tokens = self._tokenize(hint_text)
        if not tokens:
            return atts[:1]
        scored = []
        for a in atts:
            name = (a.name or "").lower()
            score = 0
            for tok in tokens:
                if tok and tok in name:
                    score += 3 if tok.isdigit() else 1
            if score:
                scored.append((score, a.id))
        if not scored:
            return atts[:1]
        scored.sort(key=lambda x: (-x[0], x[1]))
        return atts.browse(scored[0][1])

    @classmethod
    def _cache_get_pdf_texts(cls, attachment):
        key = (attachment.id, str(attachment.write_date or attachment.create_date or ""))
        if key in _PDF_TEXT_CACHE:
            _PDF_TEXT_CACHE.move_to_end(key)
            return _PDF_TEXT_CACHE[key]

        # cap cache
        while len(_PDF_TEXT_CACHE) >= _PDF_TEXT_CACHE_MAX:
            _PDF_TEXT_CACHE.popitem(last=False)

        # extract
        try:
            from PyPDF2 import PdfReader  # type: ignore
        except Exception as e:
            raise RuntimeError("PyPDF2 is required for proof page detection") from e

        raw = attachment.datas
        if not raw:
            _PDF_TEXT_CACHE[key] = []
            return []
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        data = base64.b64decode(raw)
        reader = PdfReader(io.BytesIO(data))
        texts = []
        # Hard cap to avoid heavy CPU on huge PDFs
        max_pages = min(len(reader.pages), 60)
        for i in range(max_pages):
            try:
                txt = reader.pages[i].extract_text() or ""
            except Exception:
                txt = ""
            txt = re.sub(r"\s+", " ", txt).strip()
            texts.append(txt)

        _PDF_TEXT_CACHE[key] = texts
        return texts

    def _find_best_page_and_excerpt(self, attachment, hint_text: str):
        tokens = self._tokenize(hint_text)
        if not tokens:
            return (0, "")
        try:
            pages = self._cache_get_pdf_texts(attachment)
        except Exception as e:
            _logger.warning("Tender AI proof: failed to extract pdf text for attachment %s: %s", attachment.id, str(e))
            return (0, "")
        if not pages:
            return (0, "")

        best = (0, -1, -1)  # (score, page_idx, match_pos)
        best_tok = None
        for idx, txt in enumerate(pages):
            low = (txt or "").lower()
            if not low:
                continue
            score = 0
            match_pos = -1
            for tok in tokens:
                p = low.find(tok)
                if p >= 0:
                    score += 3 if tok.isdigit() else 1
                    if match_pos < 0 or p < match_pos:
                        match_pos = p
                        best_tok = tok
            if score > best[0]:
                best = (score, idx, match_pos)
        if best[0] <= 0 or best[1] < 0:
            return (0, "")

        page_num = best[1] + 1  # 1-index for UI
        txt = pages[best[1]] or ""
        low = txt.lower()
        pos = low.find(best_tok) if best_tok else -1
        if pos < 0:
            pos = max(0, best[2])
        start = max(0, pos - 220)
        end = min(len(txt), pos + 260)
        excerpt = txt[start:end].strip()
        if start > 0:
            excerpt = "… " + excerpt
        if end < len(txt):
            excerpt = excerpt + " …"
        return (page_num, excerpt)

    @api.depends("result", "bidder_id", "evidence", "reason", "missing_documents")
    def _compute_proof(self):
        for rec in self:
            rec.proof_attachment_id = False
            rec.proof_page = 0
            rec.proof_excerpt = False
            rec.proof_url = False

            # Only show proof for failures (noise otherwise)
            if rec.result != "fail" or not rec.bidder_id:
                continue

            hint = " ".join([
                rec.evidence or "",
                rec.reason or "",
                rec.missing_documents or "",
            ]).strip()
            if not hint:
                continue

            att = rec._pick_best_attachment(rec.bidder_id, hint)
            if not att:
                continue

            page, excerpt = rec._find_best_page_and_excerpt(att, hint)
            rec.proof_attachment_id = att
            rec.proof_page = int(page or 0)
            rec.proof_excerpt = excerpt or ""
            if page:
                # Serve highlighted view (no new PDF stored). Viewer will also accept #page.
                rec.proof_url = f"/tender_ai/proof/{rec.id}#page={int(page)}"
            else:
                rec.proof_url = f"/tender_ai/proof/{rec.id}"


