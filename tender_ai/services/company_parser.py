# -*- coding: utf-8 -*-

import os
import json
import re
import time
from typing import Any, Dict, List, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from .gemini_service import upload_file_to_gemini, generate_with_gemini


# ----------------------------
# Prompt (ONE PDF at a time)
# ----------------------------
ONE_PDF_PROMPT_TEMPLATE = """
You are a HIGH-PRECISION data extraction engine for Government Tender bidder documents.

You will receive ONE PDF that belongs to ONE company/bidder.
The PDF may contain scanned images and tables.
You MUST OCR where required.

Return STRICT JSON ONLY (no markdown, no explanation).

Company folder name (SOURCE OF TRUTH for bidder vendorCompanyName):
"{company_name}"

GENERAL RULES:
- Extract information ONLY if explicitly present in the PDF.
- DO NOT GUESS. If not found return "".
- Keep formatting as in document (PAN/GSTIN, dates).
- Extract ALL rows you can find in this PDF for:
  (1) payments
  (2) workExperience

Return JSON EXACTLY in this schema:

{{
  "bidder": {{
    "vendorCompanyName": "{company_name}",
    "companyAddress": "",
    "emailId": "",
    "contactPerson": "",
    "contactNo": "",
    "pan": "",
    "gstin": "",
    "placeOfRegistration": "",
    "offerValidityDays": ""
  }},
  "payments": [
    {{
      "vendor": "",
      "paymentMode": "",
      "bankName": "",
      "transactionId": "",
      "amountINR": "",
      "transactionDate": "",
      "status": ""
    }}
  ],
  "workExperience": [
    {{
      "vendorCompanyName": "{company_name}",
      "nameOfWork": "",
      "employer": "",
      "location": "",
      "contractAmountINR": "",
      "dateOfStart": "",
      "dateOfCompletion": "",
      "completionCertificate": "",
      "attachment": ""
    }}
  ]
}}

WORK EXPERIENCE RULES:
- Work experience may appear under headings like:
  "Work Experience", "Similar Work", "Past Experience", "Completed Works", "Ongoing Works"
- Each row must be one object in workExperience[].
- contractAmountINR: numeric string only, commas allowed. No currency symbols.
- dateOfStart/dateOfCompletion: keep as shown in PDF.
- completionCertificate: Yes/No or certificate number if present, else "".
- attachment: filename/attachment reference if present, else "".
""".strip()


# ----------------------------
# Helpers
# ----------------------------
def _safe_json_load(text: str) -> Dict[str, Any]:
    """
    Robust JSON extraction: parse directly, else extract first {...} block.
    Optimized to avoid multiple regex searches.
    """
    if not text:
        return {}
    text = text.strip()

    # Try direct parse first (most common case)
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else {}
    except (json.JSONDecodeError, ValueError):
        pass

    # Remove markdown code blocks if present
    if "```" in text:
        text = re.sub(r"```(?:json)?\s*([\s\S]*?)\s*```", r"\1", text).strip()

    # Try parsing again after markdown removal
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else {}
    except (json.JSONDecodeError, ValueError):
        pass

    # Last resort: extract JSON object from text
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        try:
            obj = json.loads(m.group(0))
            return obj if isinstance(obj, dict) else {}
        except (json.JSONDecodeError, ValueError):
            pass

    return {}


def _is_valid_pdf(path: str) -> bool:
    """
    Keep this LENIENT (like your earlier bidder_parser),
    otherwise many tender PDFs get skipped and results become empty.
    """
    try:
        if not path or not os.path.exists(path):
            return False
        if not path.lower().endswith(".pdf"):
            return False

        name = os.path.basename(path)
        if name.startswith("."):
            return False
        if "__macosx" in path.lower():
            return False

        # Reject only extremely tiny files
        if os.path.getsize(path) < 200:
            return False

        return True
    except Exception:
        return False


def _merge_first_non_empty(base: Dict[str, str], incoming: Dict[str, Any]) -> Dict[str, str]:
    """Merge bidder fields: keep existing if already non-empty, else fill from incoming."""
    if not isinstance(incoming, dict):
        return base

    for k in base.keys():
        if base.get(k, ""):
            continue
        v = incoming.get(k, "")
        if v is None:
            v = ""
        v = str(v).strip()
        if v:
            base[k] = v
    return base


def _normalize_payments(arr: Any) -> List[Dict[str, str]]:
    if not isinstance(arr, list):
        return []
    out: List[Dict[str, str]] = []
    for p in arr:
        if not isinstance(p, dict):
            continue
        out.append({
            "vendor": str(p.get("vendor", "") or "").strip(),
            "paymentMode": str(p.get("paymentMode", "") or "").strip(),
            "bankName": str(p.get("bankName", "") or "").strip(),
            "transactionId": str(p.get("transactionId", "") or "").strip(),
            "amountINR": str(p.get("amountINR", "") or "").strip(),
            "transactionDate": str(p.get("transactionDate", "") or "").strip(),
            "status": str(p.get("status", "") or "").strip(),
        })
    return out


def _normalize_work_experience(arr: Any, company_name: str) -> List[Dict[str, str]]:
    if not isinstance(arr, list):
        return []

    out: List[Dict[str, str]] = []
    for w in arr:
        if not isinstance(w, dict):
            continue
        out.append({
            "vendorCompanyName": company_name,
            "nameOfWork": str(w.get("nameOfWork", "") or "").strip(),
            "employer": str(w.get("employer", "") or "").strip(),
            "location": str(w.get("location", "") or "").strip(),
            "contractAmountINR": str(w.get("contractAmountINR", "") or "").strip(),
            "dateOfStart": str(w.get("dateOfStart", "") or "").strip(),
            "dateOfCompletion": str(w.get("dateOfCompletion", "") or "").strip(),
            "completionCertificate": str(w.get("completionCertificate", "") or "").strip(),
            "attachment": str(w.get("attachment", "") or "").strip(),
        })
    return out


def _dedupe_work_experience(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """
    Deduplicate rows across PDFs.
    Key uses the most identifying columns.
    """
    seen: set = set()
    deduped: List[Dict[str, str]] = []

    def key(r: Dict[str, str]) -> Tuple[str, str, str, str, str]:
        return (
            (r.get("nameOfWork") or "").lower(),
            (r.get("employer") or "").lower(),
            (r.get("location") or "").lower(),
            (r.get("dateOfStart") or "").lower(),
            (r.get("contractAmountINR") or "").lower(),
        )

    for r in rows:
        k = key(r)
        if k in seen:
            continue
        seen.add(k)
        deduped.append(r)
    return deduped


def _coerce_schema(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize into:
      {"bidder": {...}, "payments": [...], "workExperience": [...]}

    Sometimes the AI service may return bidder fields at root instead of inside "bidder".
    """
    if not isinstance(data, dict):
        return {"bidder": {}, "payments": [], "workExperience": []}

    bidder = data.get("bidder")
    payments = data.get("payments")
    work_exp = data.get("workExperience")

    if not isinstance(bidder, dict):
        possible_keys = {
            "companyAddress", "emailId", "contactPerson", "contactNo",
            "pan", "gstin", "placeOfRegistration", "offerValidityDays"
        }
        bidder = data if any(k in data for k in possible_keys) else {}

    if not isinstance(payments, list):
        payments = []

    if not isinstance(work_exp, list):
        work_exp = []

    return {"bidder": bidder, "payments": payments, "workExperience": work_exp}


def _merge_tokens(total: Dict[str, int], usage: Dict[str, Any]) -> Dict[str, int]:
    if not isinstance(total, dict):
        total = {"promptTokens": 0, "outputTokens": 0, "totalTokens": 0}
    if not isinstance(usage, dict):
        return total

    def _to_int(v):
        try:
            return int(v)
        except Exception:
            return 0

    total["promptTokens"] += _to_int(usage.get("promptTokens"))
    total["outputTokens"] += _to_int(usage.get("outputTokens"))
    total["totalTokens"] += _to_int(usage.get("totalTokens"))
    return total


# ----------------------------
# Parallel extraction per PDF
# ----------------------------
def _extract_from_single_pdf(company_name: str, pdf_path: str, model: str, env=None) -> Dict[str, Any]:
    """
    Upload 1 PDF + call the AI service 1 time.
    Returns:
      {
        "bidder": {...}, "payments": [...], "workExperience": [...],
        "analytics": {"pdfPath","model","durationMs","tokens","success","error"}
      }
    
    Args:
        company_name: Name of the company
        pdf_path: Path to the PDF file
        model: AI model to use
        env: Optional Odoo environment (api.Environment). Used to get API key from system parameters.
    """
    prompt = ONE_PDF_PROMPT_TEMPLATE.format(company_name=company_name)

    per_pdf_t0 = time.time()
    try:
        uploaded = upload_file_to_gemini(pdf_path, env=env)

        out = generate_with_gemini(
            contents=[prompt, uploaded],
            model=model,
            env=env,
        )

        text = ""
        usage = {}
        used_model = model
        duration_ms = 0

        if isinstance(out, dict):
            text = str(out.get("text", "") or "")
            usage = out.get("usage") or {}
            used_model = str(out.get("model") or model)
            duration_ms = int(out.get("durationMs") or 0)
        else:
            text = str(out or "")

        data = _safe_json_load(text) or {}
        data = _coerce_schema(data)

        per_pdf_t1 = time.time()
        dur_ms_final = duration_ms if duration_ms else int((per_pdf_t1 - per_pdf_t0) * 1000)

        tokens = {
            "promptTokens": int((usage or {}).get("promptTokens") or 0),
            "outputTokens": int((usage or {}).get("outputTokens") or 0),
            "totalTokens": int((usage or {}).get("totalTokens") or 0),
        }

        return {
            "bidder": data.get("bidder") or {},
            "payments": data.get("payments") or [],
            "workExperience": data.get("workExperience") or [],
            "analytics": {
                "pdfPath": pdf_path,
                "pdfName": os.path.basename(pdf_path),
                "model": used_model,
                "durationMs": dur_ms_final,
                "tokens": tokens,
                "success": True,
                "error": "",
            }
        }

    except Exception as e:
        per_pdf_t1 = time.time()
        return {
            "bidder": {},
            "payments": [],
            "workExperience": [],
            "analytics": {
                "pdfPath": pdf_path,
                "pdfName": os.path.basename(pdf_path),
                "model": model,
                "durationMs": int((per_pdf_t1 - per_pdf_t0) * 1000),
                "tokens": {"promptTokens": 0, "outputTokens": 0, "totalTokens": 0},
                "success": False,
                "error": str(e)[:500],
            }
        }


def extract_company_bidder_and_payments(
    company_name: str,
    pdf_paths: List[str],
    model: str = "gemini-3-flash-preview",
    max_workers: int = 6,
    env=None,
) -> Dict[str, Any]:
    """
    Parallel AI calls per PDF inside a company folder.

    Returns:
      {
        "bidder": {...},
        "payments": [...],
        "work_experience": [...],
        "analytics": {...}
      }
    """
    t0 = time.time()
    company_name = (company_name or "").strip()

    bidder_result: Dict[str, str] = {
        "vendorCompanyName": company_name,
        "companyAddress": "",
        "emailId": "",
        "contactPerson": "",
        "contactNo": "",
        "pan": "",
        "gstin": "",
        "placeOfRegistration": "",
        "offerValidityDays": "",
    }

    pdf_count_received = len(pdf_paths or [])

    if not pdf_paths:
        return {
            "bidder": bidder_result,
            "payments": [],
            "work_experience": [],
            "analytics": {
                "companyName": company_name,
                "durationMs": 0,
                "durationSeconds": 0,
                "pdfCountReceived": 0,
                "validPdfCount": 0,
                "geminiCalls": 0,
                "tokens": {"promptTokens": 0, "outputTokens": 0, "totalTokens": 0},
                "perPdf": [],
            },
        }

    valid_pdfs = sorted([p for p in (pdf_paths or []) if _is_valid_pdf(p)])
    valid_pdf_count = len(valid_pdfs)

    if not valid_pdfs:
        t1 = time.time()
        return {
            "bidder": bidder_result,
            "payments": [],
            "work_experience": [],
            "analytics": {
                "companyName": company_name,
                "durationMs": int((t1 - t0) * 1000),
                "durationSeconds": round(t1 - t0, 3),
                "pdfCountReceived": pdf_count_received,
                "validPdfCount": 0,
                "geminiCalls": 0,
                "tokens": {"promptTokens": 0, "outputTokens": 0, "totalTokens": 0},
                "perPdf": [],
            },
        }

    all_payments: List[Dict[str, str]] = []
    all_work_exp: List[Dict[str, str]] = []

    total_tokens = {"promptTokens": 0, "outputTokens": 0, "totalTokens": 0}
    per_pdf_analytics: List[Dict[str, Any]] = []

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = [
            ex.submit(_extract_from_single_pdf, company_name, pdf_path, model, env)
            for pdf_path in valid_pdfs
        ]

        for fut in as_completed(futures):
            try:
                result = fut.result() or {}

                bidder_part = result.get("bidder") or {}
                payments_part = result.get("payments") or []
                work_part = result.get("workExperience") or []

                bidder_result = _merge_first_non_empty(bidder_result, bidder_part)
                all_payments.extend(_normalize_payments(payments_part))
                all_work_exp.extend(_normalize_work_experience(work_part, company_name))

                # ✅ per-pdf analytics + token totals
                a = result.get("analytics") or {}
                if isinstance(a, dict):
                    per_pdf_analytics.append(a)
                    total_tokens = _merge_tokens(total_tokens, (a.get("tokens") or {}))

            except Exception:
                continue

    bidder_result["vendorCompanyName"] = company_name
    all_work_exp = _dedupe_work_experience(all_work_exp)

    t1 = time.time()

    # Count AI calls: 1 per valid PDF (even if fails)
    gemini_calls = valid_pdf_count

    company_analytics = {
        "companyName": company_name,
        "durationMs": int((t1 - t0) * 1000),
        "durationSeconds": round(t1 - t0, 3),
        "pdfCountReceived": pdf_count_received,
        "validPdfCount": valid_pdf_count,
        "geminiCalls": gemini_calls,
        "tokens": total_tokens,
        "perPdf": sorted(per_pdf_analytics, key=lambda x: str(x.get("pdfName") or "")),
        # helpful debugging counts
        "successPdfCount": sum(1 for x in per_pdf_analytics if x.get("success") is True),
        "failedPdfCount": sum(1 for x in per_pdf_analytics if x.get("success") is False),
    }

    return {
        "bidder": bidder_result,
        "payments": all_payments,
        "work_experience": all_work_exp,
        "analytics": company_analytics,
    }

