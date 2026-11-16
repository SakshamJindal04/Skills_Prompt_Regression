"""
Run Comparison and Statistical Gate Verification View
Paired evaluation between baseline and candidate artifacts, exact McNemar test,
bootstrap confidence intervals, flip table drill-downs, and ablation attribution.
"""

import sys
from pathlib import Path
import streamlit as st
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.db import get_session
from core.models import Artifact, Trace, TestCase, Score
from core.comparator import compare_test_results
from core.gate import evaluate_gate
from core.attribution import ablate_and_attribute
from core.repo import list_versions
from core.runner import run_test, sync_tests_to_db
from core.scorer import score_artifact_runs
from app.ui.theme import init_theme
from app.ui.components import (
    safe_set_page_config,
    top_bar,
    page_header,
    kpi_card,
    status_chip,
    verdict_banner,
    copyable_hash,
    labelled_divider,
    empty_state,
    error_panel,
)

safe_set_page_config("Run Comparison")
init_theme()
top_bar()

page_header(
    "Run Comparison & Regression Gate",
    "Statistically rigorous paired evaluation using exact McNemar tests, 95% bootstrap confidence intervals, and flip table drill-downs.",
)

with get_session() as session:
    artifacts = session.query(Artifact).order_by(Artifact.id.desc()).all()
    art_map = {f"#{a.id} ({a.name}, {a.short_hash})": a.id for a in artifacts}

if len(artifacts) < 2:
    empty_state(
        "At least two registered artifacts are required for paired comparison.",
        "Author a new version in Versions & Diffs or run the benchmark seed suite.",
        icon=":material/compare_arrows:",
    )
    st.stop()

labels = list(art_map.keys())

# Live Test Execution Expander
with st.expander(":material/play_arrow: Run Live Tests on Artifact / Commit", expanded=False):
    st.caption("Executes the test suite against local Ollama with wall-clock profiling and fixed seeds.")
    col_r1, col_r2, col_r3 = st.columns([2, 1, 1])
    target_art_lbl = col_r1.selectbox("Target Artifact", labels, index=min(3, len(labels) - 1))
    target_art_id = art_map[target_art_lbl]
    quick_run = col_r2.checkbox("Quick Mode (20 tests, k=3)", value=True)

    if col_r3.button("Execute Tests Now", type="primary"):
        sync_tests_to_db()
        with get_session() as session:
            all_tests = [tc.to_dict() for tc in session.query(TestCase).all()]
        k_val = 3 if quick_run else 5
        tests_to_run = all_tests[:20] if quick_run else all_tests

        progress_bar = st.progress(0.0)
        status_msg = st.empty()

        for idx, tc in enumerate(tests_to_run):
            status_msg.text(f"Running test {idx+1}/{len(tests_to_run)}: {tc['id']} ({k_val} runs)...")
            run_test(target_art_id, tc, k=k_val, model_id="qwen2.5:3b", use_cache=False)
            progress_bar.progress((idx + 1) / len(tests_to_run))

        score_artifact_runs(target_art_id, tests_to_run)
        status_msg.success(f"Completed {len(tests_to_run)} tests ({len(tests_to_run) * k_val} live calls).")
        st.rerun()

labelled_divider("Comparison Configuration")

col1, col2, col3 = st.columns([2, 2, 1])
l_base = col1.selectbox("Baseline Artifact (Control)", labels, index=0)
l_cand = col2.selectbox("Candidate Artifact (Under Test)", labels, index=min(3, len(labels) - 1))
alpha = col3.number_input("Significance Alpha", value=0.05, step=0.01, min_value=0.001, max_value=0.20)

base_id = art_map[l_base]
cand_id = art_map[l_cand]

# Load tests and traces from DB
with get_session() as session:
    raw_tests = session.query(TestCase).all()
    test_cases = [tc.to_dict() for tc in raw_tests]
    base_scores = session.query(Score).filter_by(artifact_id=base_id).all()
    cand_scores = session.query(Score).filter_by(artifact_id=cand_id).all()
    base_traces = session.query(Trace).filter_by(artifact_id=base_id).all()
    cand_traces = session.query(Trace).filter_by(artifact_id=cand_id).all()

# Compute scores if traces exist but scores missing
if not base_scores and base_traces:
    score_artifact_runs(base_id, test_cases)
    with get_session() as session:
        base_scores = session.query(Score).filter_by(artifact_id=base_id).all()

if not cand_scores and cand_traces:
    score_artifact_runs(cand_id, test_cases)
    with get_session() as session:
        cand_scores = session.query(Score).filter_by(artifact_id=cand_id).all()

base_run_map = {}
for s in base_scores:
    base_run_map.setdefault(s.test_id, []).append(bool(s.passed))

cand_run_map = {}
for s in cand_scores:
    cand_run_map.setdefault(s.test_id, []).append(bool(s.passed))

base_out_map = {tr.test_id: (tr.output or "") for tr in base_traces}
cand_out_map = {tr.test_id: (tr.output or "") for tr in cand_traces}

comp_res = compare_test_results(test_cases, base_run_map, cand_run_map, k=5)
verdict, report_md = evaluate_gate(comp_res, alpha=alpha, candidate_id=cand_id, baseline_id=base_id)

# Statistical Metric Cards
k1, k2, k3, k4 = st.columns(4)
with k1:
    kpi_card(
        label="Baseline Pass Rate",
        value=f"{comp_res['base_pass_rate'] * 100:.1f}%",
        delta=f"Artifact #{base_id}",
        help_text="Proportion of tests passed by baseline via majority vote",
    )
with k2:
    kpi_card(
        label="Candidate Pass Rate",
        value=f"{comp_res['cand_pass_rate'] * 100:.1f}%",
        delta=f"Artifact #{cand_id}",
        help_text="Proportion of tests passed by candidate via majority vote",
    )
with k3:
    d_val = comp_res['delta_pass_rate'] * 100
    ci_low = comp_res['ci_delta'][0] * 100
    ci_high = comp_res['ci_delta'][1] * 100
    kpi_card(
        label="Delta Pass Rate (95% CI)",
        value=f"{d_val:+.1f}%",
        delta=f"[{ci_low:+.1f}%, {ci_high:+.1f}%]",
        help_text="Empirical difference in pass rate with 10,000-resample bootstrap confidence intervals",
    )
with k4:
    p_val = comp_res["p_value"]
    kpi_card(
        label="McNemar p-value",
        value=f"{p_val:.4f}",
        delta=f"b={comp_res['regressed_count']}, c={comp_res['fixed_count']}",
        help_text="Exact two-sided binomial p-value testing discordant pairs (b vs c)",
    )

st.markdown("<div style='margin-bottom: 16px;'></div>", unsafe_allow_html=True)

# Prominent Verdict Banner
if verdict == "BLOCK":
    summary_text = (
        f"Candidate rejected: {comp_res['regressed_count']} regressions observed against {comp_res['fixed_count']} fixes. "
        f"Exact McNemar test confirms statistically significant degradation or critical test failure (p = {p_val:.4f} <= {alpha:.2f})."
    )
else:
    summary_text = (
        f"Candidate approved for baseline promotion: {comp_res['fixed_count']} fixes observed with {comp_res['regressed_count']} regressions. "
        f"Delta pass rate: {comp_res['delta_pass_rate'] * 100:+.1f}% (p = {p_val:.4f})."
    )

verdict_banner(
    verdict=verdict,
    summary=summary_text,
    p_value=p_val,
    delta_pass_rate=comp_res["delta_pass_rate"],
)

if comp_res["hidden_flips_detected"]:
    st.warning(":material/warning: **Simpson's Paradox Alert**: The aggregate pass rate appears stable, but individual test cases suffered regressions that were masked by other tests.")

tab_flips, tab_slices, tab_ablation, tab_report = st.tabs([
    "Flip Table & Output Comparison",
    "Slices Breakdown",
    "Change Attribution (Ablation)",
    "Generated Gate Report",
])

with tab_flips:
    st.subheader("Flip Table: Test-by-Test Behavior Comparison")
    st.caption("Inspect individual test flips between the baseline and candidate outputs.")

    f_col1, f_col2 = st.columns([2, 1])
    flip_filter = f_col1.radio(
        "Filter Outcomes",
        ["All Tests", "Regressed (Pass -> Fail)", "Fixed (Fail -> Pass)", "Unchanged (Pass <-> Pass)"],
        horizontal=True,
    )

    flips = comp_res["flips"]
    if flip_filter == "Regressed (Pass -> Fail)":
        flips = [f for f in flips if f["outcome"] == "regressed"]
    elif flip_filter == "Fixed (Fail -> Pass)":
        flips = [f for f in flips if f["outcome"] == "fixed"]
    elif flip_filter == "Unchanged (Pass <-> Pass)":
        flips = [f for f in flips if f["outcome"] == "unchanged"]

    # Export Flip Table CSV
    if flips:
        export_rows = [
            {
                "Test ID": f["test_id"],
                "Target": f.get("target", ""),
                "Outcome": f["outcome"].upper(),
                "Critical": f.get("critical", False),
                "Base Runs Passed": f.get("base_runs_passed", 0),
                "Cand Runs Passed": f.get("cand_runs_passed", 0),
            }
            for f in flips
        ]
        df_export = pd.DataFrame(export_rows)
        f_col2.download_button(
            ":material/download: Download Flip Table CSV",
            data=df_export.to_csv(index=False),
            file_name=f"flip_table_{base_id}_vs_{cand_id}.csv",
            mime="text/csv",
        )

    if not flips:
        empty_state(f"No test cases matching outcome filter '{flip_filter}'.")
    else:
        for f in flips:
            tid = f["test_id"]
            outcome = f["outcome"]
            crit_badge = " [CRITICAL]" if f.get("critical") else ""
            
            outcome_icons = {
                "regressed": ":material/trending_down: REGRESSED",
                "fixed": ":material/trending_up: FIXED",
                "unchanged": ":material/check: UNCHANGED PASS",
                "still_failing": ":material/close: UNCHANGED FAIL",
            }
            outcome_label = outcome_icons.get(outcome, outcome.upper())
            header = f"{tid} ({f.get('target', 'prompt')}){crit_badge} — {outcome_label}"

            with st.expander(header, expanded=(outcome == "regressed")):
                col_o1, col_o2 = st.columns(2)
                col_o1.markdown("**Baseline Output (Old)**")
                col_o1.code(base_out_map.get(tid, "(empty output)"), language="text")

                col_o2.markdown("**Candidate Output (New)**")
                col_o2.code(cand_out_map.get(tid, "(empty output)"), language="text")

with tab_slices:
    st.subheader("Performance by Test Slice")
    st.caption("Slice pass-rate deltas across test difficulty, categories, and tags.")

    slices_list = comp_res.get("slices", [])
    if slices_list:
        df_sl = pd.DataFrame([
            {
                "Slice Tag": s["slice"],
                "Test Count": s["n_tests"],
                "Baseline Pass Rate": f"{s['base_rate'] * 100:.1f}%",
                "Candidate Pass Rate": f"{s['cand_rate'] * 100:.1f}%",
                "Delta (%)": f"{s['delta'] * 100:+.1f}%",
                "Verdict": "REGRESSED" if s["delta"] <= -0.10 else ("IMPROVED" if s["delta"] >= 0.10 else "STABLE"),
            }
            for s in slices_list
        ])
        st.dataframe(df_sl, use_container_width=True, hide_index=True)
    else:
        empty_state("No slice metadata defined on the evaluated tests.")

with tab_ablation:
    st.subheader("Multi-File Change Attribution via Ablation")
    st.caption("Reverts one changed file at a time from baseline to candidate to isolate which modification caused the performance change.")

    commits = list_versions()
    if len(commits) >= 2:
        sha_labels = {f"{c['short_hash']} - {c['message'][:35]}": c['git_hash'] for c in commits}
        col_a1, col_a2 = st.columns(2)
        base_c = col_a1.selectbox("Base Commit", list(sha_labels.keys()), index=min(1, len(sha_labels) - 1))
        bad_c = col_a2.selectbox("Bad Commit", list(sha_labels.keys()), index=0)

        if st.button("Run Ablation Attribution", type="primary"):
            with st.spinner("Executing ablation test runs across candidate files..."):
                ablation_res = ablate_and_attribute(
                    base_commit=sha_labels[base_c],
                    bad_commit=sha_labels[bad_c],
                )

            st.markdown(f"**Primary Culprit File**: <code class='arm-mono'>{ablation_res.get('guilty_file', 'None')}</code>", unsafe_allow_html=True)
            impacts = ablation_res.get("file_impacts", [])
            if impacts:
                df_imp = pd.DataFrame([
                    {
                        "Modified File": imp["file"],
                        "Ablated Pass Rate": f"{imp['ablated_pass_rate'] * 100:.1f}%",
                        "Recovery Delta": f"{imp['recovery_delta'] * 100:+.1f}%",
                    }
                    for imp in impacts
                ])
                st.dataframe(df_imp, use_container_width=True, hide_index=True)
    else:
        empty_state("Need at least two Git commits in workspace to execute ablation.")

with tab_report:
    st.subheader("Complete Regression Gate Report (report.md)")
    st.markdown(report_md)
    st.download_button(
        ":material/download: Download report.md",
        data=report_md,
        file_name="report.md",
        mime="text/markdown",
    )
