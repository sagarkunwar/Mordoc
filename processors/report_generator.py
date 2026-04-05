"""
Unified PDF report generator for a Case.

Produces a single PDF with:
  - Cover page  (case metadata, anchor, doc list)
  - Audit table (all documents, TFN counts, name-match flags)
  - Appended pages from each document (redacted version if available, original otherwise)
"""
from __future__ import annotations

import io
import textwrap
from datetime import datetime
from typing import Optional

import fitz  # pymupdf


# ── colour palette ────────────────────────────────────────────────────────────
_GREEN  = (0.18, 0.64, 0.38)
_YELLOW = (0.93, 0.70, 0.13)
_RED    = (0.83, 0.23, 0.23)
_DARK   = (0.13, 0.13, 0.20)
_MID    = (0.40, 0.40, 0.50)
_LIGHT  = (0.95, 0.95, 0.97)
_WHITE  = (1.00, 1.00, 1.00)
_ACCENT = (0.24, 0.39, 0.93)   # brand blue


def _flag_colour(flag: Optional[str]):
    if flag == "green":
        return _GREEN
    if flag == "yellow":
        return _YELLOW
    return _RED


def _tier_label(tier: int) -> str:
    labels = {1: "Tier 1 – Primary ID", 2: "Tier 2 – Secondary ID",
               3: "Tier 3 – Photo ID", 4: "Tier 4 – Supporting", 5: "Tier 5 – Unknown"}
    return labels.get(tier, f"Tier {tier}")


# ── internal helpers ──────────────────────────────────────────────────────────

def _new_page(doc: fitz.Document, width: float = 595, height: float = 842) -> fitz.Page:
    return doc.new_page(width=width, height=height)


def _rect(x, y, w, h) -> fitz.Rect:
    return fitz.Rect(x, y, x + w, y + h)


def _filled_rect(page: fitz.Page, rect: fitz.Rect, colour):
    page.draw_rect(rect, color=colour, fill=colour)


def _text(page: fitz.Page, text: str, x: float, y: float,
          fontsize: float = 10, colour=(0, 0, 0), bold: bool = False):
    fontname = "helv" if not bold else "hebo"
    page.insert_text((x, y), text, fontname=fontname, fontsize=fontsize, color=colour)


def _wrapped_text(page: fitz.Page, text: str, x: float, y: float, max_width: float,
                  fontsize: float = 9, colour=(0, 0, 0)) -> float:
    """Insert wrapped text; returns the y position after the last line."""
    words = text.split()
    line = ""
    line_h = fontsize + 2
    for word in words:
        test = (line + " " + word).strip()
        # rough char-width estimate: fontsize * 0.55
        if len(test) * fontsize * 0.55 > max_width and line:
            _text(page, line, x, y, fontsize=fontsize, colour=colour)
            y += line_h
            line = word
        else:
            line = test
    if line:
        _text(page, line, x, y, fontsize=fontsize, colour=colour)
        y += line_h
    return y


# ── cover page ────────────────────────────────────────────────────────────────

def _build_cover(report: fitz.Document, case: dict, documents: list, anchor: Optional[dict]):
    page = _new_page(report)
    W, H = 595, 842

    # Header band
    _filled_rect(page, _rect(0, 0, W, 90), _DARK)
    _text(page, "MortgageDoc AI", 36, 38, fontsize=22, colour=_WHITE, bold=True)
    _text(page, "Unified Case Report", 36, 62, fontsize=12, colour=(0.7, 0.75, 1.0))

    # Accent stripe
    _filled_rect(page, _rect(0, 90, W, 4), _ACCENT)

    y = 120
    # Case info block
    _text(page, "CASE DETAILS", 36, y, fontsize=8, colour=_MID, bold=True)
    y += 18
    _text(page, f"Client Name:", 36, y, fontsize=10, colour=_MID)
    _text(page, case.get("client_name", "—"), 150, y, fontsize=10, colour=_DARK, bold=True)
    y += 18
    _text(page, f"Case ID:", 36, y, fontsize=10, colour=_MID)
    _text(page, f"#{case['id']}", 150, y, fontsize=10, colour=_DARK)
    y += 18
    _text(page, f"Created:", 36, y, fontsize=10, colour=_MID)
    _text(page, case.get("created_at", "—"), 150, y, fontsize=10, colour=_DARK)
    y += 18
    _text(page, f"Status:", 36, y, fontsize=10, colour=_MID)
    _text(page, case.get("status", "open").upper(), 150, y, fontsize=10, colour=_DARK)
    y += 18
    _text(page, f"Documents:", 36, y, fontsize=10, colour=_MID)
    _text(page, str(len(documents)), 150, y, fontsize=10, colour=_DARK)
    y += 18
    _text(page, f"Report generated:", 36, y, fontsize=10, colour=_MID)
    _text(page, datetime.now().strftime("%d %b %Y %H:%M"), 150, y, fontsize=10, colour=_DARK)

    # Anchor box
    if anchor:
        y += 30
        _filled_rect(page, _rect(30, y, W - 60, 80), _LIGHT)
        page.draw_rect(_rect(30, y, W - 60, 80), color=_ACCENT, width=1)
        _text(page, "PRIMARY IDENTITY ANCHOR", 44, y + 14, fontsize=8, colour=_ACCENT, bold=True)
        _text(page, anchor.get("anchor_filename", "—"), 44, y + 30, fontsize=11, colour=_DARK, bold=True)
        _text(page, anchor.get("anchor_doc_type", "—"), 44, y + 46, fontsize=9, colour=_MID)
        _text(page, f"Anchor Name: {anchor.get('anchor_name', '—')}", 44, y + 62, fontsize=9, colour=_DARK)
        y += 100

    # Document table header
    y += 10
    _text(page, "DOCUMENT SUMMARY", 36, y, fontsize=8, colour=_MID, bold=True)
    y += 16

    col_x = [36, 220, 320, 390, 460]
    headers = ["Filename", "Doc Type", "TFNs", "Names", "Flag"]
    _filled_rect(page, _rect(30, y - 12, W - 60, 18), _DARK)
    for i, h in enumerate(headers):
        _text(page, h, col_x[i], y, fontsize=8, colour=_WHITE, bold=True)
    y += 10

    for idx, doc in enumerate(documents):
        bg = _LIGHT if idx % 2 == 0 else _WHITE
        _filled_rect(page, _rect(30, y - 10, W - 60, 16), bg)

        fn = doc.get("filename", "")
        if len(fn) > 28:
            fn = fn[:25] + "…"
        dt = doc.get("doc_type", "—")
        if len(dt) > 18:
            dt = dt[:15] + "…"

        flag = doc.get("flag", "")
        fc = _flag_colour(flag) if flag else _MID

        _text(page, fn, col_x[0], y, fontsize=7, colour=_DARK)
        _text(page, dt, col_x[1], y, fontsize=7, colour=_DARK)
        _text(page, str(doc.get("tfn_count", 0)), col_x[2], y, fontsize=7, colour=_DARK)
        _text(page, str(doc.get("name_count", 0)), col_x[3], y, fontsize=7, colour=_DARK)
        _text(page, (flag or "—").upper(), col_x[4], y, fontsize=7, colour=fc, bold=True)
        y += 16

        if y > H - 60:
            page = _new_page(report)
            y = 60

    # Footer
    _filled_rect(page, _rect(0, H - 30, W, 30), _DARK)
    _text(page, "CONFIDENTIAL — MortgageDoc AI   |   Generated for internal compliance use only",
          36, H - 12, fontsize=7, colour=(0.7, 0.7, 0.8))


# ── audit page ────────────────────────────────────────────────────────────────

def _build_audit(report: fitz.Document, audit_rows: list):
    W, H = 595, 842
    page = _new_page(report)

    _filled_rect(page, _rect(0, 0, W, 50), _DARK)
    _text(page, "Audit Log", 36, 32, fontsize=16, colour=_WHITE, bold=True)
    _filled_rect(page, _rect(0, 50, W, 3), _ACCENT)

    y = 80
    col_x = [36, 160, 400]
    headers = ["Time", "Action", "Detail"]
    _filled_rect(page, _rect(30, y - 12, W - 60, 18), _DARK)
    for i, h in enumerate(headers):
        _text(page, h, col_x[i], y, fontsize=8, colour=_WHITE, bold=True)
    y += 12

    for idx, row in enumerate(audit_rows):
        bg = _LIGHT if idx % 2 == 0 else _WHITE
        _filled_rect(page, _rect(30, y - 10, W - 60, 16), bg)

        ts = str(row.get("created_at", ""))[:16]
        action = str(row.get("action", ""))
        detail = str(row.get("detail", ""))
        if len(detail) > 55:
            detail = detail[:52] + "…"

        _text(page, ts,     col_x[0], y, fontsize=7, colour=_DARK)
        _text(page, action, col_x[1], y, fontsize=7, colour=_DARK)
        _text(page, detail, col_x[2], y, fontsize=7, colour=_MID)
        y += 16

        if y > H - 40:
            page = _new_page(report)
            y = 60

    _filled_rect(page, _rect(0, H - 30, W, 30), _DARK)
    _text(page, "CONFIDENTIAL — MortgageDoc AI",
          36, H - 12, fontsize=7, colour=(0.7, 0.7, 0.8))


# ── separator page ────────────────────────────────────────────────────────────

def _build_separator(report: fitz.Document, doc: dict, page_index: int):
    W, H = 595, 842
    page = _new_page(report)

    _filled_rect(page, _rect(0, 0, W, H), _LIGHT)
    _filled_rect(page, _rect(0, H // 2 - 80, W, 160), _DARK)

    fn = doc.get("filename", "")
    _text(page, f"Document {page_index}", W // 2 - 40, H // 2 - 52,
          fontsize=10, colour=(0.6, 0.65, 1.0))
    _text(page, fn, W // 2 - min(len(fn) * 4, 250), H // 2 - 28,
          fontsize=14, colour=_WHITE, bold=True)
    _text(page, doc.get("doc_type", "Unknown Document"), W // 2 - 80, H // 2 + 4,
          fontsize=10, colour=(0.7, 0.75, 1.0))

    tier = doc.get("tier", 5)
    flag = doc.get("flag", "")
    tier_txt = _tier_label(tier)
    flag_txt = f"Name Match: {flag.upper()}" if flag else ""

    _text(page, tier_txt, W // 2 - 60, H // 2 + 28, fontsize=9, colour=_ACCENT)
    if flag_txt:
        fc = _flag_colour(flag)
        _text(page, flag_txt, W // 2 - 55, H // 2 + 46, fontsize=9, colour=fc, bold=True)


# ── public API ────────────────────────────────────────────────────────────────

def generate_case_report(
    case: dict,
    documents: list,          # list of dicts with filename, doc_type, tier, tfn_count, name_count, flag
    file_blobs: list,         # list of (pdf_bytes | None) — one per document, in same order
    anchor: Optional[dict],
    audit_rows: list,
) -> bytes:
    """
    Build and return the merged case report PDF as bytes.

    Parameters
    ----------
    case        : dict from cases table row
    documents   : enriched doc dicts (filename, doc_type, tier, tfn_count, name_count, flag)
    file_blobs  : raw PDF/image bytes for each document (redacted if available, else original)
    anchor      : anchor_payload dict (or None)
    audit_rows  : rows from audit_log table for this case
    """
    report = fitz.open()

    # 1. Cover page
    _build_cover(report, case, documents, anchor)

    # 2. Audit page
    if audit_rows:
        _build_audit(report, audit_rows)

    # 3. Individual document pages
    for idx, (doc, blob) in enumerate(zip(documents, file_blobs), start=1):
        _build_separator(report, doc, idx)

        if blob:
            ext = doc.get("filename", "x.pdf").rsplit(".", 1)[-1].lower()
            filetype = "pdf"
            b = blob

            # Convert images to PDF first
            if ext in ("jpg", "jpeg", "png", "tiff", "tif", "bmp", "webp"):
                try:
                    img_doc = fitz.open(stream=blob, filetype=ext)
                    buf = io.BytesIO(img_doc.convert_to_pdf())
                    img_doc.close()
                    b = buf.read()
                    filetype = "pdf"
                except Exception:
                    b = None

            if b:
                try:
                    src = fitz.open(stream=b, filetype=filetype)
                    report.insert_pdf(src)
                    src.close()
                except Exception:
                    pass

    out = report.tobytes(garbage=4, deflate=True)
    report.close()
    return out
