# -*- coding: utf-8 -*-

import json
import re
from typing import Any, Dict, List

from .gemini_service import upload_file_to_gemini, generate_with_gemini


TENDER_PROMPT = """
Act as a high-precision data extraction engine for Government Tender documents.

STRICT EXTRACTION RULES:
1. Extract data ONLY from the provided PDF.
2. DO NOT GUESS any value.
3. If a value is not explicitly stated, return "" (empty string) or [].
4. Dates: keep as shown in PDF (do not invent).
5. Currency: Extract numeric value only for 'estimatedValueINR' (no symbols).

IMPORTANT:
The tender PDF contains a section/table like:
"Bidder's Minimum Eligibility Criteria" (may be numbered like 13, 14, etc.)
You MUST extract all rows from that table, if present.

REQUIRED JSON SCHEMA:
{
  "departmentName": "",
  "tenderId": "",
  "refNo": "",
  "tenderCreator": "",
  "procurementCategory": "",
  "tenderType": "",
  "organizationHierarchy": "",
  "estimatedValueINR": "",
  "tenderCurrency": "",
  "biddingCurrency": "",
  "offerValidityDays": "",
  "previousTenderNo": "",
  "publishedOn": "",
  "bidSubmissionStart": "",
  "bidSubmissionEnd": "",
  "tenderOpenedOn": "",
  "description": "",
  "nit": "",

  "bidderEligibilityCriteria": [
    {
      "slNo": "",
      "criteria": "",
      "supportingDocument": ""
    }
  ]
}

ELIGIBILITY CRITERIA EXTRACTION RULES:
- Find the section/table heading similar to:
  "Bidder's Minimum Eligibility Criteria"
  "Bidders Minimum Eligibility Criteria"
  "Minimum Eligibility Criteria"
- Extract ALL rows. Each row becomes one object in bidderEligibilityCriteria[].
- slNo: keep as shown (e.g., "1.", "2", "3").
- criteria: full text from the "Criteria" column.
- supportingDocument: full text from the "Supporting Document / Information..." column.
- Preserve line breaks as spaces (make it readable).
- If table not found, return bidderEligibilityCriteria as [].

RESPONSE REQUIREMENT:
Return ONLY the raw JSON object. Do not include markdown formatting or any explanation.
""".strip()


def clean_json_response(raw_text: str) -> dict:
    """
    Removes markdown code blocks and attempts to parse JSON.
    Supports when LLM returns text with code fences.
    Optimized to avoid multiple regex passes.
    """
    if not raw_text:
        return {}

    cleaned = raw_text.strip()
    
    # Remove markdown code blocks if present (e.g., ```json ... ```)
    if "```" in cleaned:
        cleaned = re.sub(r"```(?:json)?\s*([\s\S]*?)\s*```", r"\1", cleaned).strip()

    # Try direct parse first
    try:
        obj = json.loads(cleaned)
        return obj if isinstance(obj, dict) else {}
    except (json.JSONDecodeError, ValueError):
        pass

    # Fallback: extract anything between the first { and last }
    match = re.search(r"(\{[\s\S]*\})", cleaned)
    if match:
        try:
            obj = json.loads(match.group(1))
            return obj if isinstance(obj, dict) else {}
        except (json.JSONDecodeError, ValueError):
            pass
    
    raise ValueError(f"Failed to parse JSON from AI response: {raw_text[:200]}")


def _normalize_criteria(arr: Any) -> List[Dict[str, str]]:
    """
    Ensures bidderEligibilityCriteria is always a list of dicts
    with keys: slNo, criteria, supportingDocument
    """
    if not isinstance(arr, list):
        return []

    out: List[Dict[str, str]] = []
    for r in arr:
        if not isinstance(r, dict):
            continue
        out.append({
            "slNo": str(r.get("slNo", "") or "").strip(),
            "criteria": str(r.get("criteria", "") or "").strip(),
            "supportingDocument": str(r.get("supportingDocument", "") or "").strip(),
        })
    # remove empty rows
    out = [x for x in out if (x["slNo"] or x["criteria"] or x["supportingDocument"])]
    return out


def extract_tender_from_pdf_with_gemini(pdf_path: str, model: str = "gemini-3-flash-preview", env=None) -> dict:
    """
    Uploads tender.pdf to the AI service, extracts structured tender data + eligibility criteria,
    and returns a dictionary with analytics.

    Output includes:
      - normal tender fields
      - bidderEligibilityCriteria: []
      - tenderAnalytics: {model, durationMs, tokens}
    
    Args:
        pdf_path: Path to the tender PDF file
        model: AI model to use
        env: Optional Odoo environment (api.Environment). Used to get API key from system parameters.
    """
    uploaded_file = upload_file_to_gemini(pdf_path, env=env)

    # generate_with_gemini now returns dict: {text, usage, model, durationMs}
    out = generate_with_gemini(
        contents=[uploaded_file, TENDER_PROMPT],
        model=model,
        env=env,
    )

    text = ""
    usage = {}
    duration_ms = 0
    used_model = model

    if isinstance(out, dict):
        text = str(out.get("text", "") or "")
        usage = out.get("usage") or {}
        duration_ms = int(out.get("durationMs") or 0)
        used_model = str(out.get("model") or model)
    else:
        text = str(out or "")

    try:
        data = clean_json_response(text) or {}
    except Exception as e:
        print(f"Tender Extraction Error: {str(e)}")
        data = {}

    # Ensure required keys exist
    if not isinstance(data, dict):
        data = {}

    data.setdefault("departmentName", "")
    data.setdefault("tenderId", "")
    data.setdefault("refNo", "")
    data.setdefault("tenderCreator", "")
    data.setdefault("procurementCategory", "")
    data.setdefault("tenderType", "")
    data.setdefault("organizationHierarchy", "")
    data.setdefault("estimatedValueINR", "")
    data.setdefault("tenderCurrency", "")
    data.setdefault("biddingCurrency", "")
    data.setdefault("offerValidityDays", "")
    data.setdefault("previousTenderNo", "")
    data.setdefault("publishedOn", "")
    data.setdefault("bidSubmissionStart", "")
    data.setdefault("bidSubmissionEnd", "")
    data.setdefault("tenderOpenedOn", "")
    data.setdefault("description", "")
    data.setdefault("nit", "")

    # Normalize eligibility criteria
    data["bidderEligibilityCriteria"] = _normalize_criteria(data.get("bidderEligibilityCriteria"))

    # Attach analytics for tender extraction
    # Normalize tokens keys to what frontend expects
    tokens = {
        "promptTokens": int((usage or {}).get("promptTokens") or 0),
        "outputTokens": int((usage or {}).get("outputTokens") or 0),
        "totalTokens": int((usage or {}).get("totalTokens") or 0),
    }

    data["tenderAnalytics"] = {
        "model": used_model,
        "durationMs": duration_ms,
        "tokens": tokens,
    }

    return data

