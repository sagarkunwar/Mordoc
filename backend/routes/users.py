"""User / profile routes."""
import os
from fastapi import APIRouter
from database import get_db

router = APIRouter()


@router.get("/me")
def get_profile():
    """Return the current user's profile and usage stats."""
    db = get_db()

    # Monthly usage (current calendar month)
    monthly = db.execute(
        """SELECT COUNT(*) AS docs,
                  COALESCE(SUM(tfn_count),0) AS tfns
           FROM documents
           WHERE strftime('%Y-%m', created_at) = strftime('%Y-%m', 'now','localtime')
             AND status = 'processed'"""
    ).fetchone()

    total = db.execute(
        "SELECT COUNT(*) AS c FROM documents WHERE status='processed'"
    ).fetchone()["c"]

    db.close()

    return {
        "name":         os.getenv("USER_NAME",    "Admin"),
        "email":        os.getenv("USER_EMAIL",   "admin@yourdomain.com.au"),
        "company":      os.getenv("USER_COMPANY", "Your Company"),
        "role":         os.getenv("USER_ROLE",    "Mortgage Processor"),
        "plan":         "Professional",
        "monthly_limit": 100,
        "usage": {
            "docs_this_month": monthly["docs"],
            "tfns_this_month": monthly["tfns"],
            "total_processed": total,
        },
    }
