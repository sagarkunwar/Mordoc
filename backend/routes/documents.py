"""Document processing routes."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import json
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from typing import List
import io

from processors.document_ai import process_document_with_ocr
from processors.data_extractor import extract_structured_data
from database import get_db, log_audit
from auth import get_current_user

router = APIRouter()


@router.post("/process")
async def process_documents(files: List[UploadFile] = File(...), user: dict = Depends(get_current_user)):
    """
    Accept one or more PDF uploads.
    Returns JSON with per-file results (TFNs, names, pages).
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded.")

    results = []
    raw_results = []   # DocumentResult objects for anchor analysis
    db = get_db()

    for upload in files:
        content = await upload.read()
        result = process_document_with_ocr(content, upload.filename, len(content))
        raw_results.append(result)

        # Extract structured fields via OpenRouter LLM
        full_text = "\n".join(p.text for p in result.pages)
        extracted = extract_structured_data(full_text, result.doc_type, result.filename)
        extracted_json = json.dumps(extracted) if extracted else None

        # Persist to DB
        cursor = db.execute(
            """INSERT INTO documents
               (filename, pages, status, file_size, tfn_count, name_count,
                error_msg, file_bytes, doc_type, tier, extracted_data)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                result.filename,
                result.total_pages,
                result.status,
                len(content),
                len(result.all_tfns),
                len(result.names),
                result.error,
                content,
                result.doc_type,
                result.tier,
                extracted_json,
            ),
        )
        doc_id = cursor.lastrowid

        for tfn in result.all_tfns:
            boxes_json = json.dumps([
                {"x": b.x, "y": b.y, "width": b.width, "height": b.height, "page": b.page}
                for b in tfn.bounding_boxes
            ])
            db.execute(
                """INSERT INTO tfns
                   (document_id, normalized, formatted, page_number, confidence, is_valid, bounding_boxes)
                   VALUES (?,?,?,?,?,?,?)""",
                (doc_id, tfn.normalized, tfn.formatted, tfn.page_number,
                 tfn.confidence, 1 if tfn.is_valid else 0, boxes_json),
            )

        for name in result.names:
            db.execute(
                "INSERT INTO names (document_id, name) VALUES (?,?)",
                (doc_id, name),
            )

        db.commit()

        log_audit(
            "process",
            f"{result.filename} — {len(result.all_tfns)} TFN(s), {len(result.names)} name(s)",
        )

        results.append({
            "id": doc_id,
            "filename": result.filename,
            "pages": result.total_pages,
            "status": result.status,
            "error": result.error,
            "file_size": len(content),
            "doc_type": result.doc_type,
            "tier": result.tier,
            "tfns": [
                {
                    "formatted": t.formatted,
                    "normalized": t.normalized,
                    "page": t.page_number,
                    "confidence": int(t.confidence * 100),
                    "valid": t.is_valid,
                }
                for t in result.all_tfns
            ],
            "names": result.names,
            "extracted_data": extracted,
        })

    db.commit()

    # ── Packet-level anchor analysis ─────────────────────────────────────────
    from processors.name_comparator import analyse_packet
    packet = analyse_packet(raw_results)
    anchor_payload = None
    if packet:
        anchor_payload = {
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

    db.close()
    return {"results": results, "anchor": anchor_payload}


@router.get("/history")
def get_history(limit: int = 20):
    """Return recently processed documents."""
    db = get_db()
    rows = db.execute(
        "SELECT * FROM documents ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()

    docs = []
    for row in rows:
        tfns = db.execute(
            "SELECT formatted, page_number, confidence FROM tfns WHERE document_id=?",
            (row["id"],),
        ).fetchall()
        names = db.execute(
            "SELECT name FROM names WHERE document_id=?", (row["id"],)
        ).fetchall()
        docs.append({
            "id": row["id"],
            "filename": row["filename"],
            "pages": row["pages"],
            "status": row["status"],
            "file_size": row["file_size"],
            "tfn_count": row["tfn_count"],
            "name_count": row["name_count"],
            "error": row["error_msg"],
            "created_at": row["created_at"],
            "tfns": [
                {"formatted": t["formatted"], "page": t["page_number"],
                 "confidence": int((t["confidence"] or 0) * 100)}
                for t in tfns
            ],
            "names": [n["name"] for n in names],
        })

    db.close()
    return {"documents": docs}


@router.get("/stats")
def get_stats():
    """Return aggregate stats for the dashboard."""
    db = get_db()
    processed = db.execute(
        "SELECT COUNT(*) AS c FROM documents WHERE status='processed'"
    ).fetchone()["c"]
    tfns_found = db.execute(
        "SELECT COALESCE(SUM(tfn_count),0) AS s FROM documents WHERE status='processed'"
    ).fetchone()["s"]
    names_found = db.execute(
        "SELECT COALESCE(SUM(name_count),0) AS s FROM documents WHERE status='processed'"
    ).fetchone()["s"]
    flagged = db.execute(
        "SELECT COUNT(*) AS c FROM documents WHERE tfn_count > 0 AND status='processed'"
    ).fetchone()["c"]
    db.close()
    return {
        "processed": processed,
        "tfnsFound": tfns_found,
        "namesFound": names_found,
        "flagged": flagged,
    }


@router.get("/audit")
def get_audit(limit: int = 50):
    """Return audit log entries."""
    db = get_db()
    rows = db.execute(
        "SELECT * FROM audit_log ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    db.close()
    return {"log": [dict(r) for r in rows]}


class RedactRequest(dict):
    pass


@router.post("/{doc_id}/redact")
async def redact_document(
    doc_id: int,
    body: dict,
    user: dict = Depends(get_current_user),
):
    """
    Redact selected TFNs from a document and return the redacted PDF.

    Body: { "redact_tfns": ["123456782", ...] }
    Returns: application/pdf
    """
    import fitz  # pymupdf

    redact_tfns = set(body.get("redact_tfns", []))
    if not redact_tfns:
        raise HTTPException(status_code=400, detail="No TFNs specified for redaction.")

    db = get_db()
    doc_row = db.execute(
        "SELECT filename, file_bytes FROM documents WHERE id=?", (doc_id,)
    ).fetchone()

    if not doc_row:
        db.close()
        raise HTTPException(status_code=404, detail="Document not found.")

    file_bytes = doc_row["file_bytes"]
    filename   = doc_row["filename"]

    if not file_bytes:
        db.close()
        raise HTTPException(status_code=422, detail="Original file not stored. Re-upload to redact.")

    # Get bounding boxes for the TFNs to redact
    tfn_rows = db.execute(
        "SELECT normalized, bounding_boxes FROM tfns WHERE document_id=?", (doc_id,)
    ).fetchall()
    db.close()

    # Build page → list of rect mappings
    boxes_to_redact = []
    for row in tfn_rows:
        if row["normalized"] not in redact_tfns:
            continue
        if not row["bounding_boxes"]:
            continue
        for b in json.loads(row["bounding_boxes"]):
            boxes_to_redact.append(b)

    # Determine file type
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "pdf"

    # For images, convert to PDF first via pymupdf
    if ext in ("jpg", "jpeg", "png", "tiff", "tif", "bmp", "webp"):
        img_doc = fitz.open(stream=file_bytes, filetype=ext)
        pdf_bytes_io = io.BytesIO(img_doc.convert_to_pdf())
        pdf_bytes_io.seek(0)
        pdf_bytes = pdf_bytes_io.read()
        img_doc.close()
    else:
        pdf_bytes = file_bytes

    # Open with pymupdf and apply redaction
    pdf = fitz.open(stream=pdf_bytes, filetype="pdf")

    for page in pdf:
        page_num  = page.number + 1  # pymupdf is 0-indexed
        page_rect = page.rect
        w = page_rect.width
        h = page_rect.height

        for b in boxes_to_redact:
            if b["page"] != page_num:
                continue
            # Convert normalised coords → points
            x0 = b["x"] * w
            y0 = b["y"] * h
            x1 = (b["x"] + b["width"])  * w
            y1 = (b["y"] + b["height"]) * h
            # Add a small padding so the box fully covers the text
            pad = 3
            rect = fitz.Rect(x0 - pad, y0 - pad, x1 + pad, y1 + pad)
            page.add_redact_annot(rect, fill=(0, 0, 0))

        page.apply_redactions()

    redacted_bytes = pdf.tobytes(garbage=4, deflate=True)
    pdf.close()

    stem = filename.rsplit(".", 1)[0] if "." in filename else filename
    out_name = f"{stem}_redacted.pdf"

    log_audit("redact", f"{filename} — {len(redact_tfns)} TFN(s) redacted")

    return StreamingResponse(
        io.BytesIO(redacted_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{out_name}"'},
    )
