"""
Custom CSS theme — professional navy/white mortgage industry palette.

Colour semantics (consistent across the whole app):
  Green  #16A34A  — confirmed / safe / done
  Amber  #D97706  — needs review / warning
  Red    #DC2626  — problem / error / TFN found
  Blue   #2563EB  — processing / info
  Purple #7C3AED  — redacted
"""
import streamlit as st

_CSS = """
/* ── Reset default Streamlit chrome ─────────────────────────────────────── */
#MainMenu          { visibility: hidden !important; }
footer             { visibility: hidden !important; }
header             { visibility: hidden !important; }
[data-testid="stDecoration"] { display: none !important; }

/* ── App background ─────────────────────────────────────────────────────── */
.stApp {
    background-color: #F0F4F8;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                 "Helvetica Neue", Arial, sans-serif;
}

/* ── Main content container ─────────────────────────────────────────────── */
.block-container {
    padding: 2rem 2.5rem 3rem !important;
    max-width: 1300px !important;
}

/* ── Sidebar ────────────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0D1B2A 0%, #122740 100%) !important;
    border-right: none !important;
    min-width: 240px !important;
}
[data-testid="stSidebar"] > div:first-child {
    padding-top: 0 !important;
}
/* Force all sidebar text to be light */
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] div {
    color: #CBD5E1 !important;
}

/* Sidebar logo block */
.sidebar-logo {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 1.4rem 1.2rem 1.2rem;
    border-bottom: 1px solid rgba(255,255,255,0.08);
    margin-bottom: 0.75rem;
}
.sidebar-logo-icon  { font-size: 2rem; line-height: 1; }
.sidebar-logo-title { font-size: 1.05rem; font-weight: 700;
                       color: #F1F5F9 !important; letter-spacing: 0.2px; }
.sidebar-logo-sub   { font-size: 0.65rem; color: #64748B !important;
                       text-transform: uppercase; letter-spacing: 1px; margin-top: 2px; }

/* "Coming soon" nav items */
.nav-coming-soon {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.55rem 1rem;
    border-radius: 8px;
    margin: 2px 0.4rem;
    opacity: 0.45;
    font-size: 0.875rem;
    color: #CBD5E1 !important;
    cursor: not-allowed;
    user-select: none;
}
.nav-soon-badge {
    font-size: 0.6rem;
    background: rgba(255,255,255,0.1);
    padding: 2px 7px;
    border-radius: 10px;
    text-transform: uppercase;
    letter-spacing: 0.6px;
}

/* Sidebar primary buttons (active nav) */
[data-testid="stSidebar"] .stButton > button[kind="primary"] {
    background-color: rgba(255,255,255,0.12) !important;
    border: 1px solid rgba(255,255,255,0.18) !important;
    color: #F1F5F9 !important;
    border-radius: 8px !important;
    font-size: 0.875rem !important;
    font-weight: 600 !important;
    text-align: left !important;
    padding: 0.5rem 1rem !important;
    box-shadow: none !important;
    border-left: 3px solid #60A5FA !important;
}
[data-testid="stSidebar"] .stButton > button[kind="secondary"] {
    background-color: transparent !important;
    border: 1px solid transparent !important;
    color: #94A3B8 !important;
    border-radius: 8px !important;
    font-size: 0.875rem !important;
    font-weight: 400 !important;
    text-align: left !important;
    padding: 0.5rem 1rem !important;
    box-shadow: none !important;
}
[data-testid="stSidebar"] .stButton > button[kind="secondary"]:hover {
    background-color: rgba(255,255,255,0.07) !important;
    color: #E2E8F0 !important;
}

/* Sidebar stats footer */
.sidebar-stats {
    border-top: 1px solid rgba(255,255,255,0.08);
    padding: 1rem 1.2rem;
    margin-top: 1rem;
}
.sidebar-stat {
    display: flex;
    justify-content: space-between;
    padding: 0.28rem 0;
    font-size: 0.8rem;
    color: #64748B !important;
}
.sidebar-stat-value {
    font-weight: 600;
    color: #CBD5E1 !important;
}

/* ── Page header ─────────────────────────────────────────────────────────── */
.page-header   { margin-bottom: 1.75rem; }
.page-title    { font-size: 1.75rem; font-weight: 700; color: #0D1B2A; margin: 0 0 0.25rem; }
.page-subtitle { font-size: 0.93rem; color: #64748B; }

/* ── Metric cards ────────────────────────────────────────────────────────── */
.metric-card {
    background: #FFFFFF;
    border-radius: 12px;
    padding: 1.4rem 1.6rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.07), 0 4px 16px rgba(0,0,0,0.04);
    border: 1px solid #E2E8F0;
    height: 100%;
    transition: box-shadow 0.18s;
}
.metric-card:hover { box-shadow: 0 4px 14px rgba(0,0,0,0.1); }
.metric-card-icon  { font-size: 1.8rem; display: block; margin-bottom: 0.6rem; }
.metric-card-value { font-size: 2.1rem; font-weight: 700; color: #0D1B2A; line-height: 1; }
.metric-card-label { font-size: 0.78rem; color: #64748B; text-transform: uppercase;
                      letter-spacing: 0.6px; margin-top: 0.35rem; }

/* ── Status badges ───────────────────────────────────────────────────────── */
.badge {
    display: inline-flex;
    align-items: center;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 0.72rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    white-space: nowrap;
}
.badge-done       { background:#F0FDF4; color:#15803D; border:1px solid #BBF7D0; }
.badge-processing { background:#EFF6FF; color:#1D4ED8; border:1px solid #BFDBFE; }
.badge-error      { background:#FEF2F2; color:#B91C1C; border:1px solid #FECACA; }
.badge-review     { background:#FFFBEB; color:#B45309; border:1px solid #FDE68A; }
.badge-uploaded   { background:#F8FAFC; color:#475569; border:1px solid #E2E8F0; }
.badge-redacted   { background:#F5F3FF; color:#6D28D9; border:1px solid #DDD6FE; }

/* ── TFN display (monospaced) ────────────────────────────────────────────── */
.tfn-chip {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    background: #F8FAFC;
    border: 1px solid #E2E8F0;
    border-radius: 6px;
    padding: 3px 8px;
    margin: 2px 3px 2px 0;
}
.tfn-number {
    font-family: 'Courier New', Courier, monospace;
    font-size: 0.88rem;
    font-weight: 700;
    letter-spacing: 1.5px;
    color: #0D1B2A;
}
.tfn-chip.valid   { border-left: 3px solid #16A34A; }
.tfn-chip.invalid { border-left: 3px solid #DC2626; }
.tfn-page         { font-size: 0.7rem; color: #94A3B8; }
.conf-high   { font-size: 0.7rem; font-weight: 600; color: #16A34A; }
.conf-medium { font-size: 0.7rem; font-weight: 600; color: #D97706; }
.conf-low    { font-size: 0.7rem; font-weight: 600; color: #DC2626; }

/* ── Document rows ───────────────────────────────────────────────────────── */
.doc-row {
    display: flex;
    align-items: flex-start;
    gap: 1rem;
    padding: 0.9rem 1.25rem;
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 10px;
    margin-bottom: 0.5rem;
    transition: box-shadow 0.15s;
}
.doc-row:hover { box-shadow: 0 2px 10px rgba(0,0,0,0.08); }
.doc-filename  { font-weight: 600; color: #0D1B2A; font-size: 0.95rem;
                  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 360px; }
.doc-meta      { font-size: 0.8rem; color: #64748B; margin-top: 3px; }

/* ── Upload zone ─────────────────────────────────────────────────────────── */
[data-testid="stFileUploaderDropzone"] {
    border: 2px dashed #CBD5E1 !important;
    border-radius: 14px !important;
    background: #FFFFFF !important;
    padding: 2.5rem !important;
    text-align: center !important;
    transition: border-color 0.2s, background 0.2s !important;
    min-height: 160px !important;
}
[data-testid="stFileUploaderDropzone"]:hover {
    border-color: #1B3A5C !important;
    background: #F8FAFC !important;
}
[data-testid="stFileUploaderDropzoneInstructions"] {
    font-size: 1rem !important;
    color: #64748B !important;
}

/* ── Processing progress item ────────────────────────────────────────────── */
.proc-item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 0.7rem 1rem;
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 8px;
    margin-bottom: 0.4rem;
    font-size: 0.9rem;
    color: #0D1B2A;
}
.proc-filename { flex: 1; font-weight: 500; }
.proc-size     { font-size: 0.8rem; color: #94A3B8; }

/* ── Alert boxes ─────────────────────────────────────────────────────────── */
.alert {
    border-radius: 8px;
    padding: 0.85rem 1.1rem;
    font-size: 0.88rem;
    margin-bottom: 1rem;
    border-left-width: 4px;
    border-left-style: solid;
}
.alert-info    { background:#EFF6FF; border-left-color:#2563EB; color:#1E40AF; border:1px solid #BFDBFE; }
.alert-warning { background:#FFFBEB; border-left-color:#F59E0B; color:#92400E; border:1px solid #FDE68A; }
.alert-success { background:#F0FDF4; border-left-color:#16A34A; color:#166534; border:1px solid #BBF7D0; }
.alert-error   { background:#FEF2F2; border-left-color:#DC2626; color:#991B1B; border:1px solid #FECACA; }

/* ── Empty state ─────────────────────────────────────────────────────────── */
.empty-state       { text-align: center; padding: 3.5rem 2rem; }
.empty-state-icon  { font-size: 3.2rem; display: block; margin-bottom: 1rem; }
.empty-state-title { font-size: 1.15rem; font-weight: 600; color: #374151; margin-bottom: 0.4rem; }
.empty-state-text  { font-size: 0.88rem; color: #6B7280; }

/* ── Misc ────────────────────────────────────────────────────────────────── */
hr { border: none; border-top: 1px solid #E2E8F0; margin: 1.5rem 0; }

/* Main action buttons */
.stButton > button[kind="primary"] {
    background-color: #0D1B2A !important;
    border: none !important;
    color: #FFFFFF !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    transition: background 0.15s, transform 0.1s !important;
}
.stButton > button[kind="primary"]:hover {
    background-color: #1B3A5C !important;
    transform: translateY(-1px) !important;
}
.stButton > button[kind="secondary"] {
    border-radius: 8px !important;
    font-weight: 500 !important;
}
"""


def apply_styles() -> None:
    st.markdown(f"<style>{_CSS}</style>", unsafe_allow_html=True)
