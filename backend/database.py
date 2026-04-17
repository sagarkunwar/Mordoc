"""SQLite database — stores documents, TFNs, names, and audit log."""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "mortgagedoc.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS documents (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            filename    TEXT    NOT NULL,
            pages       INTEGER DEFAULT 0,
            status      TEXT    DEFAULT 'processed',
            file_size   INTEGER DEFAULT 0,
            tfn_count   INTEGER DEFAULT 0,
            name_count  INTEGER DEFAULT 0,
            error_msg   TEXT,
            file_bytes  BLOB,
            doc_type    TEXT    DEFAULT 'Unknown Document',
            tier        INTEGER DEFAULT 5,
            created_at  TEXT    DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS tfns (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id     INTEGER NOT NULL,
            normalized      TEXT,
            formatted       TEXT,
            page_number     INTEGER,
            confidence      REAL,
            is_valid        INTEGER DEFAULT 1,
            bounding_boxes  TEXT,
            FOREIGN KEY (document_id) REFERENCES documents(id)
        );

        CREATE TABLE IF NOT EXISTS names (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            name        TEXT,
            FOREIGN KEY (document_id) REFERENCES documents(id)
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            action     TEXT NOT NULL,
            detail     TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS cases (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            client_name     TEXT    NOT NULL,
            anchor_doc_type TEXT,
            anchor_name     TEXT,
            status          TEXT    DEFAULT 'open',
            doc_count       INTEGER DEFAULT 0,
            created_at      TEXT    DEFAULT (datetime('now','localtime')),
            updated_at      TEXT    DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS case_documents (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id         INTEGER NOT NULL,
            document_id     INTEGER NOT NULL,
            is_redacted     INTEGER DEFAULT 0,
            redacted_bytes  BLOB,
            added_at        TEXT    DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (case_id)     REFERENCES cases(id),
            FOREIGN KEY (document_id) REFERENCES documents(id)
        );
    """)
    conn.commit()
    # Migrations: add columns if they don't exist yet (safe to re-run)
    for table, col, definition in [
        ("documents", "file_bytes",     "BLOB"),
        ("tfns",      "bounding_boxes", "TEXT"),
        ("documents", "doc_type",       "TEXT DEFAULT 'Unknown Document'"),
        ("documents", "tier",           "INTEGER DEFAULT 5"),
        ("cases",     "anchor_name",    "TEXT"),
        ("cases",     "anchor_doc_type","TEXT"),
        ("documents", "extracted_data", "TEXT"),
    ]:
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {definition}")
            conn.commit()
        except Exception:
            pass  # column already exists
    conn.close()


def log_audit(action: str, detail: str = ""):
    conn = get_db()
    conn.execute(
        "INSERT INTO audit_log (action, detail) VALUES (?,?)", (action, detail)
    )
    conn.commit()
    conn.close()
