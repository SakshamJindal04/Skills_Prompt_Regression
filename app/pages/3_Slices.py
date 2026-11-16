"""
Slice Breakdown and Simpson's Paradox Analysis View
Inspect pass-rate deltas across test tags (category, difficulty) and identify regressions hidden behind aggregate pass rates.
"""

import sys
from pathlib import Path
import streamlit as st
import pandas as pd
import plotly.express as px

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.db import get_session
from core.models import Artifact, TestCase, Score
from core.comparator import compare_test_results
from core.scorer import score_artifact_runs
from app.ui.theme import init_theme, get_plotly_template
from app.ui.components import (
    safe_set_page_config,
    top_bar,
    page_header,
    kpi_card,
    status_chip,
    empty_state,
    section_card,
    labelled_divider,
    source_caption,
)

safe_set_page_config("Slices & Simpson's Paradox")
init_theme()
top_bar()

page_header(
    "Slice Breakdown & Simpson's Paradox Analysis",
    "Inspect pass-rate deltas across test slices (categories and difficulty tiers) to uncover localized regressions hidden behind aggregate metrics.",
)

with get_session() as session:
    artifacts = session.query(Artifact).all()
    art_map = {f"#{a.id} ({a.name}, {a.short_hash})": a.id for a in artifacts}

if len(artifacts) < 2:
    empty_state(
        "At least two registered artifacts are required for slice analysis.",
        "Run scripts/seed_demo.py or register new revisions in Versions & Diffs.",
        icon=":material/pie_chart:",
    )
    st.stop()

labels = list(art_map.keys())

with st.container():
    col1, col2 = st.columns(2)
    with col1:
        base_lbl = st.selectbox(
            "Baseline Artifact",
            labels,
            index=0,
            help="Reference artifact against which slices are evaluated.",
        )
    with col2:
        cand_lbl = st.selectbox(
            "Candidate Artifact",
            labels,
            index=min(3, len(labels) - 1),
            help="Candidate artifact being evaluated for sliced regressions.",
        )

base_id = art_map[base_lbl]
cand_id = art_map[cand_lbl]

with get_session() as session:
    raw_tests = session.query(TestCase).all()
    test_cases = [tc.to_dict() for tc in raw_tests]
    base_scores = session.query(Score).filter_by(artifact_id=base_id).all()
    cand_scores = session.query(Score).filter_by(artifact_id=cand_id).all()

if not base_scores:
    score_artifact_runs(base_id, test_cases)
    with get_session() as session:
        base_scores = session.query(Score).filter_by(artifact_id=base_id).all()

if not cand_scores:
    score_artifact_runs(cand_id, test_cases)
    with get_session() as session:
        cand_scores = session.query(Score).filter_by(artifact_id=cand_id).all()

base_run_map = {}
for s in base_scores:
    base_run_map.setdefault(s.test_id, []).append(bool(s.passed))

cand_run_map = {}
for s in cand_scores:
    cand_run_map.setdefault(s.test_id, []).append(bool(s.passed))

comp_res = compare_test_results(test_cases, base_run_map, cand_run_map, k=5)
slices = comp_res.get("slices", [])

# Top KPI row summarizing aggregate vs slice spread
col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns(4)
with col_kpi1:
    kpi_card("Baseline Pass Rate", f"{comp_res['base_pass_rate'] * 100:.1f}%")
with col_kpi2:
    kpi_card("Candidate Pass Rate", f"{comp_res['cand_pass_rate'] * 100:.1f}%")
with col_kpi3:
    kpi_card("Aggregate Delta", f"{comp_res['delta_pass_rate'] * 100:+.1f}%")
with col_kpi4:
    regressed_slices = sum(1 for s in slices if s["delta"] <= -0.10)
    kpi_card(
        "Regressed Slices",
        f"{regressed_slices} / {len(slices)}",
        delta="Warning" if regressed_slices > 0 else "Nominal",
    )

labelled_divider("Slice Breakdown Matrix")

if slices:
    slice_data = []
    plot_data = []
    for s in slices:
        delta_val = s["delta"] * 100
        if s["delta"] <= -0.10:
            status_text = "REGRESSED"
        elif s["delta"] >= 0.10:
            status_text = "IMPROVED"
        else:
            status_text = "STABLE"

        slice_data.append({
            "Slice Tag": s["slice"],
            "Tests Evaluated": s["n_tests"],
            "Baseline Rate": f"{s['base_rate'] * 100:.1f}%",
            "Candidate Rate": f"{s['cand_rate'] * 100:.1f}%",
            "Delta (%)": f"{delta_val:+.1f}%",
            "Status": status_text,
        })

        plot_data.append({
            "Slice": s["slice"],
            "Delta (%)": delta_val,
            "Status": status_text,
        })

    df_slices = pd.DataFrame(slice_data)
    st.dataframe(df_slices, use_container_width=True, hide_index=True)
    source_caption("Source: Local MySQL database 'scores' partitioned by slice tags from tests_data/golden_tests.yaml.")

    # Plotly bar chart with custom styling and Natural Palette
    df_plot = pd.DataFrame(plot_data)
    fig = px.bar(
        df_plot,
        x="Slice",
        y="Delta (%)",
        color="Status",
        color_discrete_map={
            "REGRESSED": "#B4483C",
            "IMPROVED": "#4C8A5E",
            "STABLE": "#5B665F",
        },
        title="Pass Rate Delta (%) Across Evaluation Slices",
    )
    fig.update_layout(
        template=get_plotly_template(),
        yaxis=dict(ticksuffix="%"),
        legend=dict(title=dict(text="Slice Status")),
    )
    st.plotly_chart(fig, use_container_width=True)
    source_caption("Source: Local paired comparison across slices. Evaluates localized degradation independently from aggregate pass rates.")

labelled_divider("Simpson's Paradox Analysis")

with st.container():
    st.markdown(
        r"""
        ### Why Per-Test Slicing Matters: Simpson's Paradox Detection
        In aggregate, the candidate pass rate changed by **{delta:+.1f}%** ({base:.1f}% -> {cand:.1f}%).
        However, analyzing partitioned slices reveals whether localized sub-cohorts suffered severe regressions that were masked by gains in large high-frequency sub-cohorts.

        In production LLM deployments, aggregate metrics frequently conceal critical regressions in edge-case security or syntax parsing queries. Our slice-aware gating policy evaluates both the aggregate McNemar test ($p < 0.05$) and partitioned slice thresholds ($\Delta \le -0.10$) before authorizing promotion.
        """.format(
            delta=comp_res['delta_pass_rate'] * 100,
            base=comp_res['base_pass_rate'] * 100,
            cand=comp_res['cand_pass_rate'] * 100,
        )
    )
