"""
System Audit Trail View
Immutable append-only record of all change requests, gate evaluations,
approvals, and baseline promotions with cryptographic SHA-256 hash chaining.
"""

import sys
from pathlib import Path
import streamlit as st
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.audit import (
    get_audit_logs,
    export_audit_report,
    verify_audit_hash_chain,
    AUDIT_JSONL_PATH,
)
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

safe_set_page_config("Audit Log")
init_theme()
top_bar()

page_header(
    "Cryptographic Audit Trail",
    "Append-only ledger of change requests, gate evaluations, and promotion actions anchored by SHA-256 hash chaining.",
)

# Hash Chain Verification
chain_status = verify_audit_hash_chain()
col_h1, col_h2, col_h3 = st.columns([2, 1, 1])

with col_h1:
    if chain_status["valid"]:
        st.markdown(
            f"""
            <div style="background: var(--arm-success-bg); border: 1px solid var(--arm-success-border); border-radius: var(--arm-radius-md); padding: 12px 16px;">
              <div style="display: flex; align-items: center; gap: 8px; font-weight: 700; color: var(--arm-success-text);">
                :material/verified_user: Cryptographic Hash Chain: VERIFIED
              </div>
              <div style="font-size: 0.85rem; color: var(--arm-text-caption); margin-top: 4px;">
                {chain_status['checked_count']} contiguous records verified intact with zero tampering anomalies.
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        error_panel(
            "Cryptographic Hash Chain: COMPROMISED",
            f"{len(chain_status['errors'])} tampering anomalies or broken hashes detected.",
        )

with col_h2:
    kpi_card(
        "Verified Records",
        str(chain_status.get("checked_count", 0)),
        delta="Unbroken" if chain_status["valid"] else "Anomaly",
    )

with col_h3:
    head_h = str(chain_status.get("head_hash") or "-")
    kpi_card(
        "Head SHA-256",
        head_h[:7],
        help_text=f"Full Head Hash: {head_h}",
    )

labelled_divider("Filter & Export Controls")

c1, c2, c3, c4 = st.columns([1, 1, 1, 1])
with c1:
    filter_what = st.selectbox(
        "Filter Action",
        options=[
            "All",
            "submit_change_request",
            "gate_evaluation_promote",
            "gate_evaluation_block",
            "approve_and_promote",
            "reject_change_request",
        ],
        index=0,
    )
with c2:
    filter_verdict = st.selectbox(
        "Filter Verdict",
        options=["All", "PROMOTE", "BLOCK", "PROMOTED", "REJECTED"],
        index=0,
    )
with c3:
    if st.button("Export Markdown Report", type="primary", icon=":material/description:"):
        out_file = export_audit_report()
        st.toast(f"Exported to {out_file}", icon=":material/check_circle:")
with c4:
    if AUDIT_JSONL_PATH.exists():
        raw_jsonl = AUDIT_JSONL_PATH.read_text(encoding="utf-8")
        st.download_button(
            "Download Raw JSONL",
            data=raw_jsonl,
            file_name="audit.jsonl",
            mime="application/jsonlines",
            icon=":material/download:",
        )

logs = get_audit_logs(limit=200, filter_what=filter_what, filter_verdict=filter_verdict)

labelled_divider(f"Recorded Audit Events ({len(logs)})")

if not logs:
    empty_state(
        "No audit events found matching the specified filters.",
        icon=":material/event_busy:",
    )
else:
    df_logs = pd.DataFrame([
        {
            "ID": row["id"],
            "Timestamp (UTC)": row["timestamp"][:19] if row.get("timestamp") else "-",
            "Actor": row["who"],
            "Action": row["what"],
            "Base Commit": (row.get("base_commit") or "-")[:7],
            "Cand Commit": (row.get("candidate_commit") or "-")[:7],
            "Model": row.get("model_id") or "-",
            "Verdict": row.get("verdict") or "-",
            "p-value": f"{row['p_value']:.4f}" if row.get("p_value") is not None else "-",
            "Regressed (b)": row.get("b", 0),
            "Fixed (c)": row.get("c", 0),
            "Approver": row.get("approver") or "-",
            "Comment": row.get("comment") or "-",
        }
        for row in logs
    ])

    st.dataframe(df_logs, use_container_width=True, hide_index=True)

    labelled_divider("Detailed Audit Record Inspector")
    log_ids = [row["id"] for row in logs]
    selected_id = st.selectbox("Select Audit Event ID to Inspect:", options=log_ids)
    selected_entry = next((row for row in logs if row["id"] == selected_id), None)

    if selected_entry:
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown(f"**Action Category**: `{selected_entry['what']}`")
            st.markdown(f"**Actor (who)**: `{selected_entry['who']}`")
            st.markdown(f"**Timestamp (UTC)**: `{selected_entry['timestamp']}`")
            st.markdown(f"**Base Revision**: `{selected_entry.get('base_commit') or 'N/A'}`")
            st.markdown(f"**Candidate Revision**: `{selected_entry.get('candidate_commit') or 'N/A'}`")
            st.markdown(f"**Evaluated Model**: `{selected_entry.get('model_id') or 'N/A'}`")

        with col_b:
            st.markdown(f"**Gate Verdict**: **{selected_entry.get('verdict') or 'N/A'}**")
            st.markdown(f"**Approver Identity**: `{selected_entry.get('approver') or 'None'}`")
            st.markdown(f"**Justification / Comment**: `{selected_entry.get('comment') or 'None'}`")
            st.markdown(f"**Execution Seeds**: `{selected_entry.get('seeds') or 'N/A'}`")
            st.markdown(f"**Audit Report Path**: `{selected_entry.get('report_path') or 'N/A'}`")
