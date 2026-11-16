"""
Multi-Model Regression and Evaluation Matrix View
Cross-model performance evaluation across prompt targets, exact McNemar test results,
latency profiling, and LLM judge calibration.
"""

import sys
import json
from pathlib import Path
import streamlit as st
import pandas as pd
import plotly.express as px

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from scripts.model_swap_case_study import run_model_swap_study
from scripts.judge_calibration import run_calibration
from app.ui.theme import init_theme, get_plotly_template
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

safe_set_page_config("Model Matrix")
init_theme()
top_bar()

page_header(
    "Multi-Model Regression & Evaluation Matrix",
    "Cross-model performance matrix evaluating qwen2.5:3b against candidate local weights (llama3.2:3b, gemma2:2b) with McNemar tests and LLM judge calibration.",
)

res_dir = BASE_DIR / "results"
summary_csv = res_dir / "model_summary.csv"
matrix_csv = res_dir / "model_matrix.csv"
swap_md = res_dir / "model_swap.md"
judge_json = res_dir / "judge_calibration.json"
judge_md = res_dir / "judge_calibration.md"

# Actions bar
col_info, col_btn1, col_btn2 = st.columns([2, 1, 1])
with col_info:
    st.caption("Empirical model-swap study across 18 regression suites and 8 benign controls with local Ollama runtime.")

with col_btn1:
    quick_run = st.checkbox("Quick Evaluation Mode (--quick)", value=False)
    if st.button("Run Model Study", type="primary", icon=":material/play_arrow:"):
        with st.spinner("Executing model evaluation across models..."):
            run_model_swap_study(
                base_model="qwen2.5:3b",
                candidate_models=["llama3.2:3b", "gemma2:2b"],
                suite="golden",
                k=3 if quick_run else 5,
                quick=quick_run,
            )
            st.toast("Model study completed.", icon=":material/check_circle:")
            st.rerun()

with col_btn2:
    if st.button("Run Judge Calibration", icon=":material/psychology:"):
        with st.spinner("Running judge calibration on 40 open-ended outputs..."):
            run_calibration(
                model_under_test="qwen2.5:3b",
                judge_model="gemma2:2b",
                total_samples=40,
            )
            st.toast("Judge calibration completed.", icon=":material/check_circle:")
            st.rerun()

# Summary Metrics and Heatmap
if summary_csv.exists():
    df_sum = pd.read_csv(summary_csv)

    overall_df = df_sum[df_sum["prompt_target"] == "ALL_PROMPTS"]
    if not overall_df.empty:
        labelled_divider("Combined Model Performance Summary")
        m_cols = st.columns(len(overall_df))
        for idx, (_, row) in enumerate(overall_df.iterrows()):
            with m_cols[idx]:
                v_text = str(row["verdict"])
                kpi_card(
                    f"Model: {row['model_id']}",
                    f"{row['pass_rate'] * 100:.1f}%",
                    delta=f"Gate: {v_text}",
                    help_text=f"Wilson 95% CI: [{row['ci_lower']*100:.1f}%, {row['ci_upper']*100:.1f}%] | Latency: {row['mean_latency_s']:.2f}s | Flips: b={row['regressed_b']}, c={row['fixed_c']}",
                )

    labelled_divider("Performance Heatmap (Pass Rate % by Prompt & Model)")
    pivot_df = df_sum[df_sum["prompt_target"] != "ALL_PROMPTS"].pivot(
        index="prompt_target", columns="model_id", values="pass_rate"
    )
    if not pivot_df.empty:
        pivot_pct = pivot_df * 100
        fig_heat = px.imshow(
            pivot_pct,
            text_auto=".1f",
            color_continuous_scale="Viridis",
            labels=dict(x="Model Architecture", y="Prompt Target", color="Pass Rate (%)"),
            title="Pass Rate (%) Across Prompt Targets and Models",
            aspect="auto",
        )
        fig_heat.update_layout(template=get_plotly_template(), height=450)
        st.plotly_chart(fig_heat, use_container_width=True)
        source_caption("Source: results/model_summary.csv. Matrix of empirical pass rates across models and prompt tasks.")

    labelled_divider("Latency & Consistency Comparison")
    col_lat, col_cons = st.columns(2)
    with col_lat:
        fig_lat = px.bar(
            df_sum[df_sum["prompt_target"] != "ALL_PROMPTS"],
            x="prompt_target",
            y="mean_latency_s",
            color="model_id",
            barmode="group",
            title="Mean Latency (s) by Prompt and Model",
            labels={"mean_latency_s": "Mean Latency (s)", "prompt_target": "Prompt Target"},
            color_discrete_sequence=["#3F6B57", "#3E6E8C", "#B8862B"],
        )
        fig_lat.update_layout(template=get_plotly_template())
        col_lat.plotly_chart(fig_lat, use_container_width=True)
        with col_lat:
            source_caption("Source: results/model_summary.csv. Mean end-to-end execution latency per call.")

    with col_cons:
        fig_cons = px.bar(
            df_sum[df_sum["prompt_target"] != "ALL_PROMPTS"],
            x="prompt_target",
            y="consistency",
            color="model_id",
            barmode="group",
            title="Run-to-Run Consistency Score",
            labels={"consistency": "Consistency", "prompt_target": "Prompt Target"},
            color_discrete_sequence=["#3F6B57", "#3E6E8C", "#B8862B"],
        )
        fig_cons.update_layout(template=get_plotly_template())
        col_cons.plotly_chart(fig_cons, use_container_width=True)
        with col_cons:
            source_caption("Source: results/model_summary.csv. Run-to-run consistency across k=5 repetitions.")

    labelled_divider("Model Performance Matrix")
    format_df = df_sum.copy()
    format_df["Wilson 95% CI"] = format_df.apply(
        lambda r: f"[{r['ci_lower']*100:.1f}%, {r['ci_upper']*100:.1f}%]", axis=1
    )
    format_df["Pass Rate (%)"] = (format_df["pass_rate"] * 100).round(1)
    format_df["Consistency"] = format_df["consistency"].round(3)
    format_df["Mean Latency (s)"] = format_df["mean_latency_s"].round(2)
    format_df["p95 Latency (s)"] = format_df["p95_latency_s"].round(2)
    format_df["Skill Acc (%)"] = (format_df["skill_activation_acc"] * 100).round(1)

    display_cols = [
        "prompt_target",
        "model_id",
        "model_digest",
        "Pass Rate (%)",
        "Wilson 95% CI",
        "Consistency",
        "Mean Latency (s)",
        "p95 Latency (s)",
        "Skill Acc (%)",
        "regressed_b",
        "fixed_c",
        "p_value",
        "verdict",
    ]
    st.dataframe(format_df[display_cols], use_container_width=True, hide_index=True)
    source_caption("Source: results/model_summary.csv. Evaluated on qwen2.5:3b, llama3.2:3b, gemma2:2b with k=5 repetitions.")

else:
    empty_state(
        "No model matrix summary found.",
        "Click 'Run Model Study' above to generate empirical results.",
        icon=":material/analytics:",
    )

labelled_divider("Flip Table Drill-Down")

if matrix_csv.exists():
    df_raw = pd.read_csv(matrix_csv)
    models_in_data = df_raw["model_id"].unique().tolist()
    candidates = [m for m in models_in_data if m != "qwen2.5:3b"]

    if candidates:
        col_c_sel, col_t_sel = st.columns(2)
        with col_c_sel:
            selected_cand = st.selectbox(
                "Candidate Model to Compare Against qwen2.5:3b",
                candidates,
            )
        with col_t_sel:
            filter_outcome = st.selectbox("Filter Outcome", ["All Flips", "Regressed Only (b)", "Fixed Only (c)"])

        base_df = df_raw[df_raw["model_id"] == "qwen2.5:3b"]
        cand_df = df_raw[df_raw["model_id"] == selected_cand]

        base_maj = base_df.groupby("test_id")["passed"].apply(lambda s: s.sum() >= ((len(s) // 2) + 1))
        cand_maj = cand_df.groupby("test_id")["passed"].apply(lambda s: s.sum() >= ((len(s) // 2) + 1))

        flips = []
        for tid in base_maj.index:
            if tid in cand_maj.index:
                b_pass = bool(base_maj[tid])
                c_pass = bool(cand_maj[tid])
                if b_pass and not c_pass:
                    flips.append({"test_id": tid, "outcome": "regressed", "baseline": "PASS", "candidate": "FAIL"})
                elif not b_pass and c_pass:
                    flips.append({"test_id": tid, "outcome": "fixed", "baseline": "FAIL", "candidate": "PASS"})

        if flips:
            df_flips = pd.DataFrame(flips)
            if filter_outcome == "Regressed Only (b)":
                df_flips = df_flips[df_flips["outcome"] == "regressed"]
            elif filter_outcome == "Fixed Only (c)":
                df_flips = df_flips[df_flips["outcome"] == "fixed"]

            st.dataframe(df_flips, use_container_width=True, hide_index=True)
            st.caption(f"Showing {len(df_flips)} test outcome flips between qwen2.5:3b and {selected_cand}.")
        else:
            st.info(f"No flips observed between qwen2.5:3b and {selected_cand}.")
else:
    empty_state("Raw matrix data not available.", icon=":material/table_rows:")

labelled_divider("LLM Judge Calibration (Deterministic vs LLM Judge)")
st.caption("Calibration evaluated on 40 open-ended outputs using zero-temperature cross-family LLM judge (gemma2:2b).")

if judge_json.exists():
    try:
        j_data = json.loads(judge_json.read_text(encoding="utf-8"))
        jc1, jc2, jc3, jc4 = st.columns(4)
        with jc1:
            kpi_card("Evaluated Outputs", str(j_data.get("total_evaluated", 40)))
        with jc2:
            kpi_card("Observed Agreement (p_o)", f"{j_data.get('observed_agreement', 0.0) * 100:.1f}%")
        with jc3:
            kpi_card("Chance Agreement (p_e)", f"{j_data.get('chance_agreement', 0.0) * 100:.1f}%")
        with jc4:
            kappa_val = j_data.get("cohen_kappa", 0.0)
            kpi_card(
                "Cohen's Kappa (kappa)",
                f"{kappa_val:.4f}",
                delta="Moderate / Substantial" if kappa_val >= 0.6 else "Fair Agreement",
            )

        conf = j_data.get("confusion_matrix", {})
        st.markdown("#### 2x2 Contingency Matrix")
        mat_df = pd.DataFrame({
            "Deterministic Pass (D=1)": [conf.get("tp", 0), conf.get("fn", 0)],
            "Deterministic Fail (D=0)": [conf.get("fp", 0), conf.get("tn", 0)],
        }, index=["Judge Pass (J=1)", "Judge Fail (J=0)"])
        st.table(mat_df)
        source_caption("Source: results/judge_calibration.json. 2x2 contingency matrix comparing deterministic checks to gemma2:2b judge.")

        if judge_md.exists():
            with st.expander(":material/description: Full Judge Calibration Report Markdown", expanded=False):
                st.markdown(judge_md.read_text(encoding="utf-8"))
    except Exception as e:
        error_panel(f"Error loading judge calibration: {e}")
else:
    empty_state("Judge calibration data not yet generated.", icon=":material/psychology:")

labelled_divider("Export Benchmark Artifacts")
e_col1, e_col2, e_col3 = st.columns(3)
if summary_csv.exists():
    with e_col1:
        st.download_button(
            "Download Summary CSV",
            data=summary_csv.read_text(encoding="utf-8"),
            file_name="model_summary.csv",
            mime="text/csv",
            icon=":material/download:",
        )
if matrix_csv.exists():
    with e_col2:
        st.download_button(
            "Download Raw Matrix CSV",
            data=matrix_csv.read_text(encoding="utf-8"),
            file_name="model_matrix.csv",
            mime="text/csv",
            icon=":material/table_view:",
        )
if swap_md.exists():
    with e_col3:
        st.download_button(
            "Download Case Study Markdown",
            data=swap_md.read_text(encoding="utf-8"),
            file_name="model_swap.md",
            mime="text/markdown",
            icon=":material/description:",
        )
