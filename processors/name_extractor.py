"""
Person name extraction from mortgage document text.

Primary source: Document AI entities (when the processor returns them).
Fallback: regex patterns tuned for Australian mortgage document language.
"""
import re
from typing import List

# Labelled field patterns — highest precision
_LABELLED_PATTERNS = [
    re.compile(
        r'(?:full\s*name|applicant(?:\'?s)?\s*name|borrower(?:\'?s)?\s*name'
        r'|employee(?:\'?s)?\s*name|name\s*of\s*(?:applicant|borrower|employee)'
        r'|customer\s*name|client\s*name)\s*[:\-]\s*'
        r'([A-Z][a-z]{1,20}(?:\s+[A-Z][a-z]{1,20}){1,3})',
        re.IGNORECASE,
    ),
    # "Dear Mr/Mrs/Ms Smith" or "Dear John Smith"
    re.compile(
        r'\bDear\s+(?:Mr\.?\s*|Mrs\.?\s*|Ms\.?\s*|Dr\.?\s*)?'
        r'([A-Z][a-z]{1,20}(?:\s+[A-Z][a-z]{1,20}){0,3})',
        re.IGNORECASE,
    ),
    # Signature block: "Sincerely, John Smith"
    re.compile(
        r'(?:Regards|Sincerely|Yours\s+(?:sincerely|faithfully)),?\s*\n\s*'
        r'([A-Z][a-z]{1,20}(?:\s+[A-Z][a-z]{1,20}){1,3})'
    ),
]

# General title-case name pattern (lower precision — used last)
_GENERAL_PATTERN = re.compile(
    r'\b([A-Z][a-z]{1,20}(?:\s+[A-Z][a-z]{1,20}){1,3})\b'
)

# Phrases that look like names but aren't — exact substring match
_EXCLUSIONS = {
    "Tax Return", "Tax File", "Tax Office", "Date Birth", "Date Of",
    "Bank Statement", "Bank Account", "Loan Application", "Home Loan",
    "Pay Slip", "Pay Stubs", "Total Income", "Gross Income", "Net Income",
    "Phone Number", "Email Address", "Street Address", "Post Code",
    "Account Number", "Reference Number", "Document Number", "File Number",
    "Australian Tax", "Income Tax", "Business Name", "Company Name",
    "Property Address", "Mailing Address", "Employment Status",
    "Credit Score", "Interest Rate", "Loan Amount", "Page Of",
    "Commonwealth Bank", "National Australia", "Westpac Banking",
    "New South Wales", "Western Australia", "South Australia",
    "January", "February", "March", "April", "June", "July",
    "August", "September", "October", "November", "December",
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
    "Saturday", "Sunday",
}


def extract_names_from_text(text: str) -> List[str]:
    """Return a deduplicated list of likely person names from raw text."""
    names: List[str] = []
    seen: set = set()

    def _add(name: str) -> None:
        name = name.strip()
        if len(name) < 5 or name.lower() in seen:
            return
        words = name.split()
        if len(words) < 2:
            return
        if any(len(w) < 2 for w in words):
            return
        if any(excl.lower() in name.lower() for excl in _EXCLUSIONS):
            return
        seen.add(name.lower())
        names.append(name)

    # Labelled patterns first (higher precision)
    for pattern in _LABELLED_PATTERNS:
        for m in pattern.finditer(text):
            _add(m.group(1))

    # General pattern last (lower precision, catches the rest)
    for m in _GENERAL_PATTERN.finditer(text):
        _add(m.group(1))

    return names


def extract_names_from_entities(entities) -> List[str]:
    """Extract person names from Document AI entity objects."""
    _PERSON_TYPES = {
        "person", "person_name", "receiver_name", "supplier_name",
        "payer_name", "employee_name", "applicant_name", "borrower_name",
        "debtor_name", "creditor_name", "guarantor_name",
    }
    names: List[str] = []
    seen: set = set()

    for entity in entities:
        entity_type = (entity.type_ or "").lower()
        if entity_type in _PERSON_TYPES:
            name = (entity.mention_text or "").strip()
            if name and name.lower() not in seen and len(name) >= 3:
                seen.add(name.lower())
                names.append(name)

    return names
