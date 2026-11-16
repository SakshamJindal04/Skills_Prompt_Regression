"""
Theme and design tokens for the Skill & Prompt Regression Manager.
Light-Only Modern Design System:
Enforces local-first system typography, WCAG AAA (>= 7:1) body contrast,
WCAG AA (>= 4.5:1) UI text contrast, and unified light Plotly template.
Palette: #F6F8FB (bg), #FFFFFF (cards), #1E293B (text), #DBEAFE (primary action).
"""

from pathlib import Path
import streamlit as st
import plotly.graph_objects as go
import plotly.io as pio

BASE_DIR = Path(__file__).resolve().parent.parent.parent
STYLES_CSS_PATH = BASE_DIR / "app" / "ui" / "styles.css"

TOKENS = {
    "colors": {
        "page_bg": "#F6F8FB",
        "surface": "#FFFFFF",
        "surface_alt": "#F1F5F9",
        "border": "#E2E8F0",
        "border_strong": "#CBD5E1",
        "text_primary": "#1E293B",
        "text_secondary": "#475569",
        "text_muted": "#475569",
        "text_caption": "#475569",

        # Primary action
        "primary": "#1E3A8A",
        "primary_action_bg": "#DBEAFE",
        "primary_action_border": "#93C5FD",
        "primary_action_text": "#1E3A8A",
        "primary_action_hover": "#BFDBFE",

        # Secondary action
        "secondary_action_bg": "#FFFFFF",
        "secondary_action_border": "#CBD5E1",
        "secondary_action_text": "#1E293B",
        "secondary_action_hover": "#F1F5F9",

        # Status semantics (light fill + dark text >= 4.5:1)
        "success": {"text": "#166534", "bg": "#DCFCE7", "border": "#86EFAC"},
        "danger": {"text": "#991B1B", "bg": "#FEE2E2", "border": "#FCA5A5"},
        "warning": {"text": "#92400E", "bg": "#FEF3C7", "border": "#FCD34D"},
        "info": {"text": "#075985", "bg": "#E0F2FE", "border": "#7DD3FC"},
        "neutral": {"text": "#334155", "bg": "#F1F5F9", "border": "#CBD5E1"},
    },
    "typography": {
        "font_sans": 'system-ui, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
        "font_mono": 'ui-monospace, "Cascadia Mono", Consolas, monospace',
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

# Modern light-only chart colorway with >= 3:1 contrast against white:
# Blue (#3B82F6), Emerald (#059669), Amber (#D97706), Red (#EF4444), Violet (#8B5CF6), Slate (#64748B)
COLORWAY = [
    "#3B82F6",  # Series 1: Blue
    "#059669",  # Series 2: Emerald Green (calibrated for 3.77:1 contrast)
    "#D97706",  # Series 3: Dark Amber (calibrated for 3.19:1 contrast)
    "#EF4444",  # Series 4: Crimson Red
    "#8B5CF6",  # Series 5: Violet
    "#64748B",  # Series 6: Slate Gray
]


def init_theme() -> None:
    """Injects custom light-only modern design system CSS into the Streamlit session."""
    if STYLES_CSS_PATH.exists():
        css = STYLES_CSS_PATH.read_text(encoding="utf-8")
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def get_plotly_template(is_dark: bool = False, *args, **kwargs) -> go.layout.Template:
    """Returns a standardized light Plotly template with white plot canvas and >= 3:1 contrast marks."""
    axis_color = "#334155"
    grid_color = "#E2E8F0"
    card_bg = "#FFFFFF"

    template = go.layout.Template()
    template.layout = go.Layout(
        colorway=COLORWAY,
        font=dict(
            family='system-ui, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
            size=13,
            color=axis_color,
        ),
        paper_bgcolor=card_bg,
        plot_bgcolor=card_bg,
        margin=dict(l=48, r=24, t=44, b=44),
        hoverlabel=dict(
            bgcolor="#FFFFFF",
            font_size=13,
            font_color="#1E293B",
            font_family='system-ui, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
            bordercolor=grid_color,
        ),
        xaxis=dict(
            gridcolor=grid_color,
            gridwidth=1,
            zerolinecolor=grid_color,
            tickfont=dict(size=12, color=axis_color),
            title=dict(font=dict(size=13, color=axis_color)),
        ),
        yaxis=dict(
            gridcolor=grid_color,
            gridwidth=1,
            zerolinecolor=grid_color,
            tickfont=dict(size=12, color=axis_color),
            title=dict(font=dict(size=13, color=axis_color)),
        ),
        legend=dict(
            font=dict(size=12, color=axis_color),
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
        ),
    )
    return template


# Register custom template with Plotly
pio.templates["regguard_light"] = get_plotly_template()
pio.templates["regguard_natural"] = pio.templates["regguard_light"]
pio.templates["arm_enterprise"] = pio.templates["regguard_light"]
pio.templates.default = "regguard_light"
