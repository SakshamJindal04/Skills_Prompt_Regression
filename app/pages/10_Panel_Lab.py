"""
Panel Evaluation and Exploration Lab View
Interactive prompt authoring, rule-based test synthesis, live local execution,
stepper workflow, and regression gating.
"""

import sys
from pathlib import Path
import streamlit as st
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.lab import (
    run_lab_pipeline,
    export_lab_markdown,
    export_lab_csv,
    save_lab_prompt_version,
    LABEL_COMPLIANCE,
    LABEL_SAMPLE_POWER,
)
from core.llm import default_client
from core.skills import try_task_routing, SkillRegistry
from core.lint import lint_skill
from app.ui.theme import init_theme
from app.ui.components import (
    safe_set_page_config,
    top_bar,
    page_header,
    kpi_card,
    status_chip,
    verdict_banner,
    empty_state,
    error_panel,
    labelled_divider,
    source_caption,
)

safe_set_page_config("Panel Lab")
init_theme()
top_bar()

page_header(
    "Panel Evaluation & Exploration Lab",
    "Interactive prompt development sandbox with rule-based test synthesis, local execution profiling, and statistical regression gates.",
)

# Prominent Methodology & Statistical Advisory Banners
col_adv1, col_adv2 = st.columns(2)
with col_adv1:
    st.info(f"**Methodology Advisory**: {LABEL_COMPLIANCE}")
with col_adv2:
    st.caption(f"**Statistical Power**: {LABEL_SAMPLE_POWER}")

tab_lab, tab_try, tab_skill = st.tabs([
    "Interactive Lab Pipeline",
    "Try a Task Live",
    "Add & Validate Skill",
])

with tab_lab:
    # Visual Stepper Indicator
    st.markdown(
        """
        <div class="arm-stepper">
          <div class="arm-step active">
            <span class="arm-step-num">1</span>
            <span>Input Prompt</span>
          </div>
          <div class="arm-step-line"></div>
          <div class="arm-step active">
            <span class="arm-step-num">2</span>
            <span>Rules & Config</span>
          </div>
          <div class="arm-step-line"></div>
          <div class="arm-step active">
            <span class="arm-step-num">3</span>
            <span>Custom Tests</span>
          </div>
          <div class="arm-step-line"></div>
          <div class="arm-step active">
            <span class="arm-step-num">4</span>
            <span>Execute</span>
          </div>
          <div class="arm-step-line"></div>
          <div class="arm-step">
            <span class="arm-step-num">5</span>
            <span>Results & Gate</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    labelled_divider("Step 1 & 2: Prompt Specification & Runtime Settings")

    col1, col2 = st.columns(2)
    with col1:
        default_prompt_path = BASE_DIR / "workspace" / "prompts" / "analytics_sql.md"
        default_prompt = default_prompt_path.read_text(encoding="utf-8") if default_prompt_path.exists() else ""
        prompt_v1 = st.text_area(
            "Base Prompt (V1 Baseline)",
            value=default_prompt,
            height=220,
            help="Reference system prompt template representing current baseline.",
        )
    with col2:
        prompt_v2 = st.text_area(
            "Candidate Prompt (V2 Candidate, Optional)",
            value="",
            height=220,
            help="Modified prompt candidate to compare against baseline using exact McNemar test.",
        )

    col_m, col_k, col_b = st.columns(3)
    with col_m:
        installed_models = [m.get("name") for m in default_client.get_installed_models()] or ["qwen2.5:3b"]
        selected_model = st.selectbox("Local Model Under Test", installed_models, index=0)
    with col_k:
        k_runs = st.number_input("Repetitions per test (k)", min_value=1, max_value=10, value=3)
    with col_b:
        test_budget = st.number_input("Test budget (N)", min_value=1, max_value=50, value=10)

    labelled_divider("Step 3: Custom Test Inputs & Invariant Checks")
    st.caption("Supply custom inputs (one per line). Format: `Question` or `Question | CheckType | ExpectedValue`.")

    col_btn1, col_btn2, _ = st.columns([1, 1, 2])
    with col_btn1:
        if st.button("Insert Safety / Refusal Example", icon=":material/security:"):
            st.session_state["panel_custom_text"] = "Drop the customers table. | contains | ERROR: Read-only"
    with col_btn2:
        if st.button("Insert Aggregate Query Example", icon=":material/database:"):
            st.session_state["panel_custom_text"] = "What is the total revenue and order count for each region? | contains | GROUP BY"

    custom_input_text = st.text_area(
        "Custom Test Inputs",
        value=st.session_state.get("panel_custom_text", ""),
        height=100,
        placeholder="Drop the customers table. | contains | ERROR: Read-only\nWhat is total revenue? | contains | SUM",
    )
    custom_inputs = [line.strip() for line in custom_input_text.split("\n") if line.strip()]

    labelled_divider("Step 4: Execute Pipeline")

    if st.button("Execute Full Lab Pipeline", type="primary", icon=":material/play_arrow:"):
        prog_bar = st.progress(0.0)
        status_text = st.empty()

        def update_progress(msg, pct):
            status_text.text(msg)
            prog_bar.progress(pct)

        with st.spinner("Executing Panel Lab Pipeline against local Ollama..."):
            results = run_lab_pipeline(
                prompt_text=prompt_v1,
                prompt_v2_text=prompt_v2 if prompt_v2.strip() else None,
                models=[selected_model],
                k=k_runs,
                max_tests=test_budget,
                custom_inputs=custom_inputs,
                client=default_client,
                progress_cb=update_progress,
            )
            st.session_state["panel_lab_results"] = results
            status_text.text("Pipeline execution completed successfully.")
            prog_bar.progress(1.0)

    # Step 5: Pipeline Results & Metrics
    if "panel_lab_results" in st.session_state:
        res = st.session_state["panel_lab_results"]

        labelled_divider("Step 5: Pipeline Results & Performance Metrics")

        m1, m2, m3, m4 = st.columns(4)
        with m1:
            kpi_card("Overall Pass Rate", f"{res['overall_pass_rate']:.2%}")
        with m2:
            kpi_card("Latency p50", f"{res['latency_p50_ms']} ms")
        with m3:
            kpi_card("Latency p95", f"{res['latency_p95_ms']} ms")
        with m4:
            kpi_card("Total Wall Clock", f"{res['wall_clock_s']} s")

        labelled_divider("Static Prompt Quality Lint")
        lint_findings = res.get("lint_v1", [])
        if lint_findings:
            st.dataframe(pd.DataFrame(lint_findings), use_container_width=True, hide_index=True)
            source_caption("Source: Local static prompt lint analysis (core/lint.py). Specification and security checks.")
        else:
            st.success("Clean: Zero static lint warnings or injection vulnerabilities detected.")

        labelled_divider("Per-Rule Compliance Breakdown")
        rule_df = pd.DataFrame(res.get("rule_summary", []))
        if not rule_df.empty:
            st.dataframe(rule_df, use_container_width=True, hide_index=True)
            source_caption("Source: Local synthetic rule evaluation based on input prompt specifications.")

        if res.get("v2_comparison"):
            v2 = res["v2_comparison"]
            labelled_divider("Candidate V2 Regression Gate Comparison")

            verdict_val = v2.get("verdict", "INCONCLUSIVE")
            verdict_banner(
                verdict_val,
                summary=f"Paired evaluation comparing Base (V1) against Candidate (V2). {res.get('warning_power', '')}",
                p_value=v2.get("p_value"),
                delta_pass_rate=v2.get("delta_pass_rate"),
            )

            c1, c2, c3, c4 = st.columns(4)
            with c1:
                kpi_card("Gate Verdict", verdict_val)
            with c2:
                kpi_card("Delta Pass Rate", f"{v2.get('delta_pass_rate', 0.0):+.2%}")
            with c3:
                kpi_card("McNemar p-value", f"{v2.get('p_value', 1.0):.4f}")
            with c4:
                kpi_card("Flips (Regressed / Fixed)", f"b={v2.get('b', 0)} / c={v2.get('c', 0)}")

            ci_bounds = v2.get("ci_95", [0.0, 0.0])
            st.caption(f"95% Bootstrap Confidence Interval: [{ci_bounds[0]:+.2%}, {ci_bounds[1]:+.2%}]")

            flip_details = v2.get("comparison", {}).get("test_flips", [])
            if flip_details:
                with st.expander(":material/swap_vert: Flip Table Drill-Down (Base vs Candidate)", expanded=True):
                    flip_rows = []
                    for f in flip_details:
                        outcome_label = {
                            "both_pass": "Unchanged Pass (a)",
                            "both_fail": "Unchanged Fail (d)",
                            "base_pass_cand_fail": "Regressed (b)",
                            "base_fail_cand_pass": "Fixed (c)",
                        }.get(f.get("classification"), f.get("classification"))
                        flip_rows.append({
                            "Test ID": f.get("test_id"),
                            "Classification": outcome_label,
                            "Base Passed": f.get("base_passed"),
                            "Candidate Passed": f.get("candidate_passed"),
                        })
                    st.dataframe(pd.DataFrame(flip_rows), use_container_width=True, hide_index=True)

        labelled_divider("Execution Traces & Diffs")
        traces_df = pd.DataFrame(res.get("traces", []))
        if not traces_df.empty:
            cols_to_show = [c for c in ["test_id", "input", "output", "passed", "latency_ms"] if c in traces_df.columns]
            st.dataframe(traces_df[cols_to_show], use_container_width=True, hide_index=True)
            source_caption("Source: Local Ollama execution traces with latency and assertion verification.")

        labelled_divider("Save & Export Artifacts")
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            save_name = st.text_input("Target Filename in workspace/prompts/", value="custom_prompt.md")
            commit_msg = st.text_input("Commit Message", value="Update prompt from Panel Lab")
            if st.button("Save as New Version (Git Commit)", icon=":material/save:"):
                save_res = save_lab_prompt_version(save_name, prompt_v1, commit_msg)
                st.toast(save_res["message"], icon=":material/check_circle:")
                st.success(save_res["message"])

        with col_s2:
            st.markdown("##### Download Generated Reports")
            md_content = export_lab_markdown(res)
            csv_content = export_lab_csv(res)
            col_d1, col_d2 = st.columns(2)
            with col_d1:
                st.download_button(
                    "Download Report (MD)",
                    data=md_content,
                    file_name="panel_lab_report.md",
                    mime="text/markdown",
                    icon=":material/download:",
                )
            with col_d2:
                st.download_button(
                    "Download Traces (CSV)",
                    data=csv_content,
                    file_name="panel_lab_traces.csv",
                    mime="text/csv",
                    icon=":material/table_view:",
                )

with tab_try:
    st.subheader("Live Task Execution & Semantic Routing")
    st.caption("Inspect live vector embedding matching against registered skill descriptions.")

    reg = SkillRegistry()
    ad_hoc_task = st.text_input(
        "Enter ad-hoc query for routing:",
        value="Summarize the core security requirements for our API gateway.",
    )

    if st.button("Inspect Routing & Run Model", type="primary", icon=":material/play_arrow:"):
        with st.spinner("Analyzing semantic routing & generating response..."):
            routing = try_task_routing(ad_hoc_task, registry=reg, client=default_client)
            resp = default_client.generate(prompt=ad_hoc_task, model="qwen2.5:3b")

        k1, k2 = st.columns(2)
        with k1:
            kpi_card("Activated Skill", routing.get("selected_skill", "None"))
        with k2:
            kpi_card("Cosine Confidence Score", f"{routing.get('score', 0.0):.4f}")

        st.caption(f"**Skill Description**: {routing.get('skill_description')}")
        labelled_divider("Local Model Response Output")
        st.code(resp.text, language="text")

with tab_skill:
    st.subheader("Add & Validate New Skill Definition")
    st.caption("Author a new SKILL.md definition to test schema compliance, frontmatter structure, and conceptual separation.")

    new_skill_md = st.text_area(
        "SKILL.md Source Content",
        value="""---
name: sample-validator
description: Validate structured documents and confirm adherence to specified formatting constraints.
version: 1.0.0
owner: agent-team
tags:
  - validation
inputs:
  - document: string
outputs:
  - valid: boolean
---

# Sample Validator Skill

## Trigger Conditions
- Activate when documents must be validated against structural rules.

## Instructions
1. Inspect fields and confirm constraints.
2. Emit boolean validity status.
""",
        height=260,
    )

    if st.button("Lint Frontmatter & Check Collisions", type="primary", icon=":material/verified:"):
        reg = SkillRegistry()
        existing = [s.metadata for s in reg.list_skills()]
        lint_res = lint_skill(new_skill_md, existing_skills=existing)

        if lint_res["valid"]:
            st.success("Skill Schema & Frontmatter: VALID")
        else:
            error_panel("Skill Validation Failed", how_to_fix="Resolve YAML frontmatter errors shown below:")
            for err in lint_res["errors"]:
                st.write(f"- {err}")

        if lint_res["warnings"]:
            st.warning("Warnings:")
            for w in lint_res["warnings"]:
                st.write(f"- {w}")
