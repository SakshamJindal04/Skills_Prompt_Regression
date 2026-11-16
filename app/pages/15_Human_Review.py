"""
Human Review Queue & Inter-Rater Reliability (Cohen's Kappa)
Allows human domain experts to audit undecidable or flagged model/judge evaluations,
label outputs, override scores with cryptographic audit logging, and track judge agreement.
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
)
from core.review_queue import (
    list_review_items,
    submit_human_review,
    compute_cohens_kappa,
)

safe_set_page_config("Human Review Queue")
init_theme()
top_bar()

page_header(
    "Human Review & Judge Calibration",
    "Audit flagged or borderline model decisions, record expert ground-truth labels, and evaluate LLM-Judge reliability via Cohen's Kappa.",
)

# Fetch current review queue items
pending_items = list_review_items(status="pending")
reviewed_items = list_review_items(status="reviewed")
kappa_stats = compute_cohens_kappa(reviewed_items)

# Top KPI metrics
c1, c2, c3, c4 = st.columns(4)
with c1:
    kpi_card("Pending Queue", len(pending_items), help="Decisions awaiting human verification")
with c2:
    kpi_card("Reviewed Count", len(reviewed_items), help="Historical human reviews recorded")
with c3:
    kpi_card("Cohen's Kappa (κ)", f"{kappa_stats['kappa']:.3f}", delta=kappa_stats['interpretation'])
with c4:
    kpi_card("Observed Agreement", f"{kappa_stats['observed_agreement'] * 100:.1f}%", help="Raw concordance between Judge and Human")

labelled_divider("Review Queue Management")

tab_pending, tab_history, tab_metrics = st.tabs([
    f"Pending Review Queue ({len(pending_items)})",
    f"Reviewed History ({len(reviewed_items)})",
    "Inter-Rater Agreement Matrix",
])

with tab_pending:
    if not pending_items:
        empty_state(
            "Review Queue Clear",
            "No pending evaluations flagged for human intervention at this time.",
            icon=":material/task_alt:",
        )
    else:
        st.write(f"Displaying **{len(pending_items)}** items requiring human adjudication:")
        for idx, item in enumerate(pending_items):
            with st.expander(f"Review Item #{item['id']} — Test: {item['test_id']} ({item['flag_reason']})", expanded=(idx == 0)):
                st.markdown(f"**Flag Reason:** `{item['flag_reason']}`")
                st.markdown(f"**Judge Verdict:** {'PASS' if item.get('judge_passed') else 'FAIL'} (Score: {item.get('judge_score')})")
                
                st.markdown("**Model Output / Trajectory:**")
                st.code(item.get("model_output") or "No output stored", language="text")

                with st.form(f"review_form_{item['id']}"):
                    fcol1, fcol2 = st.columns([1, 1])
                    with fcol1:
                        decision = st.radio(
                            "Human Label",
                            options=["PASS", "FAIL"],
                            horizontal=True,
                            key=f"decision_{item['id']}",
                        )
                        reviewer = st.text_input("Reviewer ID", value="auditor_lead", key=f"rev_{item['id']}")
                    with fcol2:
                        comment = st.text_area("Review Rationale / Notes", placeholder="State justification for this evaluation label...", key=f"comm_{item['id']}")
                        override = st.checkbox("Override score in database and audit ledger", value=True, key=f"ov_{item['id']}")

                    submitted = st.form_submit_button(":material/how_to_reg: Commit Human Decision", use_container_width=True)
                    if submitted:
                        if not comment.strip():
                            st.error("A review rationale is mandatory before committing.")
                        else:
                            try:
                                submit_human_review(
                                    review_id=item["id"],
                                    human_passed=(decision == "PASS"),
                                    reviewer_id=reviewer,
                                    comment=comment,
                                    override_score=override,
                                )
                                st.success(f"Review #{item['id']} recorded successfully.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error submitting review: {e}")

with tab_history:
    if not reviewed_items:
        empty_state(
            "No Historical Reviews",
            "Completed reviews will be archived here alongside their audit linkages.",
            icon=":material/history:",
        )
    else:
        df_history = pd.DataFrame([
            {
                "Review ID": it["id"],
                "Test ID": it["test_id"],
                "Reviewer": it["reviewer_id"],
                "Human Decision": "PASS" if it.get("human_passed") else "FAIL",
                "Judge Passed": "PASS" if it.get("judge_passed") else "FAIL",
                "Concordance": "AGREED" if it.get("human_passed") == it.get("judge_passed") else "OVERRIDDEN",
                "Comment": it.get("comment"),
                "Timestamp": it.get("reviewed_at"),
            }
            for it in reviewed_items
        ])
        st.dataframe(df_history, use_container_width=True, hide_index=True)

with tab_metrics:
    st.markdown("#### LLM Judge vs Human Inter-Rater Reliability")
    st.markdown(
        "Cohen's kappa (κ) measures inter-rater agreement for categorical items, taking into account the agreement occurring by chance:"
    )
    
    mc1, mc2 = st.columns([1, 1])
    with mc1:
        ct = kappa_stats.get("contingency_table", {})
        st.markdown("**Contingency Matrix:**")
        df_cm = pd.DataFrame(
            [
                {"Judge": "PASS", "Human PASS": ct.get("both_pass", 0), "Human FAIL": ct.get("judge_only", 0)},
                {"Judge": "FAIL", "Human PASS": ct.get("human_only", 0), "Human FAIL": ct.get("both_fail", 0)},
            ]
        ).set_index("Judge")
        st.table(df_cm)

    with mc2:
        st.markdown("**Statistical Coefficients:**")
        st.markdown(f"- **Evaluated Pairs ($N$):** `{kappa_stats['n']}`")
        st.markdown(f"- **Observed Concordance ($P_o$):** `{kappa_stats['observed_agreement']:.4f}`")
        st.markdown(f"- **Hypothetical Chance Agreement ($P_e$):** `{kappa_stats['expected_agreement']:.4f}`")
        st.markdown(f"- **Cohen's Kappa ($\\kappa$):** `{kappa_stats['kappa']:.4f}`")
        st.markdown(f"- **Benchmark Classification:** `{kappa_stats['interpretation']}`")
