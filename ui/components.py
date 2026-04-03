"""Reusable HTML/Streamlit UI components."""
from typing import List
import streamlit as st


# ── Status badges ─────────────────────────────────────────────────────────────

_BADGE_MAP = {
    "processed":  ("badge-done",       "✓ Done"),
    "processing": ("badge-processing", "⟳ Processing"),
    "error":      ("badge-error",      "✗ Error"),
    "review":     ("badge-review",     "⚠ Review"),
    "uploaded":   ("badge-uploaded",   "↑ Uploaded"),
    "redacted":   ("badge-redacted",   "⬛ Redacted"),
}


def status_badge(status: str) -> str:
    """Return an HTML badge for a document status."""
    cls, label = _BADGE_MAP.get(status.lower(), ("badge-uploaded", status.title()))
    return f'<span class="badge {cls}">{label}</span>'


# ── TFN display ───────────────────────────────────────────────────────────────

def tfn_chips(tfn_matches) -> str:
    """
    Return HTML chips for a list of TFNMatch objects.
    Each chip shows: TFN number | page number | confidence %.
    Confidence colour: green ≥85%, amber ≥50%, red <50%.
    """
    if not tfn_matches:
        return '<span style="color:#94A3B8;font-size:0.85rem;">None found</span>'

    parts = []
    for tfn in tfn_matches:
        validity_cls = "valid" if tfn.is_valid else "invalid"
        pct = int(tfn.confidence * 100)
        conf_cls = "conf-high" if pct >= 85 else ("conf-medium" if pct >= 50 else "conf-low")
        parts.append(
            f'<span class="tfn-chip {validity_cls}">'
            f'  <span class="tfn-number">{tfn.formatted}</span>'
            f'  <span class="tfn-page">p.{tfn.page_number}</span>'
            f'  <span class="{conf_cls}">{pct}%</span>'
            f'</span>'
        )
    return "".join(parts)


# ── Name list ─────────────────────────────────────────────────────────────────

def names_inline(names: List[str], limit: int = 5) -> str:
    """Return HTML for up to `limit` names, with a '+N more' indicator."""
    if not names:
        return '<span style="color:#94A3B8;font-size:0.85rem;">None found</span>'
    shown = names[:limit]
    extra = len(names) - limit
    text = ", ".join(shown)
    if extra > 0:
        text += f' <span style="color:#94A3B8;font-size:0.8rem;">+{extra} more</span>'
    return f'<span style="font-size:0.88rem;color:#1E293B;">{text}</span>'


# ── Metric cards ──────────────────────────────────────────────────────────────

def metric_card(icon: str, value, label: str, value_color: str = "#0D1B2A") -> None:
    """Render a white metric card (call inside a st.column)."""
    st.markdown(
        f"""
        <div class="metric-card">
            <span class="metric-card-icon">{icon}</span>
            <div class="metric-card-value" style="color:{value_color};">{value}</div>
            <div class="metric-card-label">{label}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ── Page header ───────────────────────────────────────────────────────────────

def page_header(title: str, subtitle: str = "") -> None:
    sub_html = f'<div class="page-subtitle">{subtitle}</div>' if subtitle else ""
    st.markdown(
        f'<div class="page-header"><div class="page-title">{title}</div>{sub_html}</div>',
        unsafe_allow_html=True,
    )


# ── Empty state ───────────────────────────────────────────────────────────────

def empty_state(icon: str, title: str, message: str) -> None:
    st.markdown(
        f"""
        <div class="empty-state">
            <span class="empty-state-icon">{icon}</span>
            <div class="empty-state-title">{title}</div>
            <div class="empty-state-text">{message}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ── Alert boxes ───────────────────────────────────────────────────────────────

def alert(message: str, kind: str = "info") -> None:
    """kind: 'info' | 'warning' | 'success' | 'error'"""
    icons = {"info": "ℹ", "warning": "⚠", "success": "✓", "error": "✗"}
    icon = icons.get(kind, "ℹ")
    st.markdown(
        f'<div class="alert alert-{kind}">{icon}&nbsp; {message}</div>',
        unsafe_allow_html=True,
    )
