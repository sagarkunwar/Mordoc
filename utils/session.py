"""Session state management — single source of truth for all app state."""
from datetime import datetime
from typing import List

import streamlit as st


def init_session_state() -> None:
    """Initialise all session state keys with safe defaults."""
    defaults = {
        "current_page": "dashboard",
        "documents": {},          # filename -> DocumentResult
        "upload_order": [],       # filenames in the order they were processed
        "stats": {
            "total_processed": 0,
            "total_tfns_found": 0,
            "total_names_found": 0,
            "session_start": datetime.now().strftime("%Y-%m-%d %H:%M"),
        },
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def add_document_result(result) -> None:
    """Persist a DocumentResult and update aggregate stats."""
    fname = result.filename
    # If re-processing, subtract old counts first
    if fname in st.session_state.documents:
        old = st.session_state.documents[fname]
        if old.status == "processed":
            st.session_state.stats["total_processed"] -= 1
            st.session_state.stats["total_tfns_found"] -= len(old.all_tfns)
            st.session_state.stats["total_names_found"] -= len(old.names)

    st.session_state.documents[fname] = result

    if fname not in st.session_state.upload_order:
        st.session_state.upload_order.append(fname)

    if result.status == "processed":
        st.session_state.stats["total_processed"] += 1
        st.session_state.stats["total_tfns_found"] += len(result.all_tfns)
        st.session_state.stats["total_names_found"] += len(result.names)


def get_all_documents() -> list:
    """Return all DocumentResult objects in processing order."""
    docs = []
    for fname in st.session_state.upload_order:
        if fname in st.session_state.documents:
            docs.append(st.session_state.documents[fname])
    return docs


def navigate_to(page: str) -> None:
    st.session_state.current_page = page
    st.rerun()
