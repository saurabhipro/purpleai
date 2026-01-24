# -*- coding: utf-8 -*-

import base64
import io
import re

from odoo import http
from odoo.http import request


class TenderAIProofController(http.Controller):
    @http.route("/tender_ai/proof/<int:line_id>", type="http", auth="user", methods=["GET"], csrf=False)
    def proof_highlight_pdf(self, line_id: int, **kwargs):
        """
        Returns an on-the-fly highlighted PDF for the bidder check line proof.
        Does NOT create a new attachment; modifies bytes in memory only.
        """
        Line = request.env["tende_ai.bidder_check_line"]
        line = Line.browse(int(line_id))
        if not line.exists():
            return request.not_found()

        # access control
        line.check_access_rights("read")
        line.check_access_rule("read")

        # Only meaningful for failed lines
        if line.result != "fail" or not line.bidder_id:
            return request.not_found()

        # Ensure proof fields are computed (may be store=False)
        att = line.proof_attachment_id
        if not att:
            return request.not_found()

        # Access control for attachment
        att.check_access_rights("read")
        att.check_access_rule("read")

        raw = att.datas
        if not raw:
            return request.not_found()
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        pdf_bytes = base64.b64decode(raw)

        hint = " ".join([line.evidence or "", line.reason or "", line.missing_documents or ""]).strip()

        # tokenization similar to bidder_check.py (keep local to avoid import cycles)
        t = (hint or "").lower()
        nums = re.findall(r"\b\d{4,}\b", t)
        words = re.findall(r"\b[a-z][a-z0-9_-]{3,}\b", t)
        stop = {
            "the", "and", "with", "from", "that", "this", "have", "has", "for", "are", "was", "were",
            "bidder", "document", "documents", "attachment", "attachments", "proof", "evidence",
            "criteria", "supporting", "required", "format", "prescribed", "order", "agreement",
        }
        words = [w for w in words if w not in stop]
        tokens = []
        tokens.extend(nums)
        tokens.extend([w for w in words if w not in tokens])
        tokens = tokens[:12]

        try:
            import fitz  # type: ignore
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            # Prefer computed page
            page_idx = int(line.proof_page or 0) - 1
            if page_idx < 0 or page_idx >= doc.page_count:
                page_idx = 0
            page = doc.load_page(page_idx)

            # Try to highlight matches on that page; if no matches, do a small scan across pages
            highlights = 0
            def _apply_on_page(p):
                nonlocal highlights
                for tok in tokens:
                    if not tok:
                        continue
                    try:
                        rects = p.search_for(tok)
                    except Exception:
                        rects = []
                    for r in rects[:8]:
                        try:
                            p.add_highlight_annot(r)
                            highlights += 1
                        except Exception:
                            pass

            _apply_on_page(page)
            if highlights == 0 and tokens:
                # scan up to 10 pages to find first token hit
                max_scan = min(doc.page_count, 10)
                found_idx = None
                for i in range(max_scan):
                    p = doc.load_page(i)
                    try:
                        if any(p.search_for(tok) for tok in tokens[:3] if tok):
                            found_idx = i
                            break
                    except Exception:
                        continue
                if found_idx is not None:
                    page = doc.load_page(found_idx)
                    _apply_on_page(page)

            out = doc.tobytes(garbage=4, deflate=True)
        except Exception:
            # If highlighting fails, fallback to original bytes
            out = pdf_bytes

        filename = (att.name or f"proof_{line_id}.pdf").replace('"', "")
        headers = [
            ("Content-Type", "application/pdf"),
            ("Content-Disposition", f'inline; filename="{filename}"'),
        ]
        return request.make_response(out, headers=headers)


