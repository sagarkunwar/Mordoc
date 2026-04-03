"""
MortgageDoc AI — Streamlit entry point.

Run:
    cd "TFN"
    pip install -r requirements.txt
    streamlit run app.py
"""
from dotenv import load_dotenv

load_dotenv()  # must happen before any config import

import streamlit as st

from ui.styles import apply_styles
from utils.session import init_session_state, navigate_to
from pages.dashboard import render_dashboard
from pages.upload import render_upload


# ── Sidebar ───────────────────────────────────────────────────────────────────

def _nav_btn(label: str, icon: str, page_id: str) -> None:
    """Render a sidebar navigation button."""
    is_active = st.session_state.get("current_page") == page_id
    if st.button(
        f"{icon}  {label}",
        key=f"nav_{page_id}",
        use_container_width=True,
        type="primary" if is_active else "secondary",
    ):
        if not is_active:
            navigate_to(page_id)


def _render_sidebar() -> None:
    with st.sidebar:
        # Brand
        st.markdown(
            """
            <div class="sidebar-logo">
                <span class="sidebar-logo-icon">🏦</span>
                <div>
                    <div class="sidebar-logo-title">MortgageDoc AI</div>
                    <div class="sidebar-logo-sub">Document Processing</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Active pages
        _nav_btn("Dashboard", "📊", "dashboard")
        _nav_btn("Upload & Process", "📤", "upload")

        # Coming-soon pages (non-clickable)
        coming_soon = [
            ("📁", "Loan Files"),
            ("👥", "Name Matching"),
            ("⬛", "Redaction"),
            ("📋", "Audit Log"),
        ]
        for icon, label in coming_soon:
            st.markdown(
                f"""
                <div class="nav-coming-soon">
                    <span>{icon}&nbsp; {label}</span>
                    <span class="nav-soon-badge">Soon</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # Stats footer
        stats = st.session_state.get("stats", {})
        st.markdown(
            f"""
            <div class="sidebar-stats">
                <div class="sidebar-stat">
                    <span>Documents</span>
                    <span class="sidebar-stat-value">{stats.get("total_processed", 0)}</span>
                </div>
                <div class="sidebar-stat">
                    <span>TFNs found</span>
                    <span class="sidebar-stat-value">{stats.get("total_tfns_found", 0)}</span>
                </div>
                <div class="sidebar-stat">
                    <span>Names</span>
                    <span class="sidebar-stat-value">{stats.get("total_names_found", 0)}</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    st.set_page_config(
        page_title="MortgageDoc AI",
        page_icon="🏦",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    apply_styles()
    init_session_state()
    _render_sidebar()

    page = st.session_state.get("current_page", "dashboard")
    if page == "dashboard":
        render_dashboard()
    elif page == "upload":
        render_upload()
    else:
        st.info("This feature is coming in the next build.")


if __name__ == "__main__":
    main()
