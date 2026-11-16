"""
Change Requests and Multi-Party Approval Workflow View
Submit changes, run policy-driven regression gating, and enforce authorized approval before promoting baselines.
"""

import sys
from pathlib import Path
import streamlit as st

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.workflow import (
    submit_change_request,
    run_change_request_gate,
    approve_change_request,
    reject_change_request,
    list_change_requests,
    get_change_request,
)
from core.policy import load_approvers, load_policy
from core.repo import list_versions, get_workspace_path
from core.versioner import get_current_baseline
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
)

safe_set_page_config("Change Requests")
init_theme()
top_bar()

page_header(
    "Change Requests & Governance Approvals",
    "Submit prompt and skill revisions, evaluate policy regression gates, and enforce two-person authorization rules before baseline promotion.",
)

# Policy Info Banner
policy = load_policy()
policy_freeze = bool(policy.get("freeze", False))

with st.container():
    col_p1, col_p2, col_p3 = st.columns(3)
    with col_p1:
        kpi_card("Policy Version", f"v{policy.get('version', '1.0.0')}")
    with col_p2:
        kpi_card("Significance Threshold", f"alpha = {policy.get('alpha', 0.05)}")
    with col_p3:
        freeze_status = "FREEZE ACTIVE" if policy_freeze else "Operational"
        kpi_card("Promotion Freeze", freeze_status, delta="Policy Lock" if policy_freeze else "Normal")

tab_list, tab_submit = st.tabs([
    "Review & Gating Queue",
    "Submit New Change Request",
])

with tab_submit:
    st.subheader("Submit Revision for Regression Gating")
    st.caption("Select base commit and candidate revision to initiate automated policy checks.")

    commits = list_versions(str(get_workspace_path()))
    if not commits:
        empty_state("No git commits found in workspace.", icon=":material/history:")
    else:
        commit_options = [c["short_hash"] + " - " + c["message"][:40] for c in commits]
        commit_map = {c["short_hash"] + " - " + c["message"][:40]: c["git_hash"] for c in commits}

        c1, c2 = st.columns(2)
        with c1:
            selected_base_label = st.selectbox(
                "Base Commit (Baseline)",
                options=commit_options,
                index=0,
                key="sb_base",
                help="Reference commit representing current active behavior.",
            )
        with c2:
            selected_cand_label = st.selectbox(
                "Candidate Commit",
                options=commit_options,
                index=min(1, len(commit_options) - 1),
                key="sb_cand",
                help="New revision to be evaluated for regressions.",
            )

        requester = st.text_input(
            "Requester Name / Identity",
            value="Alice Engineer",
            help="Author of the change request. Enforces separation-of-duties during approval.",
        )
        run_immediately = st.checkbox(
            "Execute automated regression gate immediately upon submission",
            value=True,
        )

        if st.button("Submit Change Request", type="primary", icon=":material/send:"):
            base_hash = commit_map.get(selected_base_label, selected_base_label[:7])
            cand_hash = commit_map.get(selected_cand_label, selected_cand_label[:7])

            if base_hash == cand_hash:
                st.error("Base commit and candidate commit must be distinct versions.")
            else:
                with st.spinner("Registering change request in database..."):
                    cr_id = submit_change_request(base_hash, cand_hash, requester=requester)
                    st.toast(f"Change request #{cr_id} submitted.", icon=":material/check_circle:")

                    if run_immediately:
                        with st.spinner("Executing automated policy gate..."):
                            try:
                                verdict, _ = run_change_request_gate(cr_id, quick=True)
                                st.info(f"Automated gate completed with verdict: {verdict}")
                            except Exception as e:
                                st.warning(f"Gate evaluation note: {e}")
                    st.rerun()

with tab_list:
    st.subheader("Change Request Management & Queue")
    st.caption("Inspect submitted requests, review statistical gate findings, and approve promotions.")

    f_col1, f_col2 = st.columns([1, 2])
    with f_col1:
        status_filter = st.selectbox(
            "Filter by Lifecycle Status",
            options=["All", "submitted", "gated", "approved", "rejected", "promoted"],
            index=0,
        )

    requests = list_change_requests(status_filter=status_filter)

    if not requests:
        empty_state(
            f"No change requests found matching status '{status_filter}'.",
            "Submit a new change request using the submission tab.",
            icon=":material/folder_open:",
        )
    else:
        req_labels = [
            f"CR #{r['id']} | {r['base_commit'][:7]} -> {r['candidate_commit'][:7]} | Status: {r['status'].upper()} | Verdict: {r.get('gate_verdict') or '-'}"
            for r in requests
        ]
        selected_req_label = st.selectbox("Select Change Request to Review:", options=req_labels)
        selected_cr_id = int(selected_req_label.split()[1].replace("#", ""))

        selected_cr = get_change_request(selected_cr_id)
        if selected_cr:
            m1, m2, m3, m4 = st.columns(4)
            with m1:
                kpi_card("Lifecycle Status", selected_cr["status"].upper())
            with m2:
                verdict_val = selected_cr.get("gate_verdict") or "PENDING"
                kpi_card(
                    "Gate Verdict",
                    verdict_val,
                    delta="Promotable" if verdict_val == "PROMOTE" else "Blocked" if verdict_val == "BLOCK" else "Inconclusive",
                )
            with m3:
                kpi_card("Requester", selected_cr["requester"])
            with m4:
                kpi_card("Approver", selected_cr.get("approver") or "None Assigned")

            # Dialogs for Approval and Rejection
            @st.dialog("Confirm Baseline Promotion")
            def approve_dialog(cr_id, approver_name):
                st.markdown(
                    f"You are approving **CR #{cr_id}** as **{approver_name}**.\n\n"
                    "This action advances the active baseline pointer and records an immutable entry in the audit log."
                )
                comment = st.text_area("Approval Justification (Required):", placeholder="Empirical verification confirmed zero regressions on critical slices.")
                col_a, col_b = st.columns(2)
                with col_a:
                    if st.button("Cancel", use_container_width=True):
                        st.rerun()
                with col_b:
                    if st.button("Confirm Promotion", type="primary", use_container_width=True):
                        if not comment.strip():
                            st.error("Approval justification comment is strictly mandatory.")
                        else:
                            try:
                                approve_change_request(cr_id, approver_name, comment)
                                st.toast(f"CR #{cr_id} approved. Baseline promoted.", icon=":material/check_circle:")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Approval failed: {e}")

            @st.dialog("Confirm Change Request Rejection")
            def reject_dialog(cr_id, approver_name):
                st.markdown(
                    f"You are rejecting **CR #{cr_id}** as **{approver_name}**.\n\n"
                    "This action closes the request and blocks baseline promotion."
                )
                comment = st.text_area("Rejection Justification (Required):", placeholder="Significant regression detected or insufficient test coverage.")
                col_a, col_b = st.columns(2)
                with col_a:
                    if st.button("Cancel", use_container_width=True):
                        st.rerun()
                with col_b:
                    if st.button("Confirm Rejection", type="primary", use_container_width=True):
                        if not comment.strip():
                            st.error("Rejection justification comment is strictly mandatory.")
                        else:
                            try:
                                reject_change_request(cr_id, approver_name, comment)
                                st.toast(f"CR #{cr_id} rejected.", icon=":material/warning:")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Rejection failed: {e}")

            # Approver section
            if selected_cr["status"] in ["gated", "submitted"] and selected_cr.get("gate_verdict") == "PROMOTE":
                labelled_divider("Human Authorization & Promotion")
                st.info("Automated regression gate passed. Sign-off from an authorized reviewer is required to promote baseline.")

                authorized_approvers = load_approvers()
                app_col1, app_col2 = st.columns([1, 2])
                with app_col1:
                    chosen_approver = st.selectbox("Designated Approver", options=authorized_approvers)
                with app_col2:
                    st.caption("Reviewer role authorized under governance policy.")

                if policy_freeze:
                    error_panel("POLICY FREEZE ACTIVE: Baseline promotions are temporarily halted by organization policy.")

                is_self_approval = (str(chosen_approver).strip().lower() == str(selected_cr["requester"]).strip().lower())
                if is_self_approval:
                    error_panel("Separation of duties rule violated: Requester cannot approve their own change request.")

                btn_c1, btn_c2, _ = st.columns([1, 1, 2])
                with btn_c1:
                    can_approve = not policy_freeze and not is_self_approval
                    if st.button("Open Promotion Dialog...", type="primary", disabled=not can_approve, icon=":material/verified:"):
                        approve_dialog(selected_cr_id, chosen_approver)
                with btn_c2:
                    if st.button("Open Rejection Dialog...", disabled=policy_freeze, icon=":material/close:"):
                        reject_dialog(selected_cr_id, chosen_approver)

            elif selected_cr["status"] == "rejected":
                st.error(f"Change Request Rejected: {selected_cr.get('rejection_reason') or 'Failed automated regression gate.'}")
            elif selected_cr["status"] == "promoted":
                st.success(f"Promoted by {selected_cr.get('approver')} | Justification: '{selected_cr.get('approval_comment')}'")

            # Report Viewer
            if selected_cr.get("report_md"):
                labelled_divider("Automated Gate Evaluation Report")
                with st.expander(":material/description: View Gate Audit Report", expanded=True):
                    st.markdown(selected_cr["report_md"])
            else:
                labelled_divider("Execute Gate Evaluation")
                if st.button("Run Policy Gate Now", type="primary", icon=":material/play_arrow:"):
                    with st.spinner("Evaluating regression gate across test suite..."):
                        verdict, _ = run_change_request_gate(selected_cr_id, quick=True)
                        st.info(f"Gate evaluated with verdict: {verdict}")
                        st.rerun()
