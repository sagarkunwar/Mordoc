"""
Case-level compliance analyser for mortgage document packets.

analyse_case(enriched_docs, current_date=None) -> dict

No external HTTP calls. Uses rapidfuzz for fuzzy comparisons.
"""
from __future__ import annotations

import datetime
import re
from typing import List, Optional

try:
    from rapidfuzz import fuzz as _fuzz
    _HAS_FUZZ = True
except ImportError:
    _HAS_FUZZ = False

# ── Constants ─────────────────────────────────────────────────────────────────
_NAME_GREEN  = 90
_NAME_YELLOW = 70
_ADDR_GREEN  = 85
_ADDR_YELLOW = 65
_STALE_DAYS  = 90

_DEDUCT_DOB_MISMATCH  = 20
_DEDUCT_NAME_RED      = 10
_DEDUCT_EMPLOYER      = 15
_DEDUCT_STALE         = 5
_DEDUCT_ADDR_MISMATCH = 8

_NAME_KEYS    = ["full_name", "name_on_card", "card_holder", "account_holder"]
_DOB_KEYS     = ["dob", "date_of_birth"]
_ADDRESS_KEYS = ["address", "home_address"]
_DATE_FORMATS = ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d %b %Y", "%d %B %Y"]


# ── Date helpers ──────────────────────────────────────────────────────────────

def _parse_date(s) -> Optional[datetime.date]:
    if not s or not isinstance(s, str):
        return None
    s = s.strip()
    # Try each format
    for fmt in _DATE_FORMATS:
        try:
            return datetime.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    # Try to extract a date-like segment from complex strings
    # e.g. "01 Jan 2024 – 31 Mar 2024" → take the last match
    matches = re.findall(r'\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4}|\d{2}-\d{2}-\d{4}', s)
    if matches:
        return _parse_date(matches[-1])
    return None


def _resolve_field(data: dict, keys: list) -> Optional[str]:
    for k in keys:
        v = data.get(k)
        if v and isinstance(v, str) and v.strip() and v.lower() not in ("null", "none", "n/a"):
            return v.strip()
    return None


# ── Name comparison ───────────────────────────────────────────────────────────

def _expand_initials(name: str) -> str:
    """Remove period from single-letter initials so tokens are comparable."""
    return re.sub(r'\b([A-Za-z])\.\s*', r'\1 ', name).strip()


def _name_score(n1: str, n2: str) -> float:
    if not _HAS_FUZZ:
        return 100.0 if n1.lower() == n2.lower() else 0.0
    a = _expand_initials(n1).lower()
    b = _expand_initials(n2).lower()
    base = _fuzz.token_sort_ratio(a, b)
    # Partial ratio handles abbreviated first names
    partial = _fuzz.partial_token_sort_ratio(a, b)
    return float(max(base, partial))


def _name_flag(score: float) -> str:
    if score >= _NAME_GREEN:
        return "green"
    if score >= _NAME_YELLOW:
        return "yellow"
    return "red"


def _addr_flag(n1: str, n2: str) -> str:
    if not _HAS_FUZZ:
        return "green" if n1.lower() == n2.lower() else "yellow"
    score = _fuzz.token_sort_ratio(n1.lower(), n2.lower())
    if score >= _ADDR_GREEN:
        return "green"
    if score >= _ADDR_YELLOW:
        return "yellow"
    return "red"


# ── Freshness check ───────────────────────────────────────────────────────────

def _freshness_check(extracted: dict, today: datetime.date) -> tuple[str, Optional[int]]:
    for key in ["statement_end_date", "pay_period_end", "document_date"]:
        d = _parse_date(extracted.get(key))
        if d is not None:
            days = (today - d).days
            return ("yellow" if days > _STALE_DAYS else "green"), days
    return "n/a", None


# ── Employer consistency ──────────────────────────────────────────────────────

def _check_employers(enriched_docs: list, issues: list) -> dict:
    employers = []
    for doc in enriched_docs:
        if "payslip" in (doc.get("doc_type") or "").lower():
            emp = (doc.get("extracted_data") or {}).get("employer_name")
            if emp and isinstance(emp, str) and emp.strip():
                employers.append({"doc": doc.get("filename", ""), "name": emp.strip()})

    if len(employers) < 2:
        return {
            "employers_found": [e["name"] for e in employers],
            "flag": "n/a" if not employers else "green",
            "reason": "Single employer" if employers else "No payslips found",
        }

    mismatch = False
    names = [e["name"] for e in employers]
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            score = _fuzz.token_sort_ratio(names[i].lower(), names[j].lower()) if _HAS_FUZZ else (100 if names[i].lower() == names[j].lower() else 0)
            if score < 80:
                mismatch = True
                issues.append({
                    "severity": "red",
                    "category": "employer",
                    "filename": "Multiple payslips",
                    "detail":   f"Employer mismatch: '{names[i]}' vs '{names[j]}' ({score:.0f}% match)",
                })

    return {
        "employers_found": names,
        "flag": "red" if mismatch else "green",
        "reason": "Employer names consistent across payslips" if not mismatch else "Inconsistent employer names across payslips",
    }


# ── Public API ────────────────────────────────────────────────────────────────

def analyse_case(
    enriched_docs: list,
    current_date: Optional[datetime.date] = None,
) -> dict:
    """
    Analyse a mortgage document packet and return a compliance dict.

    Parameters
    ----------
    enriched_docs : list of dicts from _enrich_documents() — each must have:
                    filename, doc_type, tier (int), extracted_data (dict)
    current_date  : override today (for testing). Defaults to date.today().

    Returns
    -------
    dict with keys: golden_record, health_score, health_grade, health_label,
                    document_checks, employer_check, issues, summary
    """
    today = current_date or datetime.date.today()

    if not enriched_docs:
        return _empty_result()

    # ── 1. Select primary document (lowest tier number) ───────────────────────
    primary_idx = min(range(len(enriched_docs)),
                      key=lambda i: enriched_docs[i].get("tier", 5))
    primary = enriched_docs[primary_idx]
    p_data  = primary.get("extracted_data") or {}

    golden = {
        "full_name":       _resolve_field(p_data, _NAME_KEYS),
        "dob":             _resolve_field(p_data, _DOB_KEYS),
        "address":         _resolve_field(p_data, _ADDRESS_KEYS),
        "source_filename": primary.get("filename", ""),
        "source_doc_type": primary.get("doc_type", ""),
        "source_tier":     primary.get("tier", 5),
    }

    gr_name    = golden["full_name"]
    gr_dob     = _parse_date(golden["dob"])
    gr_address = golden["address"]

    # ── 2. Per-document checks ────────────────────────────────────────────────
    doc_checks: list = []
    issues:     list = []
    score = 100

    for i, doc in enumerate(enriched_docs):
        d          = doc.get("extracted_data") or {}
        is_primary = (i == primary_idx)
        filename   = doc.get("filename", "")

        # — Name —
        if is_primary:
            name_flag_val, name_score_val = "green", 100.0
        elif gr_name is None:
            name_flag_val, name_score_val = "n/a", 0.0
        else:
            cand = _resolve_field(d, _NAME_KEYS)
            if cand is None:
                name_flag_val, name_score_val = "n/a", 0.0
            else:
                ns = _name_score(gr_name, cand)
                name_flag_val = _name_flag(ns)
                name_score_val = ns
                if name_flag_val == "red":
                    score -= _DEDUCT_NAME_RED
                    issues.append({"severity": "red", "category": "name",
                                   "filename": filename,
                                   "detail": f"Name mismatch: '{cand}' vs golden '{gr_name}' ({ns:.0f}%)"})
                elif name_flag_val == "yellow":
                    issues.append({"severity": "yellow", "category": "name",
                                   "filename": filename,
                                   "detail": f"Partial name match: '{cand}' ({ns:.0f}%)"})

        # — DOB —
        if is_primary or gr_dob is None:
            dob_flag_val = "n/a"
        else:
            cand_dob = _parse_date(_resolve_field(d, _DOB_KEYS))
            if cand_dob is None:
                dob_flag_val = "n/a"
            elif cand_dob != gr_dob:
                dob_flag_val = "red"
                score -= _DEDUCT_DOB_MISMATCH
                issues.append({"severity": "red", "category": "dob",
                               "filename": filename,
                               "detail": f"DOB mismatch: {cand_dob} vs golden {gr_dob}"})
            else:
                dob_flag_val = "green"

        # — Address —
        if is_primary or gr_address is None:
            addr_flag_val = "n/a"
        else:
            cand_addr = _resolve_field(d, _ADDRESS_KEYS)
            if cand_addr is None:
                addr_flag_val = "n/a"
            else:
                addr_flag_val = _addr_flag(gr_address, cand_addr)
                if addr_flag_val in ("yellow", "red"):
                    score -= _DEDUCT_ADDR_MISMATCH
                    issues.append({"severity": addr_flag_val, "category": "address",
                                   "filename": filename,
                                   "detail": f"Address varies from golden record: '{cand_addr[:60]}'"})

        # — Freshness —
        fresh_flag, days_old = _freshness_check(d, today)
        if fresh_flag == "yellow":
            score -= _DEDUCT_STALE
            issues.append({"severity": "yellow", "category": "freshness",
                           "filename": filename,
                           "detail": f"Document is {days_old} days old (>{_STALE_DAYS}d threshold)"})

        doc_checks.append({
            "filename":       filename,
            "doc_type":       doc.get("doc_type", ""),
            "tier":           doc.get("tier", 5),
            "is_primary":     is_primary,
            "name_flag":      name_flag_val,
            "name_score":     round(name_score_val, 1),
            "dob_flag":       dob_flag_val,
            "address_flag":   addr_flag_val,
            "freshness_flag": fresh_flag,
            "days_old":       days_old,
        })

    # ── 3. Employer check ─────────────────────────────────────────────────────
    employer_check = _check_employers(enriched_docs, issues)
    if employer_check["flag"] == "red":
        score -= _DEDUCT_EMPLOYER

    # ── 4. Health grade ───────────────────────────────────────────────────────
    score = max(0, min(100, score))
    if score >= 80:
        grade, label = "green",  "Submission Ready"
    elif score >= 55:
        grade, label = "yellow", "Needs Review"
    else:
        grade, label = "red",    "Action Required"

    issues.sort(key=lambda x: 0 if x["severity"] == "red" else 1)

    red_cnt = sum(1 for x in issues if x["severity"] == "red")
    yel_cnt = sum(1 for x in issues if x["severity"] == "yellow")

    summary = (
        f"{len(enriched_docs)} document(s) analysed — "
        f"{red_cnt} critical, {yel_cnt} warning(s). "
        f"Score: {score}/100 — {label}."
    )

    return {
        "golden_record":   golden,
        "health_score":    score,
        "health_grade":    grade,
        "health_label":    label,
        "document_checks": doc_checks,
        "employer_check":  employer_check,
        "issues":          issues,
        "summary":         summary,
    }


def _empty_result() -> dict:
    return {
        "golden_record":   {},
        "health_score":    0,
        "health_grade":    "red",
        "health_label":    "Action Required",
        "document_checks": [],
        "employer_check":  {"employers_found": [], "flag": "n/a", "reason": "No documents"},
        "issues":          [],
        "summary":         "No documents to analyse.",
    }
