"""
TFN detection and validation for Australian Tax File Numbers.

Format: 9 digits, written as XXX XXX XXX or XXXXXXXXX.
Validation: weighted checksum where sum(digit × weight) must be divisible by 11.
Weights (ATO specification): 1, 4, 3, 7, 5, 8, 6, 9, 10
"""
import re
from dataclasses import dataclass, field
from typing import List

# ATO-specified check digit weights
_WEIGHTS = [1, 4, 3, 7, 5, 8, 6, 9, 10]

# Both common formats: "XXX XXX XXX" (with space or tab) and "XXXXXXXXX"
# [\s] covers space, tab, and newline (PDFs sometimes break digits across lines)
_TFN_PATTERNS = [
    re.compile(r'\b(\d{3}[\s]\d{3}[\s]\d{3})\b'),
    re.compile(r'\b(\d{9})\b'),
]


@dataclass
class BoundingBox:
    """Normalised bounding box (0.0–1.0) for a token on a page.
    Stored now so Prompt 2 redaction can use them without re-processing."""
    x: float
    y: float
    width: float
    height: float
    page: int


@dataclass
class TFNMatch:
    raw: str           # exactly as found in text
    normalized: str    # 9 digits, no spaces
    formatted: str     # XXX XXX XXX canonical form
    page_number: int
    is_valid: bool     # passed check digit algorithm
    confidence: float  # 0.0–1.0
    bounding_boxes: List[BoundingBox] = field(default_factory=list)


def validate_tfn_checksum(digits: str) -> bool:
    """Return True if 9-digit string passes the ATO check digit algorithm."""
    if len(digits) != 9 or not digits.isdigit():
        return False
    total = sum(int(digits[i]) * _WEIGHTS[i] for i in range(9))
    return total % 11 == 0


def format_tfn(digits: str) -> str:
    d = digits.replace(" ", "")
    return f"{d[:3]} {d[3:6]} {d[6:]}"


def extract_tfns_from_text(text: str, page_number: int = 1) -> List[TFNMatch]:
    """
    Find all TFN candidates in a text block and validate each one.

    Returns every match — both valid (high confidence) and invalid (low confidence)
    so the UI can show confidence levels and let the operator decide.
    """
    results: List[TFNMatch] = []
    seen: set = set()

    for pattern in _TFN_PATTERNS:
        for m in pattern.finditer(text):
            raw = m.group(1)
            normalized = raw.replace(" ", "").replace("\t", "").replace("\n", "")

            if normalized in seen:
                continue
            # Skip obviously invalid patterns (all same digit)
            if len(set(normalized)) == 1:
                continue

            seen.add(normalized)
            is_valid = validate_tfn_checksum(normalized)
            # A valid checksum reduces false-positive probability to ~1/11 (~9%)
            # Without validation it would be much higher for plain 9-digit matches
            confidence = 0.93 if is_valid else 0.22

            results.append(TFNMatch(
                raw=raw,
                normalized=normalized,
                formatted=format_tfn(normalized),
                page_number=page_number,
                is_valid=is_valid,
                confidence=confidence,
            ))

    return results
