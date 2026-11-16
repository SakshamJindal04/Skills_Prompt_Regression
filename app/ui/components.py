"""
Reusable Enterprise Component Library for Streamlit.
Provides standardized, WCAG AA compliant layout and status components.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List
import streamlit as st

from app.ui.theme import TOKENS, init_theme
from core.llm import default_client
from core.db import get_session
from core.versioner import get_current_baseline
from core.policy import load_policy
from core.models import Comparison

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def safe_set_page_config(title: str, layout: str = "wide") -> None:
    """Sets page config safely without raising StreamlitSetPageConfigMustBeFirst in sub-navigation."""
    try:
        st.set_page_config(
            page_title=f"{title} | Regression Manager",
            page_icon=":material/analytics:",
            layout=layout,
            initial_sidebar_state="expanded",
        )
    except Exception:
        pass


def page_header(title: str, subtitle: Optional[str] = None) -> None:
    """Renders a standardized enterprise page header with clear hierarchy."""
    st.markdown(f"## {title}")
    if subtitle:
        st.caption(subtitle)
    st.markdown("<div style='margin-bottom: 12px;'></div>", unsafe_allow_html=True)


def status_chip(kind: str, text: str) -> str:
    """
    Renders an accessible dual-encoded status chip (always icon + text, never colour alone).
    kind: 'promote', 'block', 'regressed', 'fixed', 'inconclusive', 'warning', 'info', 'neutral'
    """
    k = kind.lower().strip()
    icon_map = {
        "promote": ":material/check_circle:",
        "block": ":material/block:",
        "regressed": ":material/trending_down:",
        "fixed": ":material/trending_up:",
        "inconclusive": ":material/help_outline:",
        "warning": ":material/warning:",
        "info": ":material/info:",
        "neutral": ":material/radio_button_unchecked:",
    }
    class_map = {
        "promote": "arm-chip-success",
        "fixed": "arm-chip-success",
        "block": "arm-chip-danger",
        "regressed": "arm-chip-danger",
        "warning": "arm-chip-warning",
        "inconclusive": "arm-chip-warning",
        "info": "arm-chip-info",
        "neutral": "arm-chip-neutral",
    }
    icon = icon_map.get(k, ":material/info:")
    css_class = class_map.get(k, "arm-chip-neutral")
    return f'<span class="arm-chip {css_class}">{icon} {text}</span>'


def render_status_chip(kind: str, text: str) -> None:
    """Renders a status chip directly into the Streamlit layout."""
    st.markdown(status_chip(kind, text), unsafe_allow_html=True)


def verdict_banner(verdict: str, summary: str, p_value: Optional[float] = None, delta_pass_rate: Optional[float] = None) -> None:
    """Renders a high-prominence status banner for gate decisions."""
    v = verdict.upper().strip()
    if v == "PROMOTE":
        css = "arm-verdict-banner-promote"
        icon = ":material/check_circle:"
        title = "GATE VERDICT: PROMOTE (Candidate Accepted)"
    elif v == "BLOCK":
        css = "arm-verdict-banner-block"
        icon = ":material/block:"
        title = "GATE VERDICT: BLOCK (Regression Detected)"
    else:
        css = "arm-verdict-banner-neutral"
        icon = ":material/info:"
        title = f"GATE VERDICT: {v}"

    stats_line = ""
    if p_value is not None or delta_pass_rate is not None:
        parts = []
        if delta_pass_rate is not None:
            parts.append(f"Delta: <b>{delta_pass_rate * 100:+.1f}%</b>")
        if p_value is not None:
            parts.append(f"McNemar p-value: <b>{p_value:.4f}</b>")
        stats_line = f"<div style='margin-top: 6px; font-size: 0.85rem;'>{' | '.join(parts)}</div>"

    html = f"""
    <div class="arm-verdict-banner {css}">
      <div class="arm-verdict-title">{icon} {title}</div>
      <div class="arm-verdict-desc">{summary}</div>
      {stats_line}
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def kpi_card(label: str, value: str, delta: Optional[str] = None, help_text: Optional[str] = None) -> None:
    """Renders an enterprise KPI metric card with hover elevation."""
    delta_html = ""
    if delta:
        delta_color = "var(--arm-success-text)" if ("+" in delta or "PROMOTE" in delta) else "var(--arm-danger-text)" if ("-" in delta or "BLOCK" in delta) else "var(--arm-text-muted)"
        delta_html = f"<div class='arm-kpi-delta' style='color: {delta_color};'>{delta}</div>"

    help_attr = f"title='{help_text}'" if help_text else ""
    html = f"""
    <div class="arm-kpi-card" {help_attr}>
      <div class="arm-kpi-label">{label}</div>
      <div class="arm-kpi-value">{value}</div>
      {delta_html}
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def copyable_hash(value: str, length: int = 7) -> str:
    """Renders a copyable monospace short hash pill."""
    val_str = str(value or "")
    short = val_str[:length] if len(val_str) >= length else val_str
    return f'<code class="arm-mono" title="Full Hash: {val_str}">{short}</code>'


def labelled_divider(label: str) -> None:
    """Renders a clean labelled divider for visual sectioning."""
    st.markdown(
        f"""
        <div style="display: flex; align-items: center; margin: 24px 0 16px 0;">
          <span style="font-size: 0.78rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; color: var(--arm-text-caption); padding-right: 12px;">{label}</span>
          <div style="flex: 1; height: 1px; background: var(--arm-border);"></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def empty_state(message: str, subtitle: Optional[str] = None, icon: str = ":material/inbox:") -> None:
    """Renders a styled empty state placeholder with actionable guidance."""
    sub_html = f'<div class="arm-empty-subtitle">{subtitle}</div>' if subtitle else ""
    st.markdown(
        f"""
        <div class="arm-empty-state">
          <div class="arm-empty-icon">{icon}</div>
          <div class="arm-empty-title">{message}</div>
          {sub_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def error_panel(message: str, how_to_fix: Optional[str] = None) -> None:
    """Renders an error panel with clear root cause and concrete next steps."""
    fix_html = f"<div style='margin-top: 8px; font-size: 0.85rem; color: var(--arm-text-muted);'><b>Resolution:</b> {how_to_fix}</div>" if how_to_fix else ""
    st.markdown(
        f"""
        <div style="background: var(--arm-danger-bg); border: 1px solid var(--arm-danger-border); border-radius: var(--arm-radius-md); padding: 16px 20px; margin: 12px 0;">
          <div style="display: flex; align-items: center; gap: 8px; font-weight: 700; color: var(--arm-danger-text);">
            :material/error: {message}
          </div>
          {fix_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_card(title: str, subtitle: Optional[str] = None) -> None:
    """Renders a section card container header."""
    sub = f"<div style='font-size: 0.85rem; color: var(--arm-text-caption); margin-top: 2px;'>{subtitle}</div>" if subtitle else ""
    st.markdown(
        f"""
        <div style="background: var(--arm-surface); border: 1px solid var(--arm-border); border-radius: var(--arm-radius-md); padding: 14px 18px; margin-bottom: 16px;">
          <div style="font-size: 0.95rem; font-weight: 700; color: var(--arm-text);">{title}</div>
          {sub}
        </div>
        """,
        unsafe_allow_html=True,
    )


def stat_row(items: List[Dict[str, str]]) -> None:
    """Renders a row of compact statistics."""
    cols = st.columns(len(items))
    for col, item in zip(cols, items):
        with col:
            kpi_card(item.get("label", ""), item.get("value", ""), delta=item.get("delta"), help_text=item.get("help"))


@st.cache_data(ttl=5)
def get_cached_system_status() -> Dict[str, Any]:
    """Caches live environment status queries for 5 seconds to prevent UI latency."""
    # 1. Ollama status
    try:
        ollama_ok, _ = default_client.is_available()
    except Exception:
        ollama_ok = False

    # 2. Database status
    db_status = "mysql"
    try:
        with get_session() as session:
            bind = session.get_bind()
            db_status = bind.dialect.name
    except Exception:
        db_status = "offline"

    # 3. Active Baseline
    try:
        baseline = get_current_baseline()
    except Exception:
        baseline = None

    # 4. Policy version
    try:
        policy = load_policy()
        policy_ver = policy.get("version", "1.0.0")
    except Exception:
        policy_ver = "1.0.0"

    # 5. Last comparison
    last_run_time = "-"
    last_verdict = "-"
    try:
        with get_session() as session:
            last_c = session.query(Comparison).order_by(Comparison.id.desc()).first()
            if last_c and last_c.created_at:
                last_run_time = last_c.created_at.strftime("%H:%M:%S UTC")
                last_verdict = last_c.verdict
    except Exception:
        pass

    return {
        "ollama_ok": ollama_ok,
        "db_status": db_status,
        "baseline_hash": (baseline.get("short_hash") or "-") if baseline else "-",
        "baseline_name": (baseline.get("name") or "None") if baseline else "None",
        "policy_version": policy_ver,
        "last_run_time": last_run_time,
        "last_verdict": last_verdict,
        "active_model": "qwen2.5:3b (Agent Baseline)",
    }


def top_bar() -> None:
    """Renders the top enterprise utility bar showing live infrastructure status chips."""
    init_theme()
    status = get_cached_system_status()

    ollama_chip = status_chip("promote", "Ollama Online") if status["ollama_ok"] else status_chip("block", "Ollama Offline")
    db_chip = status_chip("promote", f"DB: {status['db_status'].upper()}") if status["db_status"] != "offline" else status_chip("block", "DB Offline")
    base_pill = copyable_hash(status["baseline_hash"])

    html = f"""
    <div class="arm-top-shell">
      <div class="arm-top-brand">
        :material/terminal: <span>Skill & Prompt Regression Manager</span>
      </div>
      <div class="arm-top-metrics">
        <div class="arm-top-item">
          <span>Baseline:</span> {base_pill}
        </div>
        <div class="arm-top-item">
          <span>Model:</span> <span class="arm-mono">{status['active_model']}</span>
        </div>
        <div class="arm-top-item">
          {ollama_chip}
        </div>
        <div class="arm-top-item">
          {db_chip}
        </div>
        <div class="arm-top-item">
          <span>Policy:</span> <span class="arm-mono">v{status['policy_version']}</span>
        </div>
        <div class="arm-top-item">
          <span>Last Gate:</span> <b>{status['last_verdict']}</b> <span style="opacity: 0.7;">({status['last_run_time']})</span>
        </div>
      </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)
