"""Document processing routes."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from typing import List

from processors.document_ai import process_document_with_ocr
from database import get_db, log_audit

router = APIRouter()


@router.post("/process")
async def process_documents(files: List[UploadFile] = File(...)):
    """
    Accept one or more PDF uploads.
    Returns JSON with per-file results (TFNs, names, pages).
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded.")

    results = []
    db = get_db()

    for upload in files:
        content = await upload.read()
        result = process_document_with_ocr(content, upload.filename, len(content))

        # Persist to DB
        cursor = db.execute(
            """INSERT INTO documents
               (filename, pages, status, file_size, tfn_count, name_count, error_msg)
               VALUES (?,?,?,?,?,?,?)""",
            (
                result.filename,
                result.total_pages,
                result.status,
                len(content),
                len(result.all_tfns),
                len(result.names),
                result.error,
            ),
        )
        doc_id = cursor.lastrowid

        for tfn in result.all_tfns:
            db.execute(
                """INSERT INTO tfns
                   (document_id, normalized, formatted, page_number, confidence, is_valid)
                   VALUES (?,?,?,?,?,?)""",
                (doc_id, tfn.normalized, tfn.formatted, tfn.page_number,
                 tfn.confidence, 1 if tfn.is_valid else 0),
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
        })

    db.close()
    return {"results": results}


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
