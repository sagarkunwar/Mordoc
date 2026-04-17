"""
File Readiness Certificate — unified PDF report generator.

generate_case_report(case, documents, file_blobs, analysis, audit_rows) -> bytes

Pages:
  1  — File Readiness Certificate (health score, golden record, issue badges)
  2  — Document Compliance Matrix (per-doc flag table)
  3  — Issues & Findings + Employer Verification
  4+ — Audit log (if present)
  N+ — Separator + appended document pages
"""
from __future__ import annotations

import io
import math
from datetime import datetime
from typing import Optional

import fitz  # pymupdf

# ── Colour palette ────────────────────────────────────────────────────────────
_GREEN  = (0.18, 0.64, 0.38)
_YELLOW = (0.93, 0.70, 0.13)
_RED    = (0.83, 0.23, 0.23)
_DARK   = (0.10, 0.12, 0.20)
_MID    = (0.40, 0.40, 0.50)
_LIGHT  = (0.94, 0.95, 0.97)
_WHITE  = (1.00, 1.00, 1.00)
_ACCENT = (0.22, 0.37, 0.92)
_GREY   = (0.60, 0.60, 0.65)

PAGE_W, PAGE_H = 595, 842   # A4 in points


# ── Colour helpers ────────────────────────────────────────────────────────────

def _grade_col(grade: str):
    return {"green": _GREEN, "yellow": _YELLOW, "red": _RED}.get(grade, _GREY)

def _flag_col(flag: str):
    return {"green": _GREEN, "yellow": _YELLOW, "red": _RED}.get(flag, _GREY)


# ── Drawing primitives ────────────────────────────────────────────────────────

def _rect(x, y, w, h) -> fitz.Rect:
    return fitz.Rect(x, y, x + w, y + h)

def _filled(page: fitz.Page, rect: fitz.Rect, colour, radius: float = 0):
    page.draw_rect(rect, color=colour, fill=colour,
                   radius=radius if radius > 0 else None)

def _border(page: fitz.Page, rect: fitz.Rect, colour, width: float = 1):
    page.draw_rect(rect, color=colour, width=width)

def _txt(page: fitz.Page, text: str, x: float, y: float,
         size: float = 10, colour=(0, 0, 0), bold: bool = False):
    page.insert_text((x, y), str(text),
                     fontname="hebo" if bold else "helv",
                     fontsize=size, color=colour)

def _new_page(doc: fitz.Document) -> fitz.Page:
    return doc.new_page(width=PAGE_W, height=PAGE_H)


# ── Watermark ─────────────────────────────────────────────────────────────────

def _watermark(page: fitz.Page):
    """Diagonal CONFIDENTIAL stamp on any page."""
    cx, cy = PAGE_W / 2, PAGE_H / 2
    try:
        tw   = fitz.TextWriter(page.rect, color=_GREY)
        font = fitz.Font("helv")
        tw.append(fitz.Point(cx - 115, cy + 15), "CONFIDENTIAL",
                  fontsize=42, font=font)
        tw.write_text(page, opacity=0.12,
                      morph=(fitz.Point(cx, cy), fitz.Matrix(45)))
    except Exception:
        # Fallback: plain rotated text (some pymupdf versions need different API)
        try:
            page.insert_text(
                (cx - 115, cy + 15), "CONFIDENTIAL",
                fontname="helv", fontsize=42,
                color=(0.80, 0.80, 0.82), rotate=45,
            )
        except Exception:
            pass


# ── Badge helper ──────────────────────────────────────────────────────────────

def _badge(page: fitz.Page, cx: float, cy: float,
           label: str, colour, bw: float = 40, bh: float = 13):
    """Filled pill badge centred at (cx, cy)."""
    rect = fitz.Rect(cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2)
    _filled(page, rect, colour, radius=3)
    txt = label.upper()[:7]
    tx  = cx - len(txt) * 3.0
    page.insert_text((tx, cy + 4), txt, fontname="hebo", fontsize=7, color=_WHITE)


def _flag_badge(page, cx, cy, flag: str, bw=40, bh=13):
    if flag in ("green", "yellow", "red"):
        _badge(page, cx, cy, flag, _flag_col(flag), bw, bh)
    else:
        _badge(page, cx, cy, "N/A", _GREY, bw, bh)


def _footer(page: fitz.Page):
    _filled(page, _rect(0, PAGE_H - 28, PAGE_W, 28), _DARK)
    _txt(page, "CONFIDENTIAL — MortgageDoc AI  |  For internal compliance use only",
         36, PAGE_H - 10, size=7, colour=(0.65, 0.68, 0.85))


# ── Page 1: File Readiness Certificate ───────────────────────────────────────

def _build_cover(report: fitz.Document, case: dict, analysis: dict):
    page = _new_page(report)

    # Header band
    _filled(page, _rect(0, 0, PAGE_W, 88), _DARK)
    _txt(page, "MortgageDoc AI", 36, 34, size=22, colour=_WHITE, bold=True)
    _txt(page, "File Readiness Certificate", 36, 60, size=11, colour=(0.68, 0.72, 0.98))
    _filled(page, _rect(0, 88, PAGE_W, 4), _ACCENT)

    # ── Health score circle ───────────────────────────────────────────────────
    score  = analysis.get("health_score", 0)
    grade  = analysis.get("health_grade", "red")
    hlabel = analysis.get("health_label", "Action Required")
    gcol   = _grade_col(grade)
    cx, cy, r = 490, 155, 50
    page.draw_circle(fitz.Point(cx, cy), r, color=gcol, fill=gcol)
    s_str = str(score)
    page.insert_text((cx - len(s_str) * 9, cy + 11),
                     s_str, fontname="hebo", fontsize=30, color=_WHITE)
    page.insert_text((cx - 13, cy + 27),
                     "/100", fontname="helv", fontsize=9, color=_WHITE)
    lx = cx - len(hlabel) * 3.4
    _txt(page, hlabel, lx, cy + r + 16, size=8, colour=gcol, bold=True)

    # ── Case info (left column) ───────────────────────────────────────────────
    y = 110
    _txt(page, "CASE DETAILS", 36, y, size=7, colour=_MID, bold=True)
    y += 16
    for lbl, val in [
        ("Client",    case.get("client_name", "—")),
        ("Case ID",   f"#{case.get('id', '?')}"),
        ("Status",    (case.get("status") or "open").upper()),
        ("Documents", str(len(analysis.get("document_checks", [])))),
        ("Generated", datetime.now().strftime("%d %b %Y  %H:%M")),
    ]:
        _txt(page, lbl + ":", 36, y, size=9, colour=_MID)
        _txt(page, val, 130, y, size=9, colour=_DARK, bold=True)
        y += 15

    # ── Golden Record box ─────────────────────────────────────────────────────
    gr    = analysis.get("golden_record", {})
    y += 14
    brect = _rect(30, y, PAGE_W - 60, 94)
    _filled(page, brect, _LIGHT)
    _border(page, brect, _ACCENT)
    _txt(page, "GOLDEN RECORD  —  PRIMARY IDENTITY SOURCE",
         44, y + 14, size=7, colour=_ACCENT, bold=True)
    _txt(page, f"Name:    {gr.get('full_name') or '—'}",
         44, y + 30, size=10, colour=_DARK, bold=True)
    _txt(page, f"DOB:     {gr.get('dob') or '—'}",
         44, y + 48, size=9, colour=_DARK)
    addr = (gr.get("address") or "—")[:72]
    _txt(page, f"Address: {addr}", 44, y + 64, size=9, colour=_DARK)
    src = f"{gr.get('source_filename','—')}  ({gr.get('source_doc_type','')})"
    _txt(page, f"Source:  {src[:70]}", 44, y + 80, size=8, colour=_MID)
    y += 112

    # ── Issue count badges ────────────────────────────────────────────────────
    issues  = analysis.get("issues", [])
    red_cnt = sum(1 for x in issues if x["severity"] == "red")
    yel_cnt = sum(1 for x in issues if x["severity"] == "yellow")
    _txt(page, "ISSUE SUMMARY", 36, y, size=7, colour=_MID, bold=True)
    y += 18
    _badge(page, 68,  y, f"{red_cnt} CRITICAL", _RED,    bw=76, bh=20)
    _badge(page, 158, y, f"{yel_cnt} WARNING",  _YELLOW, bw=76, bh=20)
    _badge(page, 248, y, f"{len(analysis.get('document_checks',[]))} DOCS", _ACCENT, bw=64, bh=20)
    y += 36

    # ── Summary line ─────────────────────────────────────────────────────────
    summary = analysis.get("summary", "")
    if summary:
        _txt(page, summary[:105], 36, y, size=8, colour=_MID)
        y += 14
    if len(summary) > 105:
        _txt(page, summary[105:210], 36, y, size=8, colour=_MID)

    _footer(page)
    _watermark(page)


# ── Page 2: Document Compliance Matrix ───────────────────────────────────────

def _build_matrix(report: fitz.Document, analysis: dict):
    page = _new_page(report)
    checks = analysis.get("document_checks", [])

    _filled(page, _rect(0, 0, PAGE_W, 52), _DARK)
    _txt(page, "Document Compliance Matrix", 36, 34, size=16, colour=_WHITE, bold=True)
    _filled(page, _rect(0, 52, PAGE_W, 3), _ACCENT)

    # Column layout: (header, x_start, char_limit)
    COLS = [
        ("#",         30,  14),
        ("Document",  48, 140),
        ("Type",     190,  86),
        ("Tier",     278,  30),
        ("Name",     312,  44),
        ("DOB",      360,  36),
        ("Address",  400,  46),
        ("Freshness",450,  56),
    ]

    y = 74
    _filled(page, _rect(26, y - 12, PAGE_W - 52, 17), _DARK)
    for hdr, cx, _ in COLS:
        _txt(page, hdr, cx, y, size=7, colour=_WHITE, bold=True)
    y += 14

    ROW_H = 20
    for idx, chk in enumerate(checks):
        bg = _LIGHT if idx % 2 == 0 else _WHITE
        _filled(page, _rect(26, y - ROW_H + 7, PAGE_W - 52, ROW_H), bg)

        fn   = (chk.get("filename") or "")[:28]
        dt   = (chk.get("doc_type")  or "")[:18]
        tier = {1:"Tier 1",2:"Tier 2",3:"Tier 3",4:"Tier 4"}.get(chk.get("tier",5),"Tier 5")

        _txt(page, str(idx + 1), COLS[0][1], y, size=7, colour=_MID)
        _txt(page, fn,           COLS[1][1], y, size=7, colour=_DARK)
        _txt(page, dt,           COLS[2][1], y, size=7, colour=_DARK)
        _txt(page, tier,         COLS[3][1], y, size=7, colour=_MID)

        # Flag badges
        for flag_key, col_idx in [
            ("name_flag",      4),
            ("dob_flag",       5),
            ("address_flag",   6),
            ("freshness_flag", 7),
        ]:
            flag = chk.get(flag_key, "n/a") or "n/a"
            col_cx = COLS[col_idx][1] + COLS[col_idx][2] // 2 - 4
            _flag_badge(page, col_cx, y - 4, flag, bw=38, bh=13)

        y += ROW_H
        if y > PAGE_H - 55:
            _footer(page)
            _watermark(page)
            page = _new_page(report)
            _filled(page, _rect(0, 0, PAGE_W, 40), _DARK)
            _txt(page, "Document Compliance Matrix (continued)",
                 36, 26, size=11, colour=_WHITE, bold=True)
            _filled(page, _rect(0, 40, PAGE_W, 2), _ACCENT)
            y = 60

    _footer(page)
    _watermark(page)


# ── Page 3: Issues & Employer Verification ───────────────────────────────────

def _build_issues(report: fitz.Document, analysis: dict):
    page = _new_page(report)

    _filled(page, _rect(0, 0, PAGE_W, 52), _DARK)
    _txt(page, "Issues & Findings", 36, 34, size=16, colour=_WHITE, bold=True)
    _filled(page, _rect(0, 52, PAGE_W, 3), _ACCENT)

    issues = analysis.get("issues", [])
    y = 72

    if not issues:
        _filled(page, _rect(30, y, PAGE_W - 60, 40), (0.92, 0.98, 0.93))
        _border(page, _rect(30, y, PAGE_W - 60, 40), _GREEN)
        _txt(page, "✓  No issues found — document packet is fully compliant.",
             46, y + 24, size=11, colour=_GREEN, bold=True)
        y += 56
    else:
        for severity, section_title in [("red", "Critical Issues"), ("yellow", "Warnings")]:
            group = [x for x in issues if x["severity"] == severity]
            if not group:
                continue

            col = _RED if severity == "red" else _YELLOW
            _txt(page, section_title.upper(), 36, y, size=8, colour=col, bold=True)
            y += 16

            for issue in group:
                if y > PAGE_H - 80:
                    _footer(page)
                    _watermark(page)
                    page = _new_page(report)
                    _filled(page, _rect(0, 0, PAGE_W, 36), _DARK)
                    _txt(page, "Issues & Findings (continued)",
                         36, 24, size=11, colour=_WHITE, bold=True)
                    _filled(page, _rect(0, 36, PAGE_W, 2), _ACCENT)
                    y = 56

                _flag_badge(page, 52, y - 4, severity, bw=44, bh=13)
                cat = (issue.get("category") or "").upper()
                _txt(page, f"[{cat}]", 80, y, size=8, colour=col, bold=True)
                fn_txt = (issue.get("filename") or "")[:30]
                _txt(page, fn_txt, 136, y, size=8, colour=_MID)
                y += 13

                detail = (issue.get("detail") or "")
                max_ch = 96
                while len(detail) > max_ch:
                    _txt(page, detail[:max_ch], 44, y, size=8, colour=_DARK)
                    detail = detail[max_ch:]
                    y += 11
                if detail:
                    _txt(page, detail, 44, y, size=8, colour=_DARK)
                y += 18

            y += 6

    # ── Employer Verification ─────────────────────────────────────────────────
    emp = analysis.get("employer_check", {})
    _txt(page, "EMPLOYER VERIFICATION", 36, y, size=8, colour=_MID, bold=True)
    y += 16
    emp_flag = emp.get("flag", "n/a")
    _flag_badge(page, 52, y - 4, emp_flag, bw=44, bh=14)
    _txt(page, emp.get("reason", "—"), 82, y, size=9, colour=_DARK)
    y += 18

    employers = emp.get("employers_found", [])
    if employers:
        _txt(page, "Employers:  " + ",  ".join(employers[:5]),
             44, y, size=8, colour=_MID)
        y += 14

    _footer(page)
    _watermark(page)


# ── Audit page ────────────────────────────────────────────────────────────────

def _build_audit(report: fitz.Document, audit_rows: list):
    page = _new_page(report)
    _filled(page, _rect(0, 0, PAGE_W, 52), _DARK)
    _txt(page, "Audit Log", 36, 34, size=16, colour=_WHITE, bold=True)
    _filled(page, _rect(0, 52, PAGE_W, 3), _ACCENT)

    COLS = [36, 160, 400]
    y = 74
    _filled(page, _rect(28, y - 12, PAGE_W - 56, 17), _DARK)
    for h, cx in zip(["Time", "Action", "Detail"], COLS):
        _txt(page, h, cx, y, size=8, colour=_WHITE, bold=True)
    y += 14

    for idx, row in enumerate(audit_rows):
        bg = _LIGHT if idx % 2 == 0 else _WHITE
        _filled(page, _rect(28, y - 11, PAGE_W - 56, 16), bg)
        _txt(page, str(row.get("created_at", ""))[:16], COLS[0], y, size=7, colour=_DARK)
        _txt(page, str(row.get("action",     ""))[:20],  COLS[1], y, size=7, colour=_DARK)
        _txt(page, str(row.get("detail",     ""))[:52],  COLS[2], y, size=7, colour=_MID)
        y += 16
        if y > PAGE_H - 40:
            _footer(page)
            _watermark(page)
            page = _new_page(report)
            y = 40

    _footer(page)
    _watermark(page)


# ── Document separator ────────────────────────────────────────────────────────

def _build_separator(report: fitz.Document, doc: dict, page_index: int, check: Optional[dict] = None):
    page = _new_page(report)
    _filled(page, _rect(0, 0, PAGE_W, PAGE_H), _LIGHT)
    _filled(page, _rect(0, PAGE_H // 2 - 90, PAGE_W, 180), _DARK)

    _txt(page, f"Document {page_index}",
         PAGE_W // 2 - 40, PAGE_H // 2 - 64, size=10, colour=(0.60, 0.65, 0.98))

    fn = (doc.get("filename") or "")[:55]
    _txt(page, fn, PAGE_W // 2 - min(len(fn) * 4, 240),
         PAGE_H // 2 - 38, size=14, colour=_WHITE, bold=True)

    dt = doc.get("doc_type", "Unknown Document")
    _txt(page, dt, PAGE_W // 2 - min(len(dt) * 3, 150),
         PAGE_H // 2 - 8, size=10, colour=(0.68, 0.72, 0.98))

    tier_map = {1:"Tier 1 – Primary ID", 2:"Tier 2 – Secondary ID",
                3:"Tier 3 – Photo ID",   4:"Tier 4 – Supporting", 5:"Tier 5 – Unknown"}
    tier_txt = tier_map.get(doc.get("tier", 5), "Tier 5 – Unknown")
    _txt(page, tier_txt, PAGE_W // 2 - 70, PAGE_H // 2 + 20, size=9, colour=_ACCENT)

    if check:
        parts = []
        for key, lbl in [("name_flag","Name"), ("dob_flag","DOB"), ("address_flag","Addr"), ("freshness_flag","Fresh")]:
            f = check.get(key, "n/a") or "n/a"
            parts.append(f"{lbl}: {f.upper()}")
        _txt(page, "  |  ".join(parts),
             PAGE_W // 2 - 120, PAGE_H // 2 + 44, size=8, colour=_GREY)

    _watermark(page)


# ── Public API ────────────────────────────────────────────────────────────────

def generate_case_report(
    case: dict,
    documents: list,
    file_blobs: list,
    analysis: dict,
    audit_rows: list,
) -> bytes:
    """
    Build and return the complete case PDF as bytes.

    Parameters
    ----------
    case       : dict from cases table row
    documents  : enriched doc dicts (filename, doc_type, tier, extracted_data, ...)
    file_blobs : raw bytes per document (redacted if available, else original)
    analysis   : result of processors.case_analyser.analyse_case()
    audit_rows : rows from audit_log table
    """
    report = fitz.open()

    doc_checks = analysis.get("document_checks", [])

    # Page 1: Certificate cover
    _build_cover(report, case, analysis)

    # Page 2: Compliance Matrix
    _build_matrix(report, analysis)

    # Page 3: Issues & Employer check
    _build_issues(report, analysis)

    # Audit log
    if audit_rows:
        _build_audit(report, audit_rows)

    # Separator + document pages
    for idx, (doc, blob) in enumerate(zip(documents, file_blobs), start=1):
        check = doc_checks[idx - 1] if idx - 1 < len(doc_checks) else None
        _build_separator(report, doc, idx, check)

        if blob:
            ext = (doc.get("filename") or "x.pdf").rsplit(".", 1)[-1].lower()
            b   = blob
            if ext in ("jpg", "jpeg", "png", "tiff", "tif", "bmp", "webp"):
                try:
                    img_doc = fitz.open(stream=blob, filetype=ext)
                    buf = io.BytesIO(img_doc.convert_to_pdf())
                    img_doc.close()
                    b = buf.read()
                except Exception:
                    b = None
            if b:
                try:
                    pre_count = len(report)
                    src = fitz.open(stream=b, filetype="pdf")
                    report.insert_pdf(src)
                    src.close()
                    # Apply watermark to the newly inserted pages
                    for pi in range(pre_count, len(report)):
                        _watermark(report[pi])
                except Exception:
                    pass

    out = report.tobytes(garbage=4, deflate=True)
    report.close()
    return out
