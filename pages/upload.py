"""Upload & Processing page."""
import io
import csv
from typing import List

import streamlit as st

from config import config
from processors.document_ai import process_document_with_ocr, DocumentResult
from ui.components import page_header, tfn_chips, names_inline, status_badge, alert, empty_state
from utils.session import add_document_result, get_all_documents


def render_upload() -> None:
    page_header(
        "Upload & Process",
        "Drop mortgage PDFs to extract TFNs and identify persons.",
    )

    if not config.is_configured:
        alert(
            "Google Cloud credentials not configured — documents cannot be sent to Document AI. "
            "Copy <code>.env.example</code> → <code>.env</code> and restart the app.",
            kind="warning",
        )

    # ── File uploader ──────────────────────────────────────────────────────────
    st.markdown("#### Drop your files here")
    uploaded_files = st.file_uploader(
        "Upload PDFs",
        type=["pdf"],
        accept_multiple_files=True,
        label_visibility="collapsed",
        help="Drag and drop PDF files, or click to browse. Multiple files are supported.",
    )

    if not uploaded_files:
        st.markdown(
            '<div style="text-align:center;padding:0.5rem 0 1.5rem;'
            'color:#94A3B8;font-size:0.875rem;">'
            "PDF files only &nbsp;·&nbsp; Multiple files allowed &nbsp;·&nbsp; "
            "Processed locally — files are not stored"
            "</div>",
            unsafe_allow_html=True,
        )

    # ── Process button ─────────────────────────────────────────────────────────
    if uploaded_files:
        already_done = {
            f.name
            for f in uploaded_files
            if f.name in st.session_state.documents
            and st.session_state.documents[f.name].status == "processed"
        }
        new_files = [f for f in uploaded_files if f.name not in already_done]

        if already_done:
            alert(
                f"{len(already_done)} file(s) already processed this session "
                "and will be skipped. Remove and re-add a file to reprocess it.",
                kind="info",
            )

        col_btn, col_info = st.columns([2, 3])
        with col_btn:
            process_btn = st.button(
                f"Process {len(new_files)} File{'s' if len(new_files) != 1 else ''}",
                type="primary",
                disabled=(len(new_files) == 0),
                use_container_width=True,
            )
        with col_info:
            st.markdown(
                f'<div style="padding-top:0.65rem;color:#64748B;font-size:0.88rem;">'
                f"{len(uploaded_files)} file(s) selected"
                f"{f', {len(already_done)} already done' if already_done else ''}"
                f"</div>",
                unsafe_allow_html=True,
            )

        if process_btn and new_files:
            _run_processing(new_files)

    # ── Results table ──────────────────────────────────────────────────────────
    _render_results()


# ── Processing ────────────────────────────────────────────────────────────────

def _run_processing(files) -> None:
    """Process files one by one, streaming status updates to the UI."""
    st.markdown("---")
    st.markdown("#### Processing queue")

    progress = st.progress(0.0)
    status_slot = st.empty()
    results_this_run: List[DocumentResult] = []

    for idx, f in enumerate(files):
        progress.progress(idx / len(files))
        status_slot.markdown(
            f'<div class="proc-item">'
            f'<span class="badge badge-processing">⟳ Processing</span>'
            f'<span class="proc-filename">{f.name}</span>'
            f'<span class="proc-size">{_fmt_size(f.size)}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

        result = process_document_with_ocr(f.read(), f.name, f.size)
        add_document_result(result)
        results_this_run.append(result)

    progress.progress(1.0)
    status_slot.empty()

    ok = [r for r in results_this_run if r.status == "processed"]
    err = [r for r in results_this_run if r.status == "error"]

    if not err:
        alert(f"{len(ok)} document{'s' if len(ok) != 1 else ''} processed successfully.", kind="success")
    else:
        alert(
            f"{len(ok)} processed, {len(err)} failed. "
            "Check the results below for error details.",
            kind="warning",
        )

    st.rerun()


# ── Results table ─────────────────────────────────────────────────────────────

def _render_results() -> None:
    docs = get_all_documents()
    if not docs:
        return

    st.markdown("---")

    # Header row
    col_title, col_export = st.columns([3, 1])
    with col_title:
        st.markdown(f"#### Results &nbsp; <span style='font-size:0.8rem;color:#94A3B8;font-weight:400;'>{len(docs)} document(s)</span>", unsafe_allow_html=True)
    with col_export:
        csv_bytes = _build_csv(docs).encode("utf-8")
        st.download_button(
            "⬇ Export CSV",
            data=csv_bytes,
            file_name="tfn_results.csv",
            mime="text/csv",
            use_container_width=True,
        )

    for doc in reversed(docs):
        _doc_card(doc)


def _doc_card(doc: DocumentResult) -> None:
    """Render one document result card."""
    if doc.status == "error":
        tfn_html = (
            f'<span style="color:#DC2626;font-size:0.82rem;">'
            f'Error: {(doc.error or "")[:80]}{"…" if len(doc.error or "") > 80 else ""}'
            f'</span>'
        )
        name_html = '<span style="color:#94A3B8;font-size:0.85rem;">—</span>'
    else:
        tfn_html = tfn_chips(doc.all_tfns)
        name_html = names_inline(doc.names)

    pages_str = f"{doc.total_pages} page{'s' if doc.total_pages != 1 else ''}" if doc.total_pages else "—"
    size_str = _fmt_size(doc.file_size_bytes) if doc.file_size_bytes else ""
    meta = pages_str + (f" · {size_str}" if size_str else "")

    st.markdown(
        f"""
        <div class="doc-row">
            <div style="flex:1;min-width:0;">
                <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">
                    <span class="doc-filename">{doc.filename}</span>
                    {status_badge(doc.status)}
                </div>
                <div class="doc-meta" style="margin-bottom:8px;">{meta}</div>
                <div style="margin-bottom:5px;">
                    <span style="font-size:0.7rem;color:#94A3B8;text-transform:uppercase;
                                 letter-spacing:0.5px;margin-right:8px;font-weight:600;">TFNs</span>
                    {tfn_html}
                </div>
                <div>
                    <span style="font-size:0.7rem;color:#94A3B8;text-transform:uppercase;
                                 letter-spacing:0.5px;margin-right:8px;font-weight:600;">Names</span>
                    {name_html}
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fmt_size(size: int) -> str:
    if size < 1_024:
        return f"{size} B"
    if size < 1_048_576:
        return f"{size / 1_024:.1f} KB"
    return f"{size / 1_048_576:.1f} MB"


def _build_csv(docs: List[DocumentResult]) -> str:
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow([
        "Filename", "Pages", "File Size", "Status",
        "TFN Count", "TFN Values (formatted)", "TFN Pages",
        "Names Found",
    ])
    for doc in docs:
        tfn_vals = " | ".join(t.formatted for t in doc.all_tfns)
        tfn_pages = " | ".join(str(t.page_number) for t in doc.all_tfns)
        names = " | ".join(doc.names)
        writer.writerow([
            doc.filename,
            doc.total_pages,
            _fmt_size(doc.file_size_bytes),
            doc.status,
            len(doc.all_tfns),
            tfn_vals,
            tfn_pages,
            names,
        ])
    return out.getvalue()
