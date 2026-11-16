"""
Theme and design tokens for the Skill & Prompt Regression Manager.
Enforces local-first fonts, WCAG AA contrast, and unified Plotly visualization styling.
Calm Natural Palette: Sage green (#3F6B57), Slate blue (#3E6E8C), Amber (#B8862B / #E4B661), Terracotta (#B4483C).
"""

from pathlib import Path
import streamlit as st
import plotly.graph_objects as go
import plotly.io as pio

BASE_DIR = Path(__file__).resolve().parent.parent.parent
STYLES_CSS_PATH = BASE_DIR / "app" / "ui" / "styles.css"

TOKENS = {
    "colors": {
        "primary": "#3F6B57",
        "primary_hover": "#335A49",
        "primary_accent": "#3F6B57",
        "bg_light": "#FAF8F4",
        "surface_light": "#FFFFFF",
        "surface_alt_light": "#F2EFE8",
        "border_light": "#E3DED3",
        "text_light": "#1F2A24",
        "text_muted_light": "#5B665F",
        "text_caption_light": "#7A857E",
        "bg_dark": "#151A17",
        "surface_dark": "#1D2420",
        "surface_alt_dark": "#252D28",
        "border_dark": "#33403A",
        "text_dark": "#E8EDE6",
        "text_muted_dark": "#9AA79F",
        "primary_dark": "#7DB596",
        # Status semantics with WCAG AA contrast >= 4.5:1
        "success": {"text": "#447D54", "bg": "#F0F7F2", "border": "#A3CEB0"},
        "danger": {"text": "#B4483C", "bg": "#FDF2F0", "border": "#E8ABA3"},
        "warning": {"text": "#5D3C00", "bg": "#FEF9EE", "border": "#E4B661", "fill": "#E4B661"},
        "info": {"text": "#3E6E8C", "bg": "#F0F6F9", "border": "#ADC8D9"},
        "neutral": {"text": "#5B665F", "bg": "#F2EFE8", "border": "#E3DED3"},
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

# Natural palette chart sequence: #3F6B57, #3E6E8C, #B8862B, #B4483C, #7A6F99, #8A8F7C
COLORWAY = [
    "#3F6B57",  # Sage Green (Primary)
    "#3E6E8C",  # Slate Blue (Secondary)
    "#B8862B",  # Muted Amber / Ochre
    "#B4483C",  # Terracotta Red
    "#7A6F99",  # Muted Heather Purple
    "#8A8F7C",  # Warm Olive Gray
]


def init_theme() -> None:
    """Injects custom natural design system CSS into the Streamlit session."""
    if STYLES_CSS_PATH.exists():
        css = STYLES_CSS_PATH.read_text(encoding="utf-8")
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def get_plotly_template(is_dark: bool = False) -> go.layout.Template:
    """Returns a standardized, color-blind-safe Plotly template matching the Natural Palette."""
    font_color = "#E8EDE6" if is_dark else "#1F2A24"
    grid_color = "#33403A" if is_dark else "#E3DED3"
    bg_color = "rgba(0,0,0,0)"

    template = go.layout.Template()
    template.layout = go.Layout(
        colorway=COLORWAY,
        font=dict(
            family='system-ui, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
            size=12,
            color=font_color,
        ),
        paper_bgcolor=bg_color,
        plot_bgcolor=bg_color,
        margin=dict(l=40, r=20, t=40, b=40),
        hoverlabel=dict(
            bgcolor="#1D2420" if is_dark else "#FFFFFF",
            font_size=12,
            font_color=font_color,
            font_family='system-ui, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
            bordercolor=grid_color,
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
pio.templates["regguard_natural"] = get_plotly_template(is_dark=False)
pio.templates["arm_enterprise"] = pio.templates["regguard_natural"]
pio.templates.default = "regguard_natural"
