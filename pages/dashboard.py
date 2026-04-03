"""Dashboard page — session overview and quick navigation."""
import streamlit as st

from config import config
from ui.components import metric_card, page_header, empty_state, status_badge, alert, tfn_chips
from utils.session import get_all_documents, navigate_to


def render_dashboard() -> None:
    page_header(
        "Dashboard",
        "Your mortgage document processing overview.",
    )

    stats = st.session_state.get("stats", {})
    docs = get_all_documents()

    # ── Metric row ────────────────────────────────────────────────────────────
    col1, col2, col3, col4 = st.columns(4, gap="medium")
    with col1:
        metric_card("📄", stats.get("total_processed", 0), "Documents Processed")
    with col2:
        tfn_count = stats.get("total_tfns_found", 0)
        metric_card(
            "🔢", tfn_count, "TFNs Detected",
            value_color="#B91C1C" if tfn_count > 0 else "#0D1B2A",
        )
    with col3:
        metric_card("👤", stats.get("total_names_found", 0), "Names Extracted")
    with col4:
        flagged = sum(1 for d in docs if d.status == "processed" and d.all_tfns)
        metric_card(
            "⚠️", flagged, "Files Containing TFNs",
            value_color="#D97706" if flagged > 0 else "#0D1B2A",
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Two-column layout ─────────────────────────────────────────────────────
    col_main, col_side = st.columns([2, 1], gap="large")

    with col_main:
        st.markdown("### Recent Documents")

        if not docs:
            empty_state(
                "📂",
                "No documents yet",
                "Upload your first mortgage documents using the Upload & Process page.",
            )
        else:
            for doc in reversed(docs[-10:]):
                tfn_count = len(doc.all_tfns)
                name_count = len(doc.names)
                pages_str = f"{doc.total_pages} page{'s' if doc.total_pages != 1 else ''}"

                tfn_indicator = ""
                if tfn_count > 0:
                    tfn_indicator = (
                        f'&nbsp;·&nbsp;<span style="color:#B91C1C;font-weight:600;">'
                        f'⚠ {tfn_count} TFN{"s" if tfn_count > 1 else ""}</span>'
                    )

                st.markdown(
                    f"""
                    <div class="doc-row">
                        <div style="flex:1;min-width:0;">
                            <div style="display:flex;align-items:center;gap:8px;">
                                <span class="doc-filename">{doc.filename}</span>
                                {status_badge(doc.status)}
                            </div>
                            <div class="doc-meta">
                                {pages_str}
                                &nbsp;·&nbsp; {name_count} name{'s' if name_count != 1 else ''}
                                {tfn_indicator}
                            </div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    with col_side:
        st.markdown("### Quick Actions")
        st.markdown("<br>", unsafe_allow_html=True)

        if st.button("📤  Upload & Process Documents", use_container_width=True, type="primary"):
            navigate_to("upload")

        st.markdown("<br>", unsafe_allow_html=True)

        # Google Cloud connection status
        if config.is_configured:
            alert("Google Cloud connected and ready.", kind="success")
        else:
            alert(
                "Google Cloud not configured. "
                "Copy <code>.env.example</code> → <code>.env</code> and fill in your credentials.",
                kind="warning",
            )

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(
            f'<div class="doc-meta">Session started: {stats.get("session_start", "—")}</div>',
            unsafe_allow_html=True,
        )
