# -*- coding: utf-8 -*-

import json
import logging
import os
import re
import time
from typing import List, Dict, Any, Tuple

from .gemini_service import upload_file_to_gemini, generate_with_gemini

_logger = logging.getLogger(__name__)


def _pick_relevant_pdfs(pdf_paths: List[str], criteria: List[Dict[str, Any]], max_files: int = 10) -> List[str]:
    """Heuristic: pick PDFs that look relevant to supporting documents / criteria keywords."""
    if not pdf_paths:
        return []
    if len(pdf_paths) <= max_files:
        return pdf_paths

    wanted = []
    tokens = set()
    for c in criteria or []:
        for k in ("supporting_document", "supportingDocument", "criteria"):
            v = (c.get(k) or "")
            for t in re.split(r"[^A-Za-z0-9]+", v):
                t = (t or "").strip().lower()
                if len(t) >= 4:
                    tokens.add(t)

    for p in pdf_paths:
        base = os.path.basename(p).lower()
        score = 0
        for t in tokens:
            if t in base:
                score += 3
        # common tender docs
        if any(x in base for x in ("emd", "turnover", "networth", "experience", "registration", "gst", "pan", "maf", "oem", "warranty")):
            score += 1
        wanted.append((score, p))

    wanted.sort(key=lambda x: x[0], reverse=True)
    picked = [p for score, p in wanted if score > 0][:max_files]
    if len(picked) < min(max_files, len(pdf_paths)):
        # fill with remaining (stable)
        for _, p in wanted:
            if p not in picked:
                picked.append(p)
            if len(picked) >= max_files:
                break
    return picked[:max_files]


def evaluate_bidder_against_criteria(
    bidder_name: str,
    criteria: List[Dict[str, Any]],
    bidder_facts: Dict[str, Any],
    pdf_paths: List[str] | None = None,
    env=None,
    model: str = None,
) -> Dict[str, Any]:
    """
    Single AI call to evaluate bidder against eligibility criteria using DB-extracted facts.
    Optionally attach a limited set of PDFs to produce stronger evidence/citations.
    Returns dict with:
      - overallResult: pass|fail|unknown
      - lines: [{slNo, result, reason, evidence, missingDocuments}]
      - durationMs, usage, model
    """
    t0 = time.time()
    model = model or (os.getenv("AI_EVAL_MODEL") or os.getenv("AI_COMPANY_MODEL") or os.getenv("GEMINI_COMPANY_MODEL") or "gemini-3-flash-preview")

    use_pdfs = str(os.getenv("AI_EVAL_USE_PDFS", "0")).strip().lower() in ("1", "true", "yes", "y")
    pdf_paths = pdf_paths or []
    uploads = []
    if use_pdfs and pdf_paths:
        selected_pdfs = _pick_relevant_pdfs(pdf_paths, criteria, max_files=int(os.getenv("AI_EVAL_MAX_FILES", "10")))
        for p in selected_pdfs:
            try:
                uploads.append(upload_file_to_gemini(p, env=env))
            except Exception as e:
                _logger.warning("Eligibility eval: upload failed for %s: %s", p, str(e))

    criteria_compact = []
    for c in criteria or []:
        if not isinstance(c, dict):
            continue
        criteria_compact.append({
            "slNo": c.get("slNo") or c.get("sl_no") or "",
            "criteria": c.get("criteria") or "",
            "supportingDocument": c.get("supportingDocument") or c.get("supporting_document") or "",
        })

    system = (
        "You are an assistant that evaluates bidder documents against tender eligibility criteria.\n"
        "Return STRICT JSON only.\n"
        "You must be conservative: if evidence is not found, mark unknown or fail (based on criterion).\n"
        "For each criterion provide a short reason and evidence (document name + quoted snippet if possible).\n"
    )

    user = {
        "task": "evaluate_eligibility",
        "bidderName": bidder_name,
        "bidderFacts": bidder_facts or {},
        "criteria": criteria_compact,
        "outputSchema": {
            "overallResult": "pass|fail|unknown",
            "lines": [
                {
                    "slNo": "string",
                    "result": "pass|fail|unknown",
                    "reason": "string",
                    "evidence": "string",
                    "missingDocuments": ["string"],
                }
            ],
        },
    }

    contents = [system, json.dumps(user, ensure_ascii=False)]
    # Optionally attach PDFs so the model can produce citations/evidence
    if uploads:
        contents.extend([u for u in uploads if u is not None])

    out = generate_with_gemini(model=model, contents=contents, env=env)
    raw = (out or {}).get("text") or ""
    usage = (out or {}).get("usage") or {}
    model_used = (out or {}).get("model") or model
    duration_ms = (out or {}).get("durationMs") or int((time.time() - t0) * 1000)

    # Parse JSON (best effort)
    data = {}
    try:
        data = json.loads(raw) if raw else {}
    except Exception:
        m = re.search(r"\{[\s\S]*\}", raw or "")
        if m:
            try:
                data = json.loads(m.group(0))
            except Exception:
                data = {}

    if not isinstance(data, dict):
        data = {}

    data.setdefault("overallResult", "unknown")
    data.setdefault("lines", [])
    return {
        "result": data,
        "usage": usage,
        "model": model_used,
        "durationMs": duration_ms,
    }


