"""
Theme and design tokens for the Skill & Prompt Regression Manager.
Enforces local-first fonts, WCAG AA contrast, and unified Plotly visualization styling.
"""

from pathlib import Path
import streamlit as st
import plotly.graph_objects as go
import plotly.io as pio

BASE_DIR = Path(__file__).resolve().parent.parent.parent
STYLES_CSS_PATH = BASE_DIR / "app" / "ui" / "styles.css"

TOKENS = {
    "colors": {
        "primary": "#1E3A8A",
        "primary_accent": "#2563EB",
        "bg_light": "#F8FAFC",
        "surface_light": "#FFFFFF",
        "border_light": "#E2E8F0",
        "text_light": "#0F172A",
        "text_muted_light": "#475569",
        "bg_dark": "#0B0F19",
        "surface_dark": "#111827",
        "border_dark": "#374151",
        "text_dark": "#F9FAFB",
        "text_muted_dark": "#9CA3AF",
        # Status semantics with WCAG AA contrast >= 4.5:1
        "success": {"text": "#047857", "bg": "#ECFDF5", "border": "#6EE7B7"},
        "danger": {"text": "#B91C1C", "bg": "#FEF2F2", "border": "#FCA5A5"},
        "warning": {"text": "#92400E", "bg": "#FFFBEB", "border": "#FDE68A"},
        "info": {"text": "#1D4ED8", "bg": "#EFF6FF", "border": "#BFDBFE"},
        "neutral": {"text": "#334155", "bg": "#F8FAFC", "border": "#CBD5E1"},
    },
    "typography": {
        "font_sans": '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
        "font_mono": 'ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace',
    },
    "icons": {
        "promote": ":material/check_circle:",
        "block": ":material/block:",
        "regressed": ":material/trending_down:",
        "fixed": ":material/trending_up:",
        "unchanged": ":material/remove:",
        "still_failing": ":material/error_outline:",
        "inconclusive": ":material/help_outline:",
        "baseline": ":material/flag:",
        "candidate": ":material/science:",
        "audit": ":material/verified_user:",
        "warning": ":material/warning:",
        "info": ":material/info:",
        "check": ":material/check:",
        "close": ":material/close:",
        "copy": ":material/content_copy:",
        "history": ":material/history:",
        "database": ":material/database:",
        "memory": ":material/memory:",
        "play": ":material/play_arrow:",
        "download": ":material/download:",
        "filter": ":material/filter_list:",
        "search": ":material/search:",
    },
}

COLORWAY = [
    "#2563EB",  # Primary Blue
    "#059669",  # Emerald Green
    "#DC2626",  # Crimson Red
    "#D97706",  # Amber Orange
    "#7C3AED",  # Violet
    "#0891B2",  # Cyan
    "#475569",  # Slate
]


def init_theme() -> None:
    """Injects custom enterprise CSS into the Streamlit session."""
    if STYLES_CSS_PATH.exists():
        css = STYLES_CSS_PATH.read_text(encoding="utf-8")
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def get_plotly_template(is_dark: bool = False) -> go.layout.Template:
    """Returns a standardized, color-blind-safe Plotly template with accessible typography."""
    font_color = "#F9FAFB" if is_dark else "#0F172A"
    grid_color = "#374151" if is_dark else "#E2E8F0"
    bg_color = "rgba(0,0,0,0)"

    template = go.layout.Template()
    template.layout = go.Layout(
        colorway=COLORWAY,
        font=dict(
            family='-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
            size=12,
            color=font_color,
        ),
        paper_bgcolor=bg_color,
        plot_bgcolor=bg_color,
        margin=dict(l=40, r=20, t=40, b=40),
        hoverlabel=dict(
            bgcolor="#1E293B" if is_dark else "#0F172A",
            font_size=12,
            font_color="#FFFFFF",
            font_family='-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
        ),
        xaxis=dict(
            gridcolor=grid_color,
            gridwidth=1,
            zerolinecolor=grid_color,
            tickfont=dict(size=11, color=font_color),
            title=dict(font=dict(size=12, color=font_color)),
        ),
        yaxis=dict(
            gridcolor=grid_color,
            gridwidth=1,
            zerolinecolor=grid_color,
            tickfont=dict(size=11, color=font_color),
            title=dict(font=dict(size=12, color=font_color)),
        ),
        legend=dict(
            font=dict(size=11, color=font_color),
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
        ),
    )
    return template


# Register custom template with Plotly
pio.templates["arm_enterprise"] = get_plotly_template(is_dark=False)
pio.templates.default = "arm_enterprise"
