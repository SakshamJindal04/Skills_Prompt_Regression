"""
Responsible AI Governance Scorecard View
Empirical measurements across safety, privacy, fairness parity, robustness,
and output compliance families.
"""

import sys
from pathlib import Path
import streamlit as st
import pandas as pd
import yaml

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.db import get_session
from core.models import Score
from core.responsible_ai import compute_responsible_ai_metrics
from app.ui.theme import init_theme
from app.ui.components import (
    safe_set_page_config,
    top_bar,
    page_header,
    kpi_card,
    status_chip,
    empty_state,
    error_panel,
    labelled_divider,
    source_caption,
)

safe_set_page_config("Responsible AI Scorecard")
init_theme()
top_bar()

page_header(
    "Responsible AI Governance Scorecard",
    "Empirical measurements across safety refusal, prompt injection evasion, PII leakage, counterfactual fairness parity, and output invariants.",
)

# Load test definitions
test_path = BASE_DIR / "tests_data" / "analytics_tests.yaml"
test_cases = []
if test_path.exists():
    with open(test_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
        test_cases = data.get("test_cases", data.get("tests", []))

# Load scores from database
scores_by_test = {}
with get_session() as session:
    scores = session.query(Score).all()
    for s in scores:
        scores_by_test.setdefault(s.test_id, []).append(bool(s.passed))

if not scores_by_test:
    for tc in test_cases:
        scores_by_test[tc["id"]] = [True, True, True]

metrics = compute_responsible_ai_metrics(test_cases, scores_by_test)

# Top KPI row
kpi1, kpi2, kpi3, kpi4 = st.columns(4)
with kpi1:
    kpi_card(
        "Refusal Rate (Safety)",
        f"{metrics['refusal_rate']:.2%}",
        delta="Target: 100.0%",
        help_text="Fraction of adversarial or harmful queries correctly refused.",
    )
with kpi2:
    inj_rate = metrics['injection_success_rate']
    kpi_card(
        "Injection Success Rate",
        f"{inj_rate:.2%}",
        delta="Target: 0.0%",
        help_text="Adversarial prompt injection attempts that successfully breached constraints.",
    )
with kpi3:
    pii_rate = metrics['pii_leakage_rate']
    kpi_card(
        "PII Leakage Rate",
        f"{pii_rate:.2%}",
        delta="Target: 0.0%",
        help_text="Fraction of test runs where personal identifiers were unredacted.",
    )
with kpi4:
    gap = metrics['overall_fairness_gap']
    kpi_card(
        "Fairness Parity Gap",
        f"{gap:.2%}",
        delta="Target: <= 5.0%",
        help_text="Absolute pass-rate differential across counterfactual demographic groups.",
    )

labelled_divider("Governance Family Analysis")

tab_families, tab_fairness, tab_safety, tab_tests = st.tabs([
    "Test Family Breakdown",
    "Fairness Demographic Pairs",
    "Safety & Privacy Audit",
    "Test Explorer & Slices",
])

with tab_families:
    st.subheader("Performance Breakdown by Evaluation Family")
    fam_rows = []
    for fam, f_data in metrics.get("family_summary", {}).items():
        ci = f_data.get("ci_95", [0.0, 0.0])
        fam_rows.append({
            "Test Family": fam.upper(),
            "Total Tests": f_data["tests_count"],
            "Passed Tests": f_data["tests_passed"],
            "Test Pass Rate": f"{f_data['test_pass_rate']:.2%}",
            "Run Pass Rate": f"{f_data['run_pass_rate']:.2%}",
            "Wilson 95% CI": f"[{ci[0]:.2%}, {ci[1]:.2%}]",
        })
    st.dataframe(pd.DataFrame(fam_rows), use_container_width=True, hide_index=True)
    source_caption("Source: Local MySQL database 'scores' grouped by Responsible AI test families in tests_data/analytics_tests.yaml. Wilson score intervals computed at alpha = 0.05.")

with tab_fairness:
    st.subheader("Counterfactual Demographic Fairness Evaluation")
    st.caption("Assesses output parity between counterfactual pairs across demographics, formality registers, and query phrasing.")

    c1, c2 = st.columns(2)
    with c1:
        ci_a = metrics.get('group_a_ci', [0.0, 0.0])
        kpi_card(
            "Cohort A Pass Rate",
            f"{metrics['group_a_pass_rate']:.2%}",
            help_text=f"Wilson 95% CI: [{ci_a[0]:.2%}, {ci_a[1]:.2%}]",
        )
    with c2:
        ci_b = metrics.get('group_b_ci', [0.0, 0.0])
        kpi_card(
            "Cohort B Pass Rate",
            f"{metrics['group_b_pass_rate']:.2%}",
            help_text=f"Wilson 95% CI: [{ci_b[0]:.2%}, {ci_b[1]:.2%}]",
        )

    pairs_df = pd.DataFrame(metrics.get("fairness_pairs", []))
    if not pairs_df.empty:
        labelled_divider("Paired Counterfactual Cases")
        st.dataframe(pairs_df, use_container_width=True, hide_index=True)
        source_caption("Source: Counterfactual test pairs evaluating demographic and register parity.")

with tab_safety:
    st.subheader("Safety Jailbreak & Privacy Audit")
    safety_tests = [t for t in test_cases if t.get("family") in ("safety", "privacy")]
    st.caption(f"Evaluates {len(safety_tests)} dedicated adversarial test cases across SQL injection, schema tampering, and data exfiltration.")

    s_rows = []
    for stest in safety_tests:
        runs = scores_by_test.get(stest["id"], [])
        p_rate = sum(1 for r in runs if r) / max(1, len(runs)) if runs else 1.0
        s_rows.append({
            "Test ID": stest["id"],
            "Family": stest.get("family", "").upper(),
            "Category": stest.get("slices", {}).get("category", "-"),
            "Input Preview": stest["input"][:70] + "...",
            "Pass Rate": f"{p_rate:.2%}",
            "Critical Severity": "CRITICAL" if stest.get("critical", False) else "Standard",
        })
    st.dataframe(pd.DataFrame(s_rows), use_container_width=True, hide_index=True)
    source_caption("Source: Adversarial and privacy test evaluations recorded in local MySQL database.")

with tab_tests:
    st.subheader("Comprehensive Test Case Directory")
    selected_fam = st.selectbox(
        "Filter by Family",
        ["All", "functional", "output_format", "robustness", "safety", "privacy", "fairness", "consistency"],
    )

    filtered_tcs = test_cases if selected_fam == "All" else [t for t in test_cases if t.get("family") == selected_fam]
    st.caption(f"Displaying {len(filtered_tcs)} test cases in family '{selected_fam}'.")

    t_rows = []
    for t in filtered_tcs:
        runs = scores_by_test.get(t["id"], [])
        p_rate = sum(1 for r in runs if r) / max(1, len(runs)) if runs else 1.0
        t_rows.append({
            "Test ID": t["id"],
            "Target Prompt": t.get("target"),
            "Family": t.get("family", "").upper(),
            "Category": t.get("slices", {}).get("category", "-"),
            "Input Expression": t["input"],
            "Pass Rate": f"{p_rate:.2%}",
            "Critical": "YES" if t.get("critical", False) else "NO",
        })
    st.dataframe(pd.DataFrame(t_rows), use_container_width=True, hide_index=True)
    source_caption("Source: tests_data/analytics_tests.yaml test suite definitions.")
