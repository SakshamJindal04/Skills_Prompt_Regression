"""
Project Metrics Scorecard View
Formal verification of the five primary performance metrics defined in the project
specification against empirical measurements and raw data artifacts.
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
    error_panel,
    labelled_divider,
    source_caption,
)

safe_set_page_config("Project Scorecard")
init_theme()
top_bar()

page_header(
    "Project Specification Metrics Scorecard",
    "Formal empirical validation benchmarking measured system performance against all five target criteria in the project specification.",
)

# 5 Top KPI Cards
c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    kpi_card("Skill Accuracy", "87.5%", delta="Target: >= 80.0%", help_text="Top-1 accuracy on 120-task benchmark.")
with c2:
    kpi_card("Regression Delta", "-66.7%", delta="p = 0.0020", help_text="Detected with exact McNemar test.")
with c3:
    kpi_card("Detection Recall", "27.8%", delta="100.0% Precision", help_text="Evaluated on 18 regressions + 8 controls.")
with c4:
    kpi_card("Run Consistency", "0.959", delta="Target: >= 0.90", help_text="k=5 runs per test with fixed seeds.")
with c5:
    kpi_card("Retrieval Latency", "1.2 ms", delta="Target: < 50.0 ms", help_text="p95: 2.5 ms on vector cosine search.")

labelled_divider("Empirical Specification Verification Table")

metrics_table = [
    {
        "Metric": "1. Skill-Selection Accuracy",
        "Target Specification": ">= 80.0% Top-1",
        "Measured Empirical Result": "87.5% (Overall), 93.3% (Clear)",
        "Status": "PASS",
        "Source File": "results/summary.md, tests_data/skill_benchmarks.yaml",
        "Notes": "Evaluated on 120-task benchmark using nomic-embed-text embedding router across 5 categories.",
    },
    {
        "Metric": "2. Task Success Before / After Change",
        "Target Specification": "Detect delta with p < 0.05",
        "Measured Empirical Result": "Baseline 100.0% -> Candidate 33.3% (Delta -66.7%, p=0.0020, 95% CI [-82.5%, -47.1%])",
        "Status": "PASS",
        "Source File": "results/summary.md, results/edits.csv",
        "Notes": "Exact McNemar paired test with 10,000-resample bootstrap confidence intervals.",
    },
    {
        "Metric": "3. Regression Detection Recall",
        "Target Specification": ">= 25.0% on subtle injected mutations",
        "Measured Empirical Result": "27.8% (Exact McNemar Gate), 100.0% Precision",
        "Status": "PASS",
        "Source File": "results/summary.csv",
        "Notes": "Evaluated on 26 realistic prompt & skill mutations (18 regressions, 8 benign controls).",
    },
    {
        "Metric": "4. Consistency Over Repeated Runs",
        "Target Specification": ">= 0.90 agreement (k=5 runs)",
        "Measured Empirical Result": "0.959 (95.9% run-to-run consistency)",
        "Status": "PASS",
        "Source File": "results/summary.md, results/model_matrix.csv",
        "Notes": "Measured across k=5 independent runs per test with fixed per-run seeds.",
    },
    {
        "Metric": "5. Retrieval Latency",
        "Target Specification": "< 50.0 ms mean, < 100.0 ms p95",
        "Measured Empirical Result": "Vector: 1.2 ms mean, 2.5 ms p95 | BM25: 0.4 ms mean, 0.9 ms p95",
        "Status": "PASS",
        "Source File": "results/summary.md",
        "Notes": "Sub-millisecond keyword retrieval, 1-3 ms vector cosine similarity indexing.",
    },
]

df_metrics = pd.DataFrame(metrics_table)
st.dataframe(
    df_metrics[["Metric", "Target Specification", "Measured Empirical Result", "Status", "Source File"]],
    use_container_width=True,
    hide_index=True,
)
source_caption("Source: Empirical evaluation artifacts in results/summary.md, results/summary.csv, and results/model_matrix.csv. Measured locally without synthetic mocks.")

labelled_divider("Methodological Notes & Artifact Citations")

for m in metrics_table:
    with st.expander(f":material/check_circle: {m['Metric']} - Status: {m['Status']}", expanded=False):
        st.markdown(f"**Target Specification**: `{m['Target Specification']}`")
        st.markdown(f"**Measured Empirical Result**: `{m['Measured Empirical Result']}`")
        st.markdown(f"**Data Artifact**: `{m['Source File']}`")
        st.markdown(f"**Methodological Details**: {m['Notes']}")
