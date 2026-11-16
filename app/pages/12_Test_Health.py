"""
Test Suite Health and Flakiness Monitor View
Identify non-deterministic flaky assertions, isolate quarantined tests,
and audit dead-weight or stale assertions against recent prompt revisions.
"""

import sys
from pathlib import Path
import streamlit as st
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.health import analyze_test_health
from core.policy import load_policy
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

safe_set_page_config("Test Health")
init_theme()
top_bar()

page_header(
    "Test Suite Health & Flakiness Monitor",
    "Identify stochastic test flakiness, quarantine unstable assertions, and prune dead-weight or stale test cases across prompt iterations.",
)

policy = load_policy()
quarantine_threshold = policy.get("quarantine_consistency_threshold", 0.70)

health_data = analyze_test_health(quarantine_threshold=quarantine_threshold)
summary = health_data["summary"]

# Top 5 KPI metric cards
k1, k2, k3, k4, k5 = st.columns(5)
with k1:
    kpi_card("Evaluated Tests", str(summary["total_evaluated"]), help_text="Total test suite assertions analyzed.")
with k2:
    flaky_c = summary["flaky_count"]
    kpi_card(
        "Flaky Tests",
        str(flaky_c),
        delta="Requires Attention" if flaky_c > 0 else "Nominal",
        help_text="Tests with 20% - 80% pass rate indicating non-determinism.",
    )
with k3:
    q_c = summary["quarantined_count"]
    kpi_card(
        "Quarantined",
        str(q_c),
        delta="Excluded from Gate" if q_c > 0 else "Zero Quarantined",
        help_text=f"Tests with consistency < {quarantine_threshold:.2f}.",
    )
with k4:
    kpi_card(
        "Always Pass (Trivial)",
        str(summary["always_pass_count"]),
        help_text="Tests with 100% pass rate providing low discriminative power.",
    )
with k5:
    stale_c = summary["stale_count"]
    kpi_card(
        "Stale Tests",
        str(stale_c),
        delta="Needs Review" if stale_c > 0 else "Aligned",
        help_text="Tests unrevised after 3+ prompt revisions.",
    )

labelled_divider("Test Suite Health Diagnostics")

tab_flaky, tab_quarantine, tab_always, tab_stale = st.tabs([
    "Flaky Tests (20% - 80%)",
    "Quarantined Assertions",
    "Always Pass / Always Fail",
    "Stale Test Revisions",
])

with tab_flaky:
    st.subheader("Stochastic & Flaky Assertions")
    st.caption("Tests exhibiting 20% - 80% pass rates across identical seeds indicating prompt ambiguity or model hallucination.")
    flaky = health_data["flaky"]
    if flaky:
        st.dataframe(pd.DataFrame(flaky), use_container_width=True, hide_index=True)
        source_caption("Source: Local MySQL database 'scores' table analyzed across repeated test iterations.")
    else:
        st.success("Zero flaky tests detected across repeated runs.")

with tab_quarantine:
    st.subheader(f"Quarantined Assertions (Consistency < {quarantine_threshold:.2f})")
    st.caption("Quarantined tests remain recorded for diagnostic telemetry but are excluded from blocking gate promotion decisions.")
    quarantined = health_data["quarantined"]
    if quarantined:
        st.dataframe(pd.DataFrame(quarantined), use_container_width=True, hide_index=True)
        source_caption("Source: Policy quarantine rule evaluating consistency threshold in policy.yaml.")
    else:
        st.info("No test assertions currently meet the quarantine threshold.")

with tab_always:
    col_p, col_f = st.columns(2)
    with col_p:
        st.subheader("Always Pass Tests (Potential Dead Weight)")
        st.caption("Tests with 100% pass rate across all models and prompt variations.")
        ap = health_data["always_pass"]
        st.caption(f"Count: {len(ap)} assertions")
        if ap:
            st.dataframe(
                pd.DataFrame(ap)[["test_id", "target", "pass_rate", "recommendation"]],
                use_container_width=True,
                hide_index=True,
            )
            source_caption("Source: Empirical pass-rate profiling across all test runs in MySQL database.")
    with col_f:
        st.subheader("Always Fail Tests (Unachievable or Broken)")
        st.caption("Tests with 0% pass rate indicating outdated specs or impossible invariants.")
        af = health_data["always_fail"]
        st.caption(f"Count: {len(af)} assertions")
        if af:
            st.dataframe(
                pd.DataFrame(af)[["test_id", "target", "pass_rate", "recommendation"]],
                use_container_width=True,
                hide_index=True,
            )
            source_caption("Source: Empirical pass-rate profiling across all test runs in MySQL database.")

with tab_stale:
    st.subheader("Stale Test Assertions")
    st.caption("Tests whose target prompt has undergone 3 or more commit revisions without test case synchronization.")
    stale = health_data["stale"]
    if stale:
        st.dataframe(pd.DataFrame(stale), use_container_width=True, hide_index=True)
        source_caption("Source: Git commit revision history in workspace/ correlated with test metadata.")
    else:
        st.success("All test cases remain synchronized with recent prompt revisions.")
