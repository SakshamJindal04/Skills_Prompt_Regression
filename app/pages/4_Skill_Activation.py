"""
Skill Activation and Routing Benchmark View
Measure skill activation accuracy, inspect pairwise conceptual overlaps,
evaluate retrieval latency, and test live routing across skills catalog.
"""

import sys
from pathlib import Path
import streamlit as st
import pandas as pd
import yaml
import plotly.express as px

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.skills import (
    SkillRegistry,
    EmbeddingSelector,
    BM25Selector,
    EmbeddingLLMSelector,
    run_skill_benchmark,
    compute_skill_overlap_matrix,
    try_task_routing,
    benchmark_scalability,
)
from core.runner import get_llm_adapter, execute_agent_loop
from core.llm import default_client
from app.ui.theme import init_theme, get_plotly_template
from app.ui.components import (
    safe_set_page_config,
    top_bar,
    page_header,
    kpi_card,
    status_chip,
    empty_state,
    error_panel,
    labelled_divider,
)

safe_set_page_config("Skill Activation")
init_theme()
top_bar()

page_header(
    "Skill Activation & Semantic Routing",
    "Empirically evaluate semantic routing accuracy, measure retrieval latency, inspect pairwise overlap matrices, and test live tool/skill dispatch.",
)

registry = SkillRegistry()
skills = registry.list_skills()

tab_try, tab_overlap, tab_eval, tab_scale, tab_registry = st.tabs([
    "Try a Task",
    "Overlap & Similarity Matrix",
    "120-Task Benchmark",
    "Scalability (N=6, 12, 24)",
    "Skills Catalog",
])

with tab_try:
    st.subheader("Ad-Hoc Task Routing Inspector")
    st.caption("Submit natural language instructions to evaluate router scoring, cosine confidence distributions, and live agent executions.")

    task_input = st.text_input(
        "Enter task query",
        value="Extract quarterly revenue, operating expenses, and margins from this report into a Markdown table.",
        help="Input query evaluated against registered skill descriptions and triggers.",
    )

    col1, col2 = st.columns(2)
    with col1:
        with_skill = st.checkbox(
            "Inject Selected Skill Instructions into Prompt",
            value=True,
            help="When checked, appends the resolved skill documentation and rules into the system context.",
        )
    with col2:
        sel_mode = st.selectbox(
            "Routing Engine",
            ["Embedding (nomic-embed-text)", "BM25 Baseline", "Embedding + LLM Re-rank"],
            help="Select the vector embedding or lexical retrieval model for candidate selection.",
        )

    if st.button("Inspect Routing & Execute Live", type="primary", icon=":material/play_arrow:"):
        with st.spinner("Analyzing semantic routing & executing agent loop..."):
            routing_info = try_task_routing(task_input, registry=registry, client=default_client)
            adapter = get_llm_adapter()
            output, skills_used, lat = execute_agent_loop(
                task_input,
                adapter,
                registry,
                with_skill=with_skill,
            )

        col_a, col_b, col_c = st.columns(3)
        with col_a:
            kpi_card("Selected Skill", routing_info.get("selected_skill", "None"))
        with col_b:
            kpi_card("Cosine Similarity Score", f"{routing_info.get('score', 0.0):.4f}")
        with col_c:
            kpi_card("Execution Latency", f"{lat:.1f} ms")

        st.markdown(f"**Trigger Assessment**: {routing_info.get('trigger_assessment', '')}")

        ranked_cands = routing_info.get("ranked_candidates", [])
        if ranked_cands:
            st.subheader("Top Ranked Skill Candidates")
            df_cands = pd.DataFrame([
                {"Skill Name": c[0], "Cosine Similarity": float(c[1])}
                for c in ranked_cands
            ])

            # Horizontal bar chart showing candidate similarity distribution
            fig_cand = px.bar(
                df_cands,
                x="Cosine Similarity",
                y="Skill Name",
                orientation="h",
                title="Skill Activation Confidence Scores",
                text="Cosine Similarity",
            )
            fig_cand.update_traces(texttemplate="%{text:.4f}", textposition="outside")
            fig_cand.update_layout(
                template=get_plotly_template(),
                xaxis=dict(range=[0, 1.05], title=dict(text="Cosine Similarity")),
                yaxis=dict(autorange="reversed", title=dict(text="Candidate Skill")),
            )
            st.plotly_chart(fig_cand, use_container_width=True)

        labelled_divider("Live Agent Response Output")
        st.code(output, language="text")

with tab_overlap:
    st.subheader("Pairwise Skill Conceptual Overlap Matrix")
    st.caption("Flags semantic collisions and ambiguity. Any pair with cosine similarity > 0.75 is highlighted with disambiguation guidance.")

    if st.button("Compute Overlap Matrix", type="primary", icon=":material/calculate:"):
        with st.spinner("Computing high-dimensional embedding similarity matrix..."):
            matrix_res = compute_skill_overlap_matrix(registry=registry, threshold=0.75, client=default_client)
            st.session_state["overlap_matrix"] = matrix_res

    if "overlap_matrix" in st.session_state:
        m_data = st.session_state["overlap_matrix"]
        names = m_data["skills"]
        mat = m_data["matrix"]
        overlaps = m_data["overlaps"]

        # Heatmap plot using standard Viridis scale
        fig_heat = px.imshow(
            mat,
            x=names,
            y=names,
            color_continuous_scale="Viridis",
            zmin=0.0,
            zmax=1.0,
            title="Pairwise Skill Cosine Similarity Heatmap",
            labels=dict(x="Registered Skill", y="Registered Skill", color="Similarity"),
        )
        fig_heat.update_layout(
            template=get_plotly_template(),
            height=550,
        )
        st.plotly_chart(fig_heat, use_container_width=True)

        labelled_divider("Ambiguity & Collision Alerts")
        if overlaps:
            for o in overlaps:
                st.warning(
                    f"**{o['skill_a']}** <-> **{o['skill_b']}** (Cosine Similarity: `{o['similarity']:.4f}`)\n\n"
                    f"- **Warning**: {o['warning']}\n"
                    f"- **Remediation**: {o['suggestion']}"
                )
        else:
            st.success("All registered skill pairs maintain cosine separation below the 0.75 ambiguity threshold.")

with tab_eval:
    st.subheader("120-Task Comprehensive Routing Benchmark")
    st.caption("Rigorous evaluation across 120 standardized tasks spanning clear, ambiguous, noisy, multi-skill, and abstention cohorts.")

    bm_file = BASE_DIR / "tests_data" / "skill_benchmarks.yaml"
    if bm_file.exists():
        bm_data = yaml.safe_load(bm_file.read_text(encoding="utf-8"))
        items = bm_data.get("benchmarks", [])
        st.info(f"Loaded {len(items)} standardized routing benchmark tasks.")

        if st.button("Run 120-Task Routing Benchmark", type="primary", icon=":material/speed:"):
            results = []
            for m in ["embedding", "bm25"]:
                with st.spinner(f"Evaluating routing accuracy for {m}..."):
                    res = run_skill_benchmark(items, selector_method=m, registry=registry, client=default_client)
                    results.append(res)
            st.session_state["skill_bm_120"] = results

        if "skill_bm_120" in st.session_state:
            res_list = st.session_state["skill_bm_120"]
            df_res = pd.DataFrame([
                {
                    "Method": r["method"].title(),
                    "Top-1 Accuracy": f"{r['top1'] * 100:.1f}%",
                    "Top-3 Accuracy": f"{r['top3'] * 100:.1f}%",
                    "Mean Latency (ms)": f"{r['latency_mean']:.1f}",
                    "p50 Latency (ms)": f"{r['latency_p50']:.1f}",
                    "p95 Latency (ms)": f"{r['latency_p95']:.1f}",
                }
                for r in res_list
            ])
            st.dataframe(df_res, use_container_width=True, hide_index=True)

            emb_res = next((r for r in res_list if r["method"] == "embedding"), res_list[0])
            labelled_divider("Category Breakdown (Embedding Router)")
            cat_rows = []
            for cat, c_data in emb_res.get("categories", {}).items():
                cat_rows.append({
                    "Evaluation Category": cat.replace("_", " ").title(),
                    "Total Tasks": c_data["total"],
                    "Passed": c_data["correct"],
                    "Top-1 Accuracy": f"{c_data['top1_accuracy'] * 100:.1f}%",
                    "Top-3 Accuracy": f"{c_data['top3_accuracy'] * 100:.1f}%",
                })
            st.dataframe(pd.DataFrame(cat_rows), use_container_width=True, hide_index=True)

            confs = emb_res.get("top_confusions", [])
            if confs:
                labelled_divider("Top Routing Confusion Patterns")
                st.dataframe(pd.DataFrame(confs), use_container_width=True, hide_index=True)
    else:
        empty_state("Skill benchmark dataset not found.", "Expected at tests_data/skill_benchmarks.yaml.")

with tab_scale:
    st.subheader("Scalability Benchmark: Latency vs Catalog Size (N = 6, 12, 24)")
    st.caption("Validates constant-time vector search and linear sub-millisecond scaling across synthesized distractor skills.")

    if st.button("Execute Scalability Scaling Test", type="primary", icon=":material/stacked_line_chart:"):
        with st.spinner("Benchmarking retrieval latency across N = 6, 12, 24 skills..."):
            scale_res = benchmark_scalability(skill_counts=[6, 12, 24], registry=registry, client=default_client)
            st.session_state["scale_res"] = scale_res

    if "scale_res" in st.session_state:
        s_data = st.session_state["scale_res"]["scalability_results"]
        df_s = pd.DataFrame(s_data)
        st.dataframe(df_s, use_container_width=True, hide_index=True)

        fig_scale = px.line(
            df_s,
            x="num_skills",
            y=["mean_latency_ms", "p95_latency_ms"],
            markers=True,
            title="Retrieval Latency Scaling Profile",
            labels={"value": "Latency (ms)", "num_skills": "Registered Skills (N)"},
        )
        fig_scale.update_layout(
            template=get_plotly_template(),
            legend=dict(title=dict(text="Metric")),
        )
        st.plotly_chart(fig_scale, use_container_width=True)

with tab_registry:
    st.subheader(f"Registered Skills Catalog ({len(skills)} Active)")
    st.caption("Active skills loaded from workspace/skills/ with semantic schema, tags, and operational instructions.")

    for s in skills:
        with st.expander(f"{s.name}: {s.description}", expanded=False):
            st.markdown(f"**Filesystem Path**: `{s.path}`")
            st.markdown(f"**Maintainer**: `{s.metadata.get('owner', 'core')}` | **Version**: `{s.metadata.get('version', '1.0.0')}`")
            st.code(s.body, language="markdown")
