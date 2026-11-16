"""
Rollback Workflow View
Perform non-destructive rollbacks (Git revert) to restore verified baselines,
preview expected metric recovery, and re-verify compliance with explicit dialog confirmation.
"""

import sys
from pathlib import Path
import streamlit as st
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.db import get_session
from core.models import Artifact, Comparison, Score
from core.repo import (
    init_repo,
    list_versions,
    get_diff,
    revert_commit,
    get_workspace_path,
    sync_repo_to_db,
)
from core.versioner import register_artifact, get_current_baseline, set_current_baseline
from app.ui.theme import init_theme
from app.ui.components import (
    safe_set_page_config,
    top_bar,
    page_header,
    kpi_card,
    status_chip,
    copyable_hash,
    empty_state,
    error_panel,
    labelled_divider,
    source_caption,
)

safe_set_page_config("Rollback Workflow")
init_theme()
top_bar()

page_header(
    "Rollback & Incident Remediation Workflow",
    "Non-destructively revert faulty commits (via git revert), preview recovered metric baselines, and re-establish gate integrity.",
)

ws = get_workspace_path()
repo = init_repo(str(ws))
commits = list_versions()
current_baseline = get_current_baseline()

if not commits:
    empty_state(
        "No Git commits found in workspace/.",
        "Commit prompt or skill revisions in Versions & Diffs first.",
        icon=":material/history:",
    )
    st.stop()

# Baseline & HEAD status cards
col_base, col_head = st.columns(2)
with col_base:
    st.markdown("#### Active Baseline Artifact")
    if current_baseline:
        kpi_card(
            f"Baseline: #{current_baseline['id']} ({current_baseline['name']})",
            current_baseline['short_hash'],
            delta="Production Active",
            help_text=f"Full Hash: {current_baseline.get('git_hash', '')}",
        )
    else:
        st.info("No active baseline registered in database.")

with col_head:
    st.markdown("#### Current Workspace HEAD")
    head_commit = commits[0]
    files_str = ", ".join(head_commit["files_changed"]) if head_commit["files_changed"] else "none"
    kpi_card(
        f"HEAD: {head_commit['short_hash']} by {head_commit['author']}",
        head_commit["message"][:28] + ("..." if len(head_commit["message"]) > 28 else ""),
        delta=f"{len(head_commit['files_changed'])} files modified",
        help_text=f"Files: {files_str}",
    )

labelled_divider("1. Target Revision Selection & Metric Impact")

commit_options = {
    f"{c['short_hash']} - {c['message'][:60]} ({c['created_at'][:10]})": c
    for c in commits
}

selected_label = st.selectbox(
    "Select commit to inspect for revert:",
    list(commit_options.keys()),
    index=min(1, len(commit_options) - 1) if len(commit_options) > 1 else 0,
    help="Select the specific regression commit to be inverted via git revert.",
)
selected_commit = commit_options[selected_label]

with get_session() as session:
    recent_comps = session.query(Comparison).order_by(Comparison.id.desc()).limit(10).all()
    comp_dicts = [c.to_dict() for c in recent_comps]

if comp_dicts:
    latest_c = comp_dicts[0]
    st.markdown(
        f"""
        <div style="background: var(--arm-surface); border: 1px solid var(--arm-border); border-radius: var(--arm-radius-md); padding: 14px 18px; margin: 12px 0;">
          <div style="font-weight: 700; color: var(--arm-text); font-size: 0.95rem;">Expected Metric Recovery Profile</div>
          <div style="font-size: 0.88rem; color: var(--arm-text-caption); margin-top: 4px;">
            The latest evaluation gate recorded delta pass rate: <b>{latest_c['delta_pass_rate']:+.2%}</b>
            (Regressed tests: <b>{latest_c['regressed_count']}</b>, Fixed: <b>{latest_c['fixed_count']}</b>, Gate verdict: <b>{latest_c['verdict']}</b>).
            Reverting commit <code>{selected_commit['short_hash']}</code> will non-destructively invert these regressions and restore baseline reliability.
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with st.expander(f":material/code: Diff of Commit {selected_commit['short_hash']}", expanded=False):
    commit_diff = get_diff(selected_commit["git_hash"])
    st.code(commit_diff or "No text diff available (initial commit or empty).", language="diff")

labelled_divider("2. Confirmation & Rollback Execution")

# Rollback Dialog with confirmation and required justification
@st.dialog("Execute Rollback Confirmation")
def rollback_dialog(target_commit):
    st.warning(
        f"You are about to revert commit **{target_commit['short_hash']}**:\n\n"
        f"\"{target_commit['message']}\"\n\n"
        "This creates a non-destructive inverse commit in Git, updates workspace files, and registers a recovered baseline artifact."
    )
    justification = st.text_area(
        "Incident Justification / Reason (Mandatory):",
        placeholder="e.g. Critical regression detected on security/drop_table slice during gate comparison.",
    )
    custom_msg = st.text_input(
        "Git Commit Message:",
        value=f"Revert '{target_commit['message']}' (hash: {target_commit['short_hash']})",
    )

    col_dia1, col_dia2 = st.columns([1, 1])
    with col_dia1:
        if st.button("Cancel", use_container_width=True):
            st.rerun()
    with col_dia2:
        if st.button("Confirm Rollback", type="primary", use_container_width=True):
            if not justification.strip():
                st.error("Rollback justification is required before executing remediation.")
            else:
                try:
                    with st.spinner("Executing non-destructive git revert..."):
                        new_hexsha = revert_commit(
                            git_hash=target_commit["git_hash"],
                            message=f"{custom_msg}\n\nJustification: {justification}",
                        )
                        sync_repo_to_db()

                        prompt_files = list((ws / "prompts").glob("*.md"))
                        if prompt_files:
                            new_art_id, _ = register_artifact(
                                [f"prompts/{p.name}" for p in prompt_files],
                                artifact_type="prompt",
                                name="prompt_reverted",
                            )
                            set_current_baseline(new_art_id, notes=f"Rollback of {target_commit['short_hash']}: {justification}")
                            st.success(f"Rollback executed successfully! Created commit {new_hexsha[:7]} and baseline artifact #{new_art_id}.")
                        else:
                            st.success(f"Rollback executed successfully! Created commit {new_hexsha[:7]}.")
                    st.toast("Rollback completed successfully.", icon=":material/check_circle:")
                    st.rerun()
                except Exception as e:
                    st.error(f"Rollback execution failed: {e}")

if st.button("Trigger Rollback Dialog...", type="primary", icon=":material/undo:"):
    rollback_dialog(selected_commit)

labelled_divider("3. Post-Rollback Verification Scores")
st.caption("Verify test suite compliance and pass rate stabilization on registered artifacts.")

with get_session() as session:
    all_arts = session.query(Artifact).order_by(Artifact.id.desc()).limit(5).all()
    art_list = [a.to_dict() for a in all_arts]

if art_list:
    sel_art_id = st.selectbox(
        "Select artifact to inspect verification scores:",
        [a["id"] for a in art_list],
        format_func=lambda aid: f"Artifact #{aid} - {next((a['name'] for a in art_list if a['id'] == aid), '')}",
    )
    with get_session() as session:
        scores = session.query(Score).filter_by(artifact_id=sel_art_id).all()
        score_dicts = [s.to_dict() for s in scores]

    if score_dicts:
        df_scores = pd.DataFrame(score_dicts)
        pass_rate = (df_scores["passed"].sum() / len(df_scores)) * 100.0 if len(df_scores) > 0 else 0.0
        kpi_card("Artifact Empirical Pass Rate", f"{pass_rate:.1f}%")
        st.dataframe(
            df_scores[["test_id", "run_index", "passed", "score"]],
            use_container_width=True,
            hide_index=True,
        )
        source_caption("Source: Local MySQL database 'scores' table for post-rollback verification.")
    else:
        empty_state(
            "No test runs recorded for this artifact.",
            "Run live tests in Run Comparison to score this artifact.",
            icon=":material/history_edu:",
        )
