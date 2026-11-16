"""
Environments, Baseline Registry & Releases
Manages multi-environment baseline registries (Dev, Staging, Prod),
stage-gated promotions, SemVer suggestions, and Skill-by-Model compatibility matrices.
"""

import sys
from pathlib import Path
import streamlit as st
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.ui.theme import init_theme
from app.ui.components import (
    safe_set_page_config,
    top_bar,
    page_header,
    kpi_card,
    status_chip,
    empty_state,
    labelled_divider,
    copyable_hash,
)
from core.environments import (
    get_environment_baselines,
    promote_baseline,
    suggest_semver,
    compute_skill_model_compatibility,
)
from core.db import get_session
from core.models import Artifact, Comparison

safe_set_page_config("Environments & Releases")
init_theme()
top_bar()

page_header(
    "Environments, Baselines & Releases",
    "Track active baselines across Dev, Staging, and Prod environments, enforce stage gates, and audit skill-by-model compatibility.",
)

baselines = get_environment_baselines()

# Environment Overview Cards
c1, c2, c3 = st.columns(3)
with c1:
    dev_b = baselines.get("dev")
    st.markdown("### :material/developer_board: Development")
    if dev_b:
        kpi_card("Dev Version", f"v{dev_b['semver']}", help=f"Hash: {dev_b['git_hash'][:8]}")
        st.caption(f"Promoted by: `{dev_b['promoted_by']}` on {dev_b['promoted_at'][:19]}")
    else:
        st.info("No active Dev baseline set.")

with c2:
    stag_b = baselines.get("staging")
    st.markdown("### :material/science: Staging")
    if stag_b:
        kpi_card("Staging Version", f"v{stag_b['semver']}", help=f"Hash: {stag_b['git_hash'][:8]}")
        st.caption(f"Promoted by: `{stag_b['promoted_by']}` on {stag_b['promoted_at'][:19]}")
    else:
        st.info("No active Staging baseline set.")

with c3:
    prod_b = baselines.get("prod")
    st.markdown("### :material/rocket_launch: Production")
    if prod_b:
        kpi_card("Production Version", f"v{prod_b['semver']}", help=f"Hash: {prod_b['git_hash'][:8]}")
        st.caption(f"Promoted by: `{prod_b['promoted_by']}` on {prod_b['promoted_at'][:19]}")
    else:
        st.info("No active Production baseline set.")

labelled_divider("Lifecycle Operations")

tab_promote, tab_compat, tab_notes = st.tabs([
    "Promote Baseline (Stage Gate)",
    "Skill-by-Model Matrix",
    "Release Notes & SemVer",
])

with tab_promote:
    st.markdown("#### Stage Gate Promotion Workflow")
    st.caption("Promoting an artifact from one environment to the next requires a verified PROMOTE gate verdict.")

    # Fetch artifacts
    with get_session() as session:
        artifacts = session.query(Artifact).order_by(Artifact.id.desc()).limit(20).all()
        art_options = {f"#{a.id} - {a.name} ({a.short_hash})": a.id for a in artifacts}

        # Fetch passing comparisons
        passing_comps = session.query(Comparison).filter_by(verdict="PROMOTE").order_by(Comparison.id.desc()).limit(20).all()
        comp_options = {f"Comparison #{c.id} (Delta: {c.delta_pass_rate:+.1%}, p={c.p_value:.3f})": c.id for c in passing_comps}

    with st.form("promotion_form"):
        col_p1, col_p2 = st.columns(2)
        with col_p1:
            target_env = st.selectbox("Target Environment", options=["dev", "staging", "prod"])
            selected_art_str = st.selectbox("Artifact to Promote", options=list(art_options.keys()))
            selected_art_id = art_options[selected_art_str] if selected_art_str else None

        with col_p2:
            approver_name = st.text_input("Approver Identity", value="release_manager")
            custom_semver = st.text_input("Semantic Version (optional, e.g. 1.2.0)", placeholder="Auto-generated if empty")
            selected_comp_str = st.selectbox(
                "Gate Comparison Evidence (Required for Staging/Prod)",
                options=["(Auto-detect latest passing gate)"] + list(comp_options.keys()),
            )

        promo_comment = st.text_area("Promotion Rationale / Release Justification", placeholder="Describe why this artifact satisfies release criteria...")

        submit_promo = st.form_submit_button(":material/publish: Execute Gated Promotion", use_container_width=True)

        if submit_promo:
            if not promo_comment.strip():
                st.error("Promotion rationale is mandatory.")
            elif not selected_art_id:
                st.error("Select a valid artifact.")
            else:
                cid = None
                if selected_comp_str and selected_comp_str != "(Auto-detect latest passing gate)":
                    cid = comp_options.get(selected_comp_str)
                try:
                    res = promote_baseline(
                        to_env=target_env,
                        artifact_id=selected_art_id,
                        approver=approver_name,
                        comment=promo_comment,
                        comparison_id=cid,
                        semver=custom_semver if custom_semver.strip() else None,
                    )
                    st.success(f"Successfully promoted artifact #{selected_art_id} to '{target_env.upper()}' as v{res['semver']}!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Promotion rejected: {e}")

with tab_compat:
    st.markdown("#### Skill-by-Model Capability & Compatibility Matrix")
    st.caption("Empirical pass rates, latency, and deployment certification across local models.")

    compat_data = compute_skill_model_compatibility()
    df_compat = pd.DataFrame(compat_data)
    
    # Format columns
    df_display = df_compat.copy()
    df_display["Pass Rate"] = df_display["pass_rate"].apply(lambda v: f"{v * 100:.1f}%")
    df_display["Avg Latency"] = df_display["avg_latency_ms"].apply(lambda v: f"{v:.1f} ms")
    df_display["Certification"] = df_display["status"]
    
    st.dataframe(
        df_display[["skill", "model", "Pass Rate", "Avg Latency", "samples", "Certification"]],
        use_container_width=True,
        hide_index=True,
    )

with tab_notes:
    st.markdown("#### Automated Semantic Versioning & Release Notes")
    
    col_s1, col_s2 = st.columns([1, 1])
    with col_s1:
        st.markdown("**SemVer Suggester:**")
        c_ver = st.text_input("Current Base Version", value="1.0.0")
        ch_type = st.selectbox("Change Type", options=["patch", "minor", "major"])
        has_crit = st.checkbox("Has critical test regressions?", value=False)
        is_break = st.checkbox("Breaking interface changes?", value=False)
        
        sug = suggest_semver(
            current_version=c_ver,
            change_type=ch_type,
            critical_regressions=1 if has_crit else 0,
            breaking_change=is_break,
        )
        st.info(f"**Recommended Version:** `v{sug['suggested_version']}` ({sug['bump_type'].upper()})\n\n{sug['rationale']}")

    with col_s2:
        st.markdown("**Active Environment Release Notes:**")
        selected_env_notes = st.selectbox("View Release Notes for Environment", options=["prod", "staging", "dev"])
        target_b = baselines.get(selected_env_notes)
        if target_b and target_b.get("release_notes"):
            st.code(target_b["release_notes"], language="markdown")
        else:
            st.caption(f"No release notes recorded for {selected_env_notes} yet.")
