"""
Primary Identity Anchor — name comparison engine.

Selects the highest-tier document in a packet as the Anchor, extracts its
primary name, then fuzzy-matches that name against every other document.

Flags:
  green    — token_sort_ratio >= 95  (exact / near-exact)
  yellow   — ratio >= 70  OR  same surname (partial / nickname)
  red      — ratio <  70  AND different surname (major discrepancy)
  no_names — the compared document has no extracted names
"""
from dataclasses import dataclass, field
from typing import List, Optional, Any


@dataclass
class NameComparison:
    doc_index: int
    filename: str
    names_found: List[str]
    best_match_name: Optional[str]
    best_score: float
    flag: str   # "green" | "yellow" | "red" | "no_names"
    reason: str


@dataclass
class PacketAnalysis:
    anchor_index: int
    anchor_filename: str
    anchor_doc_type: str
    anchor_tier: int
    anchor_name: Optional[str]
    comparisons: List[NameComparison] = field(default_factory=list)


def _surname(name: str) -> str:
    parts = name.strip().split()
    return parts[-1].lower() if parts else ""


def _compare(anchor_name: str, candidates: List[str]):
    """Return (best_score, best_name) using rapidfuzz token_sort_ratio."""
    from rapidfuzz import fuzz
    best_score = 0.0
    best_name: Optional[str] = None
    for c in candidates:
        s = fuzz.token_sort_ratio(anchor_name.lower(), c.lower())
        if s > best_score:
            best_score, best_name = s, c
    return best_score, best_name


def _flag_and_reason(score: float, anchor_name: str, best_name: Optional[str]):
    anchor_sn = _surname(anchor_name)
    cand_sn   = _surname(best_name) if best_name else ""
    same_sn   = bool(anchor_sn and cand_sn and anchor_sn == cand_sn)

    if score >= 95:
        return "green", f"Exact match ({score:.0f}%)"
    if score >= 70 or same_sn:
        reason = f"Partial match ({score:.0f}%)"
        if not same_sn:
            reason += " — surnames differ"
        return "yellow", reason
    reason = f"Major discrepancy ({score:.0f}%)"
    if not same_sn:
        reason += " — different surname"
    return "red", reason


def analyse_packet(results: List[Any]) -> Optional[PacketAnalysis]:
    """
    Accepts a list of DocumentResult objects (must have .filename, .names,
    .tier, .doc_type attributes).

    Returns a PacketAnalysis, or None if the list is empty.
    """
    if not results:
        return None

    # Anchor = lowest tier number; ties broken by upload order
    anchor_index = min(range(len(results)), key=lambda i: results[i].tier)
    anchor = results[anchor_index]
    anchor_name = anchor.names[0] if anchor.names else None

    comparisons: List[NameComparison] = []

    for i, doc in enumerate(results):
        if i == anchor_index:
            comparisons.append(NameComparison(
                doc_index=i,
                filename=doc.filename,
                names_found=doc.names,
                best_match_name=anchor_name,
                best_score=100.0,
                flag="green",
                reason="Anchor document",
            ))
            continue

        if not doc.names:
            comparisons.append(NameComparison(
                doc_index=i,
                filename=doc.filename,
                names_found=[],
                best_match_name=None,
                best_score=0.0,
                flag="no_names",
                reason="No names extracted from this document",
            ))
            continue

        if not anchor_name:
            comparisons.append(NameComparison(
                doc_index=i,
                filename=doc.filename,
                names_found=doc.names,
                best_match_name=None,
                best_score=0.0,
                flag="yellow",
                reason="Anchor has no name — manual review required",
            ))
            continue

        best_score, best_name = _compare(anchor_name, doc.names)
        flag, reason = _flag_and_reason(best_score, anchor_name, best_name)

        comparisons.append(NameComparison(
            doc_index=i,
            filename=doc.filename,
            names_found=doc.names,
            best_match_name=best_name,
            best_score=best_score,
            flag=flag,
            reason=reason,
        ))

    return PacketAnalysis(
        anchor_index=anchor_index,
        anchor_filename=anchor.filename,
        anchor_doc_type=anchor.doc_type,
        anchor_tier=anchor.tier,
        anchor_name=anchor_name,
        comparisons=comparisons,
    )
