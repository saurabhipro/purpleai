# -*- coding: utf-8 -*-

import re

from markupsafe import Markup
from odoo import models, _
from odoo.tools import html_escape


class MailBot(models.AbstractModel):
    """
    Extends the built-in System/OdooBot (addon `mail_bot`) to answer Tender AI questions
    inside the same chat widget, using Gemini behind the scenes.
    """

    _inherit = "mail.bot"

    @staticmethod
    def _html_table(title, headers, rows, max_rows=50, add_index=True):
        safe_title = html_escape(title or "")
        safe_headers = [html_escape(h or "") for h in (headers or [])]
        safe_rows = rows or []

        # Limit rows for UI performance
        safe_rows = safe_rows[: max_rows or 50]

        if add_index:
            safe_headers = [html_escape(_("Sl No"))] + safe_headers

        thead = "".join(
            [f"<th style='border:1px solid #ddd; padding:6px; background:#f7f7f7; text-align:left;'>{h}</th>" for h in safe_headers]
        )
        tbody_rows = []
        for i, r in enumerate(safe_rows, start=1):
            cells = []
            if add_index:
                cells.append(f"<td style='border:1px solid #ddd; padding:6px; vertical-align:top;'>{i}</td>")
            for c in (r or []):
                # Allow callers to pass Markup for hyperlinks etc.
                if isinstance(c, Markup):
                    cell_html = str(c)
                else:
                    cell_html = html_escape(str(c or ""))
                cells.append(f"<td style='border:1px solid #ddd; padding:6px; vertical-align:top;'>{cell_html}</td>")
            tbody_rows.append("<tr>" + "".join(cells) + "</tr>")
        tbody = "".join(tbody_rows) or "<tr><td style='border:1px solid #ddd; padding:6px;' colspan='%d'>No data</td></tr>" % max(1, len(safe_headers))

        return Markup(
            "<div>"
            f"<div style='font-weight:700; margin:4px 0 8px 0;'>{safe_title}</div>"
            "<div style='overflow:auto; max-height:340px;'>"
            "<table style='width:100%; border-collapse:collapse; font-size:13px;'>"
            f"<thead><tr>{thead}</tr></thead>"
            f"<tbody>{tbody}</tbody>"
            "</table>"
            "</div>"
            "</div>"
        )

    @staticmethod
    def _record_link(model: str, rec_id: int, label: str):
        label = label or ""
        return Markup(
            f"<a href='/web#id={int(rec_id)}&model={html_escape(model)}&view_type=form'>"
            f"{html_escape(label)}</a>"
        )

    @staticmethod
    def _download_attachment_link(att_id: int, label: str):
        label = label or ""
        return Markup(
            f"<a href='/web/content/{int(att_id)}?download=true'>"
            f"{html_escape(label)}</a>"
        )

    @staticmethod
    def _extract_after_for(text: str) -> str:
        m = re.search(r"\bfor\s+(.+)$", text or "", flags=re.IGNORECASE)
        return (m.group(1).strip() if m else (text or "").strip())

    @staticmethod
    def _tokenize_for_attachment_match(text: str):
        """
        Extracts tokens likely to appear in filenames:
        - long numbers (e.g. PO/Ref IDs)
        - longer words (>=4 chars)
        """
        t = (text or "").lower()
        nums = re.findall(r"\b\d{4,}\b", t)
        words = re.findall(r"\b[a-z][a-z0-9_-]{3,}\b", t)
        stop = {
            "the", "and", "with", "from", "that", "this", "have", "has", "for", "are", "was", "were",
            "bidder", "document", "documents", "attachment", "attachments", "proof", "evidence",
            "criteria", "supporting", "required", "format", "prescribed",
        }
        words = [w for w in words if w not in stop and not w.startswith("tender_")]
        # prefer numeric tokens first (often unique)
        out = []
        out.extend(nums)
        out.extend([w for w in words if w not in out])
        return out[:20]

    def _match_attachments(self, bidder, text: str, limit: int = 8):
        """
        Best-effort matching of bidder attachments based on evidence/missing-doc text.
        """
        if not bidder:
            return []
        atts = bidder.attachment_ids
        if not atts:
            return []
        tokens = self._tokenize_for_attachment_match(text)
        if not tokens:
            return atts[:limit]
        scored = []
        for a in atts:
            name = (a.name or "").lower()
            score = 0
            for tok in tokens:
                if tok and tok in name:
                    score += 3 if tok.isdigit() else 1
            if score:
                scored.append((score, a))
        scored.sort(key=lambda x: (-x[0], x[1].id))
        return [a for _, a in scored[:limit]] or atts[:limit]

    def _get_answer(self, record, body, values, command=False):
        text = (body or "").strip()
        low = text.lower().strip()

        # Natural language shortcuts (so it works like ChatGPT without needing /commands),
        # even when OdooBot is in onboarding "ping me" mode.
        # We only trigger when message is clearly about tenders.
        # Trigger for any of the Tender AI tabs/models, so user can ask like:
        # "bidder names", "qualification criteria", "payments", "work experience", etc.
        if re.search(r"\b(tender|bidder|bidders|eligibility|criteria|qualification|qualifications|payment|payments|work experience|evaluation|attachment|attachments|document|documents|pdf|file|files)\b", low):
            # Count intent (handle typos like "who many")
            if re.search(r"\b(how|who)\s+many\b", low) or re.search(r"\bcount\b", low):
                cnt = self.env["tende_ai.job"].search_count([])
                return Markup("<p>%s</p>") % html_escape(_("You currently have access to %s tender jobs.") % cnt)

            # Proof / failed evidence: show likely documents for each failed criterion (best-effort)
            if re.search(r"\b(fail|failed)\b", low) and re.search(r"\b(proof|evidence|document|documents|attachment|attachments)\b", low):
                job = self.env["tende_ai.job"].sudo().search(
                    [("state", "in", ("completed", "processing", "extracted"))],
                    order="create_date desc",
                    limit=1,
                )
                if not job:
                    return Markup("<p>%s</p>") % html_escape(_("No tender jobs found."))

                query = self._extract_after_for(text)
                bidder = None
                ql = query.lower()
                for b in (job.bidders or []):
                    nm = (b.vendor_company_name or "").strip()
                    if nm and nm.lower() in ql:
                        bidder = b
                        break
                if not bidder and query:
                    bidder = self.env["tende_ai.bidder"].sudo().search(
                        [("job_id", "=", job.id), ("vendor_company_name", "ilike", query)],
                        limit=1,
                    )
                if not bidder:
                    return Markup("<p>%s</p>") % html_escape(
                        _("Please specify bidder/company name, e.g. “failed proof for APOLLO INFOWAYS”. (Latest job: %s)") % (job.name or "")
                    )

                Line = self.env["tende_ai.bidder_check_line"].sudo()
                lines = Line.search(
                    [("job_id", "=", job.id), ("bidder_id", "=", bidder.id), ("result", "=", "fail")],
                    order="sl_no, id",
                    limit=20,
                )
                if not lines:
                    return Markup("<p>%s</p>") % html_escape(
                        _("No failed eligibility lines found for %s on job %s.") % (bidder.vendor_company_name or "", job.name or "")
                    )

                rows = []
                for ln in lines:
                    evidence = (ln.evidence or ln.reason or ln.missing_documents or "").strip()
                    excerpt = evidence[:140] + ("…" if len(evidence) > 140 else "")
                    matched = self._match_attachments(bidder, evidence, limit=6)
                    links = []
                    for a in matched:
                        links.append(self._download_attachment_link(a.id, a.name or _("Download")))
                    docs_cell = Markup("<br/>").join(links) if links else Markup(html_escape(_("No matching attachment found.")))
                    rows.append([ln.sl_no or "", (ln.criteria or "")[:120], excerpt, docs_cell])

                title = _("Failed criteria proof documents") + f" — {bidder.vendor_company_name or ''} ({job.name or ''})"
                return self._html_table(title, ["Sl No (Criteria)", "Criteria", "Evidence excerpt", "Likely documents"], rows, max_rows=20, add_index=True)

            # Bidder attachments / documents quick answer
            if re.search(r"\b(attachment|attachments|document|documents|pdf|file|files)\b", low):
                job = self.env["tende_ai.job"].sudo().search(
                    [("state", "in", ("completed", "processing", "extracted"))],
                    order="create_date desc",
                    limit=1,
                )
                if not job:
                    return Markup("<p>%s</p>") % html_escape(_("No tender jobs found."))

                query = self._extract_after_for(text)
                # Find bidder in this job by company name match
                bidder = None
                ql = query.lower()
                for b in (job.bidders or []):
                    nm = (b.vendor_company_name or "").strip()
                    if nm and nm.lower() in ql:
                        bidder = b
                        break
                if not bidder and query:
                    bidder = self.env["tende_ai.bidder"].sudo().search(
                        [("job_id", "=", job.id), ("vendor_company_name", "ilike", query)],
                        limit=1,
                    )

                if not bidder:
                    return Markup("<p>%s</p>") % html_escape(
                        _("I couldn’t find that bidder in the latest job (%s). Try: “attachments for APOLLO INFOWAYS”") % (job.name or "")
                    )

                atts = bidder.attachment_ids
                if not atts:
                    return Markup("<p>%s</p>") % html_escape(
                        _("No attachments found for %s. Open the bidder record and click Attachments, or generate them if needed.")
                        % (bidder.vendor_company_name or "")
                    )

                rows = []
                for a in atts[:50]:
                    rows.append([
                        self._download_attachment_link(a.id, a.name or _("Download")),
                        self._record_link("ir.attachment", a.id, _("Open")),
                    ])
                title = _("Attachments") + f" — {bidder.vendor_company_name or ''} ({job.name or ''})"
                return self._html_table(title, ["Download", "Record"], rows, max_rows=50, add_index=True)

            # Eligibility / Qualification criteria quick answer (no Gemini needed)
            if re.search(r"\b(eligibility|criteria|qualification|qualifications)\b", low) and re.search(r"\b(list|show|what|give)\b", low):
                job = self.env["tende_ai.job"].sudo().search(
                    [("state", "in", ("completed", "processing", "extracted"))],
                    order="create_date desc",
                    limit=1,
                )
                if not job:
                    return Markup("<p>%s</p>") % html_escape(_("No tender jobs found."))
                criteria = job.eligibility_criteria.sudo().sorted(key=lambda r: (r.sl_no or ""))
                if not criteria:
                    return Markup("<p>%s</p>") % html_escape(_("No eligibility/qualification criteria found on the latest job (%s).") % (job.name or ""))
                rows = [[self._record_link("tende_ai.eligibility_criteria", c.id, c.sl_no or ""), c.criteria or "", c.supporting_document or ""] for c in criteria[:100]]
                title = _("Eligibility / Qualification Criteria") + f" ({job.name or ''})"
                return self._html_table(title, ["Criteria (Sl No)", "Criteria", "Supporting Document"], rows, max_rows=100, add_index=True)

            # Bidder names quick answer (no Gemini needed)
            if re.search(r"\bbidder(s)?\b", low) and re.search(r"\b(name|names|list|show)\b", low):
                job = self.env["tende_ai.job"].sudo().search(
                    [("state", "in", ("completed", "processing", "extracted"))],
                    order="create_date desc",
                    limit=1,
                )
                if not job:
                    return Markup("<p>%s</p>") % html_escape(_("No tender jobs found."))
                bidders = [b for b in (job.bidders or []) if b.vendor_company_name]
                if not bidders:
                    return Markup("<p>%s</p>") % html_escape(_("No bidders found on the latest job (%s).") % (job.name or ""))
                rows = [[self._record_link("tende_ai.bidder", b.id, b.vendor_company_name)] for b in bidders[:50]]
                return self._html_table(_("Bidder names") + f" ({job.name or ''})", ["Bidder"], rows, max_rows=50, add_index=True)

            # Payments quick answer (no Gemini needed) - redacted
            if re.search(r"\bpayment(s)?\b", low) and re.search(r"\b(list|show)\b", low):
                job = self.env["tende_ai.job"].sudo().search(
                    [("state", "in", ("completed", "processing", "extracted"))],
                    order="create_date desc",
                    limit=1,
                )
                if not job:
                    return Markup("<p>%s</p>") % html_escape(_("No tender jobs found."))
                pays = job.payment_ids.sudo()
                if not pays:
                    return Markup("<p>%s</p>") % html_escape(_("No payments found on the latest job (%s).") % (job.name or ""))
                rows = []
                for p in pays[:25]:
                    bidder_label = p.company_name or (p.bidder_id.vendor_company_name if p.bidder_id else "")
                    bidder_link = self._record_link("tende_ai.bidder", p.bidder_id.id, bidder_label) if p.bidder_id else html_escape(bidder_label)
                    pay_link = self._record_link("tende_ai.payment", p.id, _("Open"))
                    rows.append([bidder_link, p.vendor or "", p.amount_inr or "", p.transaction_date or "", p.status or "", pay_link])
                title = _("Payments (first 25, redacted)") + f" ({job.name or ''})"
                return self._html_table(title, ["Bidder", "Vendor", "Amount (INR)", "Date", "Status", "Payment"], rows, max_rows=25, add_index=True)

            # Work experience quick answer (no Gemini needed)
            if re.search(r"\bwork experience\b|\bexperience\b", low) and re.search(r"\b(list|show)\b", low):
                job = self.env["tende_ai.job"].sudo().search(
                    [("state", "in", ("completed", "processing", "extracted"))],
                    order="create_date desc",
                    limit=1,
                )
                if not job:
                    return Markup("<p>%s</p>") % html_escape(_("No tender jobs found."))
                work = job.work_experience_ids.sudo()
                if not work:
                    return Markup("<p>%s</p>") % html_escape(_("No work experience records found on the latest job (%s).") % (job.name or ""))
                rows = []
                for w in work[:20]:
                    bidder_label = w.vendor_company_name or (w.bidder_id.vendor_company_name if w.bidder_id else "")
                    bidder_link = self._record_link("tende_ai.bidder", w.bidder_id.id, bidder_label) if w.bidder_id else html_escape(bidder_label)
                    work_link = self._record_link("tende_ai.work_experience", w.id, _("Open"))
                    rows.append([
                        bidder_link,
                        w.name_of_work or "",
                        w.contract_amount_inr or "",
                        w.date_of_start or "",
                        w.date_of_completion or "",
                        work_link,
                    ])
                title = _("Work experience (first 20)") + f" ({job.name or ''})"
                return self._html_table(title, ["Bidder", "Work", "Amount", "Start", "End", "Record"], rows, max_rows=20, add_index=True)

            # Evaluation / qualification results quick hint (routes to Gemini if asked in detail)
            if re.search(r"\b(qualify|qualified|qualification|eligible|eligibility)\b", low) and re.search(r"\b(pass|fail|failed|why)\b", low):
                # Let Gemini answer, but we still need a job selection (handled below).
                pass

            # List intent for jobs (only if user explicitly asks for jobs)
            if re.search(r"\b(job|jobs)\b", low) and re.search(r"\b(list|show|latest)\b", low):
                jobs = self.env["tende_ai.job"].search([], order="create_date desc", limit=8)
                if not jobs:
                    return Markup("<p>%s</p>") % html_escape(_("No tender jobs found."))
                rows = [[self._record_link("tende_ai.job", j.id, j.name), j.state] for j in jobs]
                return self._html_table(_("Latest jobs"), ["Job", "Status"], rows, max_rows=8, add_index=True)

            # Selected/approved intent
            if re.search(r"\b(selected|shortlisted|approved|published)\b", low):
                tenders = self.env["tende_ai.tender"].search(
                    [("state", "in", ("approved", "published"))],
                    order="create_date desc",
                    limit=12,
                )
                if not tenders:
                    return Markup("<p>%s</p>") % html_escape(_("No approved/published tenders found."))
                rows = []
                for t in tenders:
                    ref = t.ref_no or t.tender_id or ""
                    dept = t.department_name or ""
                    rows.append([self._record_link("tende_ai.tender", t.id, ref), t.state, dept])
                return self._html_table(_("Selected (approved/published) tenders"), ["Tender", "State", "Department"], rows, max_rows=12, add_index=True)

            # Any other tender question -> route to Gemini using the latest completed job by default,
            # unless a job name is explicitly mentioned.
            job = None
            m_job = re.search(r"\b([a-z0-9]+(?:_[a-z0-9]+)+)\b", low)
            if m_job:
                job_key = m_job.group(1)
                job = self.env["tende_ai.job"].sudo().search([("name", "ilike", job_key)], limit=1)
            if not job:
                job = self.env["tende_ai.job"].sudo().search(
                    [("state", "in", ("completed", "processing", "extracted"))],
                    order="create_date desc",
                    limit=1,
                )

            if job:
                # PAN / sensitive PII: do not answer via Gemini or chat
                if re.search(r"\bpan\b|\bgstin\b|\bphone\b|\bemail\b", low):
                    return Markup("<p>%s</p>") % html_escape(
                        _("For security, I won’t share bidder PII (PAN/GSTIN/phone/email) in chat. "
                          "Please open the bidder records from the job’s Bidder tab.")
                    )
                from ..services.tender_chat_service import answer_job_question
                res = answer_job_question(env=self.env, job_id=job.id, question=text, history=None, model=None) or {}
                if res.get("success"):
                    ans = (res.get("answer") or "").strip() or _("No answer available.")
                    prefix = _("(Using job %s) ") % (job.name or "")
                    return Markup("<p>%s%s</p>") % (html_escape(prefix), html_escape(ans))
                err = (res.get("message") or res.get("error") or _("Unable to answer.")).strip()
                return Markup("<p><b>%s</b> %s</p>") % (html_escape(_("Error:")), html_escape(err))

        if low.startswith("/tender"):
            # /tender help
            if low in ("/tender", "/tender help", "/tender ?"):
                style = self._get_style_dict()
                return html_escape(
                    _("Try:%(new_line)s"
                      "%(command_start)s/tender list%(command_end)s%(new_line)s"
                      "%(command_start)s/tender count%(command_end)s%(new_line)s"
                      "%(command_start)s/tender selected%(command_end)s%(new_line)s"
                      "%(command_start)s/tender TENDER_01 which bidders failed and why?%(command_end)s")
                ) % style

            # /tender count
            if low in ("/tender count", "/tendercount"):
                cnt = self.env["tende_ai.job"].search_count([])
                style = self._get_style_dict()
                style.update({"count": cnt})
                return html_escape(_("You currently have access to %(bold_start)s%(count)s%(bold_end)s tender jobs.")) % style

            # /tender list
            if low in ("/tender list", "/tender latest"):
                jobs = self.env["tende_ai.job"].search([], order="create_date desc", limit=8)
                if not jobs:
                    return Markup("<p>%s</p>") % html_escape(_("No tender jobs found."))
                lines = []
                for j in jobs:
                    lines.append(f"{j.name} — {j.state}")
                return Markup("<p><b>%s</b></p><pre>%s</pre>") % (html_escape(_("Latest jobs")), html_escape("\n".join(lines)))

            # /tender selected  (tenders in approved/published)
            if low in ("/tender selected", "/tender shortlisted", "/tender approved"):
                tenders = self.env["tende_ai.tender"].search([("state", "in", ("approved", "published"))], order="create_date desc", limit=12)
                if not tenders:
                    return Markup("<p>%s</p>") % html_escape(_("No approved/published tenders found."))
                lines = []
                for t in tenders:
                    label = t.state
                    ref = t.ref_no or t.tender_id or ""
                    dept = t.department_name or ""
                    lines.append(f"{ref} — {label} — {dept}".strip(" -"))
                return Markup("<p><b>%s</b></p><pre>%s</pre>") % (html_escape(_("Selected (approved/published) tenders")), html_escape("\n".join(lines)))

            # /tender <job_name> <question>
            m = re.match(r"^/tender\s+(\S+)\s+(.+)$", text, flags=re.IGNORECASE)
            if m:
                job_key = m.group(1).strip()
                question = m.group(2).strip()

                job = None
                if job_key.isdigit():
                    job = self.env["tende_ai.job"].sudo().browse(int(job_key))
                if not job or not job.exists():
                    job = self.env["tende_ai.job"].sudo().search([("name", "=", job_key)], limit=1)
                if not job:
                    return Markup("<p><b>%s</b> %s</p>") % (html_escape(_("Error:")), html_escape(_("Job not found.")))

                # PAN / sensitive PII: do not answer via Gemini or chat
                if re.search(r"\bpan\b|\bgstin\b|\bphone\b|\bemail\b", question.lower()):
                    return Markup("<p>%s</p>") % html_escape(
                        _("For security, I won’t share bidder PII (PAN/GSTIN/phone/email) in chat. "
                          "Please open the bidder records from the job’s Bidder tab.")
                    )

                from ..services.tender_chat_service import answer_job_question

                res = answer_job_question(
                    env=self.env,
                    job_id=job.id,
                    question=question,
                    history=None,
                    model=None,
                ) or {}

                if res.get("success"):
                    ans = (res.get("answer") or "").strip() or _("No answer available.")
                    return Markup("<p>%s</p>") % html_escape(ans)
                err = (res.get("message") or res.get("error") or _("Unable to answer.")).strip()
                return Markup("<p><b>%s</b> %s</p>") % (html_escape(_("Error:")), html_escape(err))

            # fallback help
            style = self._get_style_dict()
            return html_escape(
                _("Try:%(new_line)s"
                  "%(command_start)s/tender list%(command_end)s%(new_line)s"
                  "%(command_start)s/tender TENDER_01 which bidders failed and why?%(command_end)s")
            ) % style

        return super()._get_answer(record, body, values, command=command)


