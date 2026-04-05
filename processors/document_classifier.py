"""
Keyword-based tier classification for Australian mortgage identity documents.

Tier 1 (Anchor):           Australian Passport, Birth Certificate, Citizenship Certificate
Tier 2 (Secondary Primary): Driver's Licence, Foreign Passport + Visa, ImmiCard
Tier 3 (Supporting):       Photo Card, Proof of Age Card
Tier 4 (Contextual):       Bank Statement, PAYG Summary, Tax Return, Payslip, Utility Bill
Tier 5 (Unknown):          Fallback when no rule matches
"""
from typing import NamedTuple, List, Tuple, Optional


class ClassificationResult(NamedTuple):
    doc_type: str
    tier: int


# Each rule: (display_name, tier, required_keywords, any_of_keywords)
# Match condition: ALL required_keywords appear AND (any_of is empty OR at least one any_of appears)
_RULES: List[Tuple[str, int, List[str], List[str]]] = [
    # ── Tier 1 — Anchor ──────────────────────────────────────────────────────
    (
        "Australian Passport", 1,
        ["passport"],
        ["australia", "australian", "commonwealth of australia", "aus"],
    ),
    (
        "Birth Certificate", 1,
        ["birth", "certificate"],
        ["birth certificate", "registry of births", "births deaths and marriages",
         "born in", "date of birth"],
    ),
    (
        "Citizenship Certificate", 1,
        ["citizenship", "certificate"],
        ["australian citizenship", "citizen of australia", "naturalisation"],
    ),
    # ── Tier 2 — Secondary Primary ───────────────────────────────────────────
    (
        "Driver's Licence", 2,
        ["licence"],
        ["driver", "driving", "motor vehicle", "roads and maritime",
         "transport for nsw", "vicroads", "qld transport", "driver licence",
         "driver's licence"],
    ),
    (
        "ImmiCard", 2,
        ["immicard"],
        [],
    ),
    (
        "Foreign Passport + Visa", 2,
        ["passport", "visa"],
        [],
    ),
    # ── Tier 3 — Supporting ──────────────────────────────────────────────────
    (
        "Photo Card", 3,
        ["photo card"],
        [],
    ),
    (
        "Proof of Age Card", 3,
        ["proof of age"],
        [],
    ),
    # ── Tier 4 — Contextual ──────────────────────────────────────────────────
    (
        "Bank Statement", 4,
        ["statement"],
        ["bank", "bsb", "account balance", "transaction history",
         "deposit", "withdrawal", "closing balance"],
    ),
    (
        "PAYG Summary", 4,
        ["payg"],
        ["payment summary", "withholding", "payg summary", "income tax withheld"],
    ),
    (
        "Tax Return", 4,
        ["tax return"],
        ["australian taxation office", "ato", "individual tax return",
         "lodge", "taxable income"],
    ),
    (
        "Payslip", 4,
        ["gross", "net pay"],
        ["pay slip", "payslip", "pay advice", "payroll", "earnings"],
    ),
    (
        "Payslip", 4,
        ["payslip"],
        [],
    ),
    (
        "Payslip", 4,
        ["pay slip"],
        [],
    ),
    (
        "Utility Bill", 4,
        ["electricity"],
        [],
    ),
    (
        "Utility Bill", 4,
        ["gas bill"],
        [],
    ),
    (
        "Utility Bill", 4,
        ["water bill"],
        [],
    ),
    (
        "Utility Bill", 4,
        ["utility", "bill"],
        ["council", "internet", "broadband", "phone"],
    ),
]

_UNKNOWN = ClassificationResult(doc_type="Unknown Document", tier=5)


def classify_document(full_text: str) -> ClassificationResult:
    """
    Classify a document by scanning its OCR full text for known keyword patterns.
    Returns the highest-authority (lowest tier number) match.
    Falls back to Tier 5 Unknown if no rule matches.
    """
    lower = full_text.lower()
    best = _UNKNOWN

    for doc_type, tier, required, any_of in _RULES:
        # Skip rules that can't beat our current best
        if tier >= best.tier:
            continue
        # All required keywords must be present
        if not all(kw in lower for kw in required):
            continue
        # At least one any_of keyword must be present (if list is non-empty)
        if any_of and not any(kw in lower for kw in any_of):
            continue
        best = ClassificationResult(doc_type=doc_type, tier=tier)

    return best
