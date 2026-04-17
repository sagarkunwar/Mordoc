"""Case management routes."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import json as _json_mod
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
import io

from database import get_db, log_audit
from auth import get_current_user

router = APIRouter()


# ── helpers ───────────────────────────────────────────────────────────────────

def _case_row_to_dict(row) -> dict:
    return {
        "id":             row["id"],
        "client_name":    row["client_name"],
        "anchor_doc_type":row["anchor_doc_type"],
        "anchor_name":    row["anchor_name"],
        "status":         row["status"],
        "doc_count":      row["doc_count"],
        "created_at":     row["created_at"],
        "updated_at":     row["updated_at"],
    }


def _enrich_documents(db, case_id: int) -> tuple[list, list]:
    """
    Returns (enriched_docs, file_blobs).
    enriched_docs: list of dicts ready for the report / frontend
    file_blobs:    raw bytes (redacted if stored, else original) per doc
    """
    cd_rows = db.execute(
        "SELECT * FROM case_documents WHERE case_id=? ORDER BY added_at",
        (case_id,)
    ).fetchall()

    enriched = []
    blobs    = []

    for cd in cd_rows:
        doc = db.execute(
            "SELECT * FROM documents WHERE id=?", (cd["document_id"],)
        ).fetchone()
        if not doc:
            continue

        tfns = db.execute(
            "SELECT formatted, page_number, confidence, normalized FROM tfns WHERE document_id=?",
            (doc["id"],)
        ).fetchall()
        names = db.execute(
            "SELECT name FROM names WHERE document_id=?", (doc["id"],)
        ).fetchall()

        enriched.append({
            "case_document_id": cd["id"],
            "document_id":      doc["id"],
            "filename":         doc["filename"],
            "doc_type":         doc["doc_type"] or "Unknown Document",
            "tier":             doc["tier"] or 5,
            "tfn_count":        doc["tfn_count"] or 0,
            "name_count":       doc["name_count"] or 0,
            "status":           doc["status"],
            "file_size":        doc["file_size"],
            "created_at":       doc["created_at"],
            "is_redacted":      bool(cd["is_redacted"]),
            "flag":             "",   # filled in below
            "extracted_data":   _json_mod.loads(doc["extracted_data"]) if doc["extracted_data"] else {},
            "tfns": [
                {"formatted": t["formatted"], "page": t["page_number"],
                 "confidence": int((t["confidence"] or 0) * 100),
                 "normalized": t["normalized"]}
                for t in tfns
            ],
            "names": [n["name"] for n in names],
        })

        # Prefer redacted bytes, fall back to original
        blob = cd["redacted_bytes"] if cd["is_redacted"] and cd["redacted_bytes"] else doc["file_bytes"]
        blobs.append(blob)

    return enriched, blobs


def _run_anchor_analysis(enriched_docs: list) -> dict | None:
    """Re-run anchor analysis over the case's documents."""
    from processors.document_classifier import ClassificationResult
    from processors.name_comparator import analyse_packet, DocumentResult as NcDocResult

    # Build lightweight DocumentResult-like objects
    class _DR:
        def __init__(self, d):
            self.filename  = d["filename"]
            self.doc_type  = d["doc_type"]
            self.tier      = d["tier"]
            self.names     = d["names"]
            self.all_tfns  = []   # not needed for name analysis
            self.total_pages = 0
            self.status    = d["status"]
            self.error     = None

    fake_results = [_DR(d) for d in enriched_docs]
    from processors.name_comparator import analyse_packet
    packet = analyse_packet(fake_results)

    if not packet:
        return None

    # Annotate docs with flag
    for comp in packet.comparisons:
        if comp.doc_index < len(enriched_docs):
            enriched_docs[comp.doc_index]["flag"] = comp.flag

    return {
        "anchor_index":    packet.anchor_index,
        "anchor_filename": packet.anchor_filename,
        "anchor_doc_type": packet.anchor_doc_type,
        "anchor_tier":     packet.anchor_tier,
        "anchor_name":     packet.anchor_name,
        "comparisons": [
            {
                "doc_index":       c.doc_index,
                "filename":        c.filename,
                "names_found":     c.names_found,
                "best_match_name": c.best_match_name,
                "best_score":      round(c.best_score, 1),
                "flag":            c.flag,
                "reason":          c.reason,
            }
            for c in packet.comparisons
        ],
    }


# ── routes ────────────────────────────────────────────────────────────────────

@router.post("/create")
async def create_case(body: dict, user: dict = Depends(get_current_user)):
    """Create a new case. Body: { client_name: str }"""
    client_name = (body.get("client_name") or "").strip()
    if not client_name:
        raise HTTPException(status_code=400, detail="client_name is required.")

    db = get_db()
    cursor = db.execute(
        "INSERT INTO cases (client_name) VALUES (?)", (client_name,)
    )
    case_id = cursor.lastrowid
    db.commit()

    case = db.execute("SELECT * FROM cases WHERE id=?", (case_id,)).fetchone()
    db.close()

    log_audit("case_create", f"Case #{case_id} — {client_name}")
    return {"case": _case_row_to_dict(case)}


@router.get("/list")
def list_cases(user: dict = Depends(get_current_user)):
    """List all cases, newest first."""
    db = get_db()
    rows = db.execute("SELECT * FROM cases ORDER BY created_at DESC").fetchall()
    db.close()
    return {"cases": [_case_row_to_dict(r) for r in rows]}


@router.get("/{case_id}")
def get_case(case_id: int, user: dict = Depends(get_current_user)):
    """Return a single case with its documents and anchor analysis."""
    db = get_db()
    case = db.execute("SELECT * FROM cases WHERE id=?", (case_id,)).fetchone()
    if not case:
        db.close()
        raise HTTPException(status_code=404, detail="Case not found.")

    enriched, _ = _enrich_documents(db, case_id)
    db.close()

    from processors.case_analyser import analyse_case
    anchor   = _run_anchor_analysis(enriched) if enriched else None
    analysis = analyse_case(enriched) if enriched else None

    return {
        "case":      _case_row_to_dict(case),
        "documents": enriched,
        "anchor":    anchor,
        "analysis":  analysis,
    }


@router.post("/{case_id}/documents")
async def add_document_to_case(
    case_id: int,
    body: dict,
    user: dict = Depends(get_current_user),
):
    """
    Link an already-processed document to a case.
    Body: { document_id: int }
    """
    doc_id = body.get("document_id")
    if not doc_id:
        raise HTTPException(status_code=400, detail="document_id is required.")

    db = get_db()
    case = db.execute("SELECT * FROM cases WHERE id=?", (case_id,)).fetchone()
    if not case:
        db.close()
        raise HTTPException(status_code=404, detail="Case not found.")

    doc = db.execute("SELECT id, filename FROM documents WHERE id=?", (doc_id,)).fetchone()
    if not doc:
        db.close()
        raise HTTPException(status_code=404, detail="Document not found.")

    # Prevent duplicates
    existing = db.execute(
        "SELECT id FROM case_documents WHERE case_id=? AND document_id=?",
        (case_id, doc_id)
    ).fetchone()
    if existing:
        db.close()
        raise HTTPException(status_code=409, detail="Document already in this case.")

    db.execute(
        "INSERT INTO case_documents (case_id, document_id) VALUES (?,?)",
        (case_id, doc_id)
    )
    db.execute(
        "UPDATE cases SET doc_count = doc_count + 1, updated_at = datetime('now','localtime') WHERE id=?",
        (case_id,)
    )
    db.commit()
    db.close()

    log_audit("case_add_doc", f"Case #{case_id} ← doc #{doc_id} ({doc['filename']})")
    return {"ok": True}


@router.post("/{case_id}/documents/{case_doc_id}/redact")
async def store_redacted_for_case(
    case_id: int,
    case_doc_id: int,
    body: dict,
    user: dict = Depends(get_current_user),
):
    """
    Store redacted PDF bytes against a case_document record.
    Body: { document_id: int, redact_tfns: [normalized, ...] }
    Uses the same redaction logic as documents.py but saves result into case_documents.
    """
    import fitz

    doc_id      = body.get("document_id")
    redact_tfns = set(body.get("redact_tfns", []))
    if not redact_tfns:
        raise HTTPException(status_code=400, detail="No TFNs specified.")

    db = get_db()

    cd = db.execute(
        "SELECT * FROM case_documents WHERE id=? AND case_id=?", (case_doc_id, case_id)
    ).fetchone()
    if not cd:
        db.close()
        raise HTTPException(status_code=404, detail="Case document not found.")

    doc_row = db.execute(
        "SELECT filename, file_bytes FROM documents WHERE id=?", (cd["document_id"],)
    ).fetchone()
    if not doc_row or not doc_row["file_bytes"]:
        db.close()
        raise HTTPException(status_code=422, detail="Original file not stored.")

    tfn_rows = db.execute(
        "SELECT normalized, bounding_boxes FROM tfns WHERE document_id=?",
        (cd["document_id"],)
    ).fetchall()

    import json as _json
    boxes_to_redact = []
    for row in tfn_rows:
        if row["normalized"] not in redact_tfns:
            continue
        if not row["bounding_boxes"]:
            continue
        for b in _json.loads(row["bounding_boxes"]):
            boxes_to_redact.append(b)

    filename = doc_row["filename"]
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "pdf"
    file_bytes = doc_row["file_bytes"]

    if ext in ("jpg", "jpeg", "png", "tiff", "tif", "bmp", "webp"):
        import io as _io
        img_doc = fitz.open(stream=file_bytes, filetype=ext)
        pdf_bytes_io = _io.BytesIO(img_doc.convert_to_pdf())
        pdf_bytes_io.seek(0)
        pdf_bytes = pdf_bytes_io.read()
        img_doc.close()
    else:
        pdf_bytes = file_bytes

    pdf = fitz.open(stream=pdf_bytes, filetype="pdf")
    for page in pdf:
        page_num  = page.number + 1
        page_rect = page.rect
        w, h = page_rect.width, page_rect.height
        for b in boxes_to_redact:
            if b["page"] != page_num:
                continue
            pad = 3
            rect = fitz.Rect(
                b["x"] * w - pad, b["y"] * h - pad,
                (b["x"] + b["width"]) * w + pad,
                (b["y"] + b["height"]) * h + pad,
            )
            page.add_redact_annot(rect, fill=(0, 0, 0))
        page.apply_redactions()

    redacted_bytes = pdf.tobytes(garbage=4, deflate=True)
    pdf.close()

    db.execute(
        "UPDATE case_documents SET is_redacted=1, redacted_bytes=? WHERE id=?",
        (redacted_bytes, case_doc_id)
    )
    db.commit()
    db.close()

    log_audit("case_redact", f"Case #{case_id} doc #{case_doc_id} — {len(redact_tfns)} TFN(s) redacted")
    return {"ok": True}


@router.get("/{case_id}/report")
def download_report(case_id: int, user: dict = Depends(get_current_user)):
    """Generate and stream the unified PDF report for this case."""
    from processors.report_generator import generate_case_report

    db = get_db()
    case = db.execute("SELECT * FROM cases WHERE id=?", (case_id,)).fetchone()
    if not case:
        db.close()
        raise HTTPException(status_code=404, detail="Case not found.")

    enriched, blobs = _enrich_documents(db, case_id)

    audit_rows = db.execute(
        "SELECT * FROM audit_log ORDER BY created_at DESC LIMIT 100"
    ).fetchall()

    db.close()

    from processors.case_analyser import analyse_case
    analysis = analyse_case(enriched) if enriched else {}

    pdf_bytes = generate_case_report(
        case       = dict(case),
        documents  = enriched,
        file_blobs = blobs,
        analysis   = analysis,
        audit_rows = [dict(r) for r in audit_rows],
    )

    client_slug = case["client_name"].replace(" ", "_").lower()
    out_name    = f"case_{case_id}_{client_slug}_report.pdf"

    log_audit("case_report", f"Case #{case_id} — report downloaded")

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{out_name}"'},
    )


@router.get("/{case_id}/extracted")
def get_extracted_data(case_id: int, user: dict = Depends(get_current_user)):
    """
    Return a structured JSON map of all extracted fields for every document in the case.
    Shape: { case_id, case_slug, extracted_data: { doc_key: { ...fields } } }
    """
    db = get_db()
    case = db.execute("SELECT * FROM cases WHERE id=?", (case_id,)).fetchone()
    if not case:
        db.close()
        raise HTTPException(status_code=404, detail="Case not found.")

    enriched, _ = _enrich_documents(db, case_id)
    db.close()

    extracted_map = {}
    type_counts: dict[str, int] = {}
    for doc in enriched:
        raw_type = doc.get("doc_type", "unknown_document")
        # Build a safe snake_case key from the doc type, deduplicated
        key_base = raw_type.lower().replace(" ", "_").replace("-", "_").replace("/", "_")
        key_base = "".join(c for c in key_base if c.isalnum() or c == "_")
        count = type_counts.get(key_base, 0) + 1
        type_counts[key_base] = count
        key = key_base if count == 1 else f"{key_base}_{count}"
        extracted_map[key] = doc.get("extracted_data") or {}

    slug = f"{case_id}_{case['client_name'].replace(' ', '_').upper()}"
    return {
        "case_id":       slug,
        "extracted_data": extracted_map,
    }


@router.delete("/{case_id}")
def delete_case(case_id: int, user: dict = Depends(get_current_user)):
    """Delete a case (documents are NOT deleted, only the case linkage)."""
    db = get_db()
    case = db.execute("SELECT client_name FROM cases WHERE id=?", (case_id,)).fetchone()
    if not case:
        db.close()
        raise HTTPException(status_code=404, detail="Case not found.")

    db.execute("DELETE FROM case_documents WHERE case_id=?", (case_id,))
    db.execute("DELETE FROM cases WHERE id=?", (case_id,))
    db.commit()
    db.close()

    log_audit("case_delete", f"Case #{case_id} — {case['client_name']}")
    return {"ok": True}
