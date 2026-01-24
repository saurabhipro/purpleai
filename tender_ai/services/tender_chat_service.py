# -*- coding: utf-8 -*-

import json
import logging
from typing import Any, Dict, List, Optional

_logger = logging.getLogger(__name__)


def _safe_str(v) -> str:
    try:
        return str(v or "")
    except Exception:
        return ""


def _compact_history(history: Any, max_turns: int = 8) -> List[Dict[str, str]]:
    if not isinstance(history, list):
        return []
    out: List[Dict[str, str]] = []
    for item in history:
        if not isinstance(item, dict):
            continue
        role = _safe_str(item.get("role")).strip().lower()
        content = _safe_str(item.get("content")).strip()
        if role not in ("user", "assistant") or not content:
            continue
        out.append({"role": role, "content": content})
    return out[-max_turns:]


def _build_job_context(job) -> Dict[str, Any]:
    """
    Build a context blob for LLM Q&A about a Tender AI job.
    Default is "safe": we avoid bidder contact details (email/phone/PAN/GSTIN/address).
    """
    tender = job.tender_id

    # Eligibility criteria (cap)
    criteria_list = []
    for c in (job.eligibility_criteria or [])[:200]:
        criteria_list.append(
            {
                "sl_no": c.sl_no or "",
                "criteria": c.criteria or "",
                "supporting_document": c.supporting_document or "",
            }
        )

    # Bidders (safe subset, cap)
    bidders = []
    for b in (job.bidders or [])[:200]:
        bidders.append(
            {
                "id": b.id,
                "company_name": b.vendor_company_name or "",
                "place_of_registration": b.place_of_registration or "",
                "offer_validity_days": b.offer_validity_days or "",
            }
        )

    # Payments (redacted, cap)
    payments = []
    for p in (job.payment_ids or [])[:500]:
        payments.append(
            {
                "company_name": p.company_name or "",
                "vendor": p.vendor or "",
                "payment_mode": p.payment_mode or "",
                "amount_inr": p.amount_inr or "",
                "transaction_date": p.transaction_date or "",
                "status": p.status or "",
            }
        )

    # Work Experience (cap)
    work_experiences = []
    for w in (job.work_experience_ids or [])[:500]:
        work_experiences.append(
            {
                "vendor": w.vendor_company_name or "",
                "name_of_work": w.name_of_work or "",
                "employer": w.employer or "",
                "location": w.location or "",
                "contract_amount_inr": w.contract_amount_inr or "",
                "date_of_start": w.date_of_start or "",
                "date_of_completion": w.date_of_completion or "",
                "completion_certificate": w.completion_certificate or "",
            }
        )

    # Checks (summary + top lines, cap)
    checks = []
    for chk in (job.bidder_check_ids or [])[:200]:
        line_summ = []
        for ln in (chk.line_ids or [])[:50]:
            line_summ.append(
                {
                    "sl_no": ln.sl_no or "",
                    "criteria": ln.criteria or "",
                    "result": ln.result or "unknown",
                    "reason": ln.reason or "",
                    "missing_documents": ln.missing_documents or "",
                }
            )
        checks.append(
            {
                "bidder": chk.bidder_id.vendor_company_name if chk.bidder_id else "",
                "overall_result": chk.overall_result or "unknown",
                "counts": {
                    "total": chk.total_criteria or 0,
                    "pass": chk.passed_criteria or 0,
                    "fail": chk.failed_criteria or 0,
                    "unknown": chk.unknown_criteria or 0,
                },
                "error": chk.error_message or "",
                "lines": line_summ,
            }
        )

    # Analytics (parsed if possible)
    analytics = {}
    try:
        if job.analytics:
            analytics = json.loads(job.analytics) if isinstance(job.analytics, str) else (job.analytics or {})
    except Exception:
        analytics = {}

    ctx: Dict[str, Any] = {
        "job": {
            "id": job.id,
            "name": job.name,
            "state": job.state,
            "tender_reference": job.tender_reference or "",
            "companies_detected": job.companies_detected or 0,
            "error_message": job.error_message or "",
            "timing_minutes": {
                "extraction": job.extraction_time_minutes or 0.0,
                "evaluation": job.evaluation_time_minutes or 0.0,
                "total": job.processing_time_minutes or 0.0,
            },
        },
        "tender": {
            "id": tender.id if tender else None,
            "tender_id": tender.tender_id if tender else "",
            "ref_no": tender.ref_no if tender else "",
            "department_name": tender.department_name if tender else "",
            "procurement_category": tender.procurement_category if tender else "",
            "tender_type": tender.tender_type if tender else "",
            "estimated_value_inr": tender.estimated_value_inr if tender else "",
            "bid_submission_start": tender.bid_submission_start if tender else "",
            "bid_submission_end": tender.bid_submission_end if tender else "",
            "opened_on": tender.tender_opened_on if tender else "",
            "description": tender.description if tender else "",
            "nit": tender.nit if tender else "",
        },
        "eligibility_criteria": criteria_list,
        "bidders": bidders,
        "payments": payments,
        "work_experiences": work_experiences,
        "eligibility_checks": checks,
        "analytics": analytics if isinstance(analytics, dict) else {},
    }
    return ctx


def answer_job_question(
    env,
    job_id: int,
    question: str,
    history: Optional[Any] = None,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    question = _safe_str(question).strip()
    if not question:
        return {
            "success": False,
            "status": 400,
            "error": "VALIDATION_ERROR",
            "message": "question is required",
            "fields": ["question"],
        }

    job = env["tende_ai.job"].sudo().browse(int(job_id))
    if not job.exists():
        return {
            "success": False,
            "status": 404,
            "error": "NOT_FOUND",
            "message": f"Job {job_id} not found",
        }

    ctx = _build_job_context(job)
    compact_history = _compact_history(history)

    # Use existing Gemini integration from this module.
    try:
        from .gemini_service import generate_with_gemini  # type: ignore
    except Exception:
        generate_with_gemini = None  # type: ignore

    if generate_with_gemini is None:
        return {
            "success": False,
            "status": 500,
            "error": "AI_NOT_AVAILABLE",
            "message": "Gemini integration is not available (google-genai not installed or module not loaded).",
        }

    system = (
        "You are an assistant for Tender AI.\n"
        "Answer ONLY using the provided JOB_CONTEXT_JSON.\n"
        "If the answer is not present, say it is not available in the job data.\n"
        "Be concise and compute simple summaries if asked.\n"
        "Do NOT invent values.\n"
        "Do NOT output bidder PII (email/phone/PAN/GSTIN/address).\n"
    )

    ctx_json = json.dumps(ctx, ensure_ascii=False, sort_keys=True, indent=2)
    history_text = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in compact_history]) or "(none)"
    prompt = (
        f"{system}\n\n"
        f"JOB_CONTEXT_JSON:\n{ctx_json}\n\n"
        f"CHAT_HISTORY:\n{history_text}\n\n"
        f"USER_QUESTION:\n{question}\n"
    )

    used_model = model or "gemini-3-flash-preview"
    try:
        out = generate_with_gemini(contents=prompt, model=used_model, temperature=0.2, env=env)
        if isinstance(out, dict):
            return {
                "success": True,
                "answer": _safe_str(out.get("text")).strip(),
                "model": out.get("model") or used_model,
                "usage": out.get("usage") or {},
                "durationMs": out.get("durationMs") or 0,
            }
        return {"success": True, "answer": _safe_str(out).strip(), "model": used_model}
    except Exception as e:
        _logger.error("Tender AI chat failed for job_id=%s: %s", job_id, str(e), exc_info=True)
        return {
            "success": False,
            "status": 502,
            "error": "AI_ERROR",
            "message": str(e),
        }


def post_chat_to_job_chatter(env, job_id: int, question: str, answer: str) -> None:
    job = env["tende_ai.job"].sudo().browse(int(job_id))
    if not job.exists():
        return
    body = (
        "<p><b>AI Question:</b></p>"
        f"<p>{_safe_str(question)}</p>"
        "<p><b>AI Answer:</b></p>"
        f"<p>{_safe_str(answer)}</p>"
    )
    try:
        job.message_post(body=body, subtype_xmlid="mail.mt_note")
    except Exception:
        _logger.warning("Tender AI: failed posting chat to chatter (job_id=%s)", job_id, exc_info=True)


