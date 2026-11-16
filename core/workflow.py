import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional

from core.db import get_session
from core.models import ChangeRequest, Artifact, BaselineRegistry
from core.policy import load_policy, is_valid_approver, validate_candidate_model
from core.audit import record_audit_event
from core.gate import resolve_ref_to_artifact, evaluate_gate
from core.comparator import compare_test_results
from core.versioner import set_current_baseline, get_current_baseline
from core.runner import run_test, sync_tests_to_db
from core.scorer import score_artifact_runs

logger = logging.getLogger("workflow")
BASE_DIR = Path(__file__).resolve().parent.parent


def submit_change_request(base_commit, candidate_commit, requester="Developer", artifact_id=None):
    """
    Submits a new change request between a base commit and a candidate commit.
    Initial status is 'submitted'.
    """
    now = datetime.now(timezone.utc)
    with get_session() as session:
        cr = ChangeRequest(
            artifact_id=artifact_id,
            base_commit=str(base_commit).strip(),
            candidate_commit=str(candidate_commit).strip(),
            requester=str(requester).strip(),
            status="submitted",
            created_at=now,
            updated_at=now,
        )
        session.add(cr)
        session.flush()
        cr_id = cr.id

    record_audit_event(
        who=requester,
        what="submit_change_request",
        base_commit=base_commit,
        candidate_commit=candidate_commit,
        comment=f"Change request #{cr_id} submitted by {requester}",
    )
    return cr_id


def get_change_request(cr_id):
    with get_session() as session:
        cr = session.get(ChangeRequest, int(cr_id))
        return cr.to_dict() if cr else None


def list_change_requests(status_filter=None):
    with get_session() as session:
        query = session.query(ChangeRequest)
        if status_filter and status_filter != "All":
            query = query.filter(ChangeRequest.status == status_filter)
        query = query.order_by(ChangeRequest.id.desc())
        return [cr.to_dict() for cr in query.all()]


def run_change_request_gate(cr_id, policy_path=None, quick=False):
    """
    Executes automated gating for a change request using settings from policy.yaml.
    If PROMOTE: status becomes 'gated' (awaiting human approver).
    If BLOCK: status becomes 'rejected' with report.
    """
    policy = load_policy(policy_path)
    alpha = policy.get("alpha", 0.05)
    k = policy.get("k", 5)
    if quick:
        k = min(k, 3)

    with get_session() as session:
        cr = session.get(ChangeRequest, int(cr_id))
        if not cr:
            raise ValueError(f"Change request #{cr_id} not found")
        base_commit = cr.base_commit
        cand_commit = cr.candidate_commit

    # Resolve artifacts
    base_art_id = resolve_ref_to_artifact(base_commit, quick=quick)
    cand_art_id = resolve_ref_to_artifact(cand_commit, quick=quick)

    if not base_art_id or not cand_art_id:
        raise RuntimeError(f"Could not resolve artifacts for base {base_commit} or candidate {cand_commit}")

    # Load test runs
    from core.models import Score, TestCase
    with get_session() as session:
        base_scores = session.query(Score).filter_by(artifact_id=base_art_id).all()
        cand_scores = session.query(Score).filter_by(artifact_id=cand_art_id).all()
        test_cases = [tc.to_dict() for tc in session.query(TestCase).all()]

    if not base_scores or not cand_scores:
        raise RuntimeError("Missing evaluation traces for candidate or baseline artifact")

    # Map scores by test_id
    base_runs_map = {}
    for s in base_scores:
        base_runs_map.setdefault(s.test_id, []).append(s.passed)

    cand_runs_map = {}
    for s in cand_scores:
        cand_runs_map.setdefault(s.test_id, []).append(s.passed)

    # Perform comparison
    comp_res = compare_test_results(test_cases, base_runs_map, cand_runs_map, k=k)

    # Check model compatibility with policy allowed_models
    with get_session() as session:
        cand_art = session.get(Artifact, cand_art_id)
        model_name = "qwen2.5:3b"
        if cand_art and cand_art.manifest:
            model_name = cand_art.manifest.get("model", "qwen2.5:3b")

    model_allowed = validate_candidate_model(model_name, policy)

    # Evaluate gate using policy
    policy_crit_ids = set(policy.get("critical_test_ids", []))
    for f in comp_res.get("flips", []):
        if f.get("test_id") in policy_crit_ids:
            f["critical"] = True

    verdict, report_md = evaluate_gate(
        comp_res,
        alpha=alpha,
        candidate_id=cand_art_id,
        baseline_id=base_art_id,
        auto_promote=False,  # Human approval required before promotion!
        policy_version=policy.get("version", "1.0.0"),
    )

    if not model_allowed:
        verdict = "BLOCK"
        report_md += f"\n\n> **Policy Violation**: Model `{model_name}` is not listed in `policy.yaml` allowed models.\n"

    new_status = "gated" if verdict == "PROMOTE" else "rejected"
    rejection = None if verdict == "PROMOTE" else "Rejected by automated regression gate"

    with get_session() as session:
        cr = session.get(ChangeRequest, int(cr_id))
        cr.artifact_id = cand_art_id
        cr.gate_verdict = verdict
        cr.report_md = report_md
        cr.status = new_status
        cr.rejection_reason = rejection
        cr.updated_at = datetime.now(timezone.utc)

    # Audit log
    b_val = comp_res.get("regressed_count", 0)
    c_val = comp_res.get("fixed_count", 0)
    p_val = comp_res.get("p_value")
    record_audit_event(
        who="system_gate",
        what=f"gate_evaluation_{verdict.lower()}",
        base_commit=base_commit,
        candidate_commit=cand_commit,
        model_id=model_name,
        p_value=p_val,
        b=b_val,
        c=c_val,
        verdict=verdict,
        comment=f"CR #{cr_id} gated with verdict {verdict}",
        report_path="report.md",
    )

    return verdict, report_md


def approve_change_request(cr_id, approver_name, comment):
    """
    Approves a gated change request. Only users in approvers.yaml may approve.
    A non-empty comment is required.
    Enforces separation of duties (author cannot approve own request) and policy freeze check.
    Successful approval promotes the candidate artifact as the new baseline.
    """
    policy = load_policy()
    if policy.get("freeze", False):
        raise PermissionError("Policy freeze is active: all promotions and approvals are currently frozen.")

    if not is_valid_approver(approver_name):
        raise PermissionError(f"User '{approver_name}' is not an authorized approver in approvers.yaml")

    if not comment or not str(comment).strip():
        raise ValueError("A justification comment is required to approve a change request.")

    with get_session() as session:
        cr = session.get(ChangeRequest, int(cr_id))
        if not cr:
            raise ValueError(f"Change request #{cr_id} not found")

        # Separation of duties: author cannot approve own change request
        if cr.requester and str(cr.requester).strip().lower() == str(approver_name).strip().lower():
            raise PermissionError(f"Separation of duties violation: author '{cr.requester}' cannot approve their own change request.")

        if cr.gate_verdict != "PROMOTE":
            raise ValueError(f"Cannot approve change request #{cr_id}: gate verdict was {cr.gate_verdict}")

        if cr.status not in ["gated", "submitted"]:
            raise ValueError(f"Cannot approve change request #{cr_id} with status '{cr.status}'")

        cr.status = "approved"
        cr.approver = approver_name
        cr.approval_comment = comment
        cand_art_id = cr.artifact_id
        cand_commit = cr.candidate_commit
        base_commit = cr.base_commit
        cr.updated_at = datetime.now(timezone.utc)

    # Promote candidate to new baseline
    if cand_art_id:
        set_current_baseline(cand_art_id, notes=f"Promoted via CR #{cr_id} approved by {approver_name}")

    with get_session() as session:
        cr = session.get(ChangeRequest, int(cr_id))
        cr.status = "promoted"
        cr.updated_at = datetime.now(timezone.utc)

    record_audit_event(
        who=approver_name,
        what="approve_and_promote",
        base_commit=base_commit,
        candidate_commit=cand_commit,
        approver=approver_name,
        comment=comment,
        verdict="PROMOTED",
    )
    return True


def request_governed_rollback(target_commit: str, requester: str = "Developer", reason: str = "") -> Dict[str, Any]:
    """
    Submits a governed rollback request. If policy requires approval, enters change_requests table
    for approver review; otherwise immediately promotes target commit.
    """
    from core.repo import get_repo, list_versions
    from core.versioner import get_current_baseline

    policy = load_policy()
    base_art = get_current_baseline()
    base_commit = base_art["commit_hash"] if base_art else "HEAD"

    require_approval = policy.get("require_approval_for_rollback", True)

    if require_approval:
        cr_id = submit_change_request(
            base_commit=base_commit,
            candidate_commit=target_commit,
            requester=requester
        )
        return {
            "status": "awaiting_approval",
            "change_request_id": cr_id,
            "message": f"Rollback to {target_commit[:7]} submitted as Change Request #{cr_id} awaiting approval."
        }
    else:
        # Immediate rollback
        target_art_id = resolve_ref_to_artifact(target_commit)
        if target_art_id:
            set_current_baseline(target_art_id, notes=f"Rollback to {target_commit[:7]} requested by {requester}")
        return {
            "status": "rolled_back",
            "target_commit": target_commit,
            "message": f"Directly rolled back to baseline commit {target_commit[:7]}."
        }



def reject_change_request(cr_id, reviewer_name, comment):
    """
    Rejects a change request with a mandatory review comment.
    """
    if not comment or not str(comment).strip():
        raise ValueError("A comment is required to reject a change request.")

    with get_session() as session:
        cr = session.get(ChangeRequest, int(cr_id))
        if not cr:
            raise ValueError(f"Change request #{cr_id} not found")

        cr.status = "rejected"
        cr.approver = reviewer_name
        cr.rejection_reason = comment
        cand_commit = cr.candidate_commit
        base_commit = cr.base_commit
        cr.updated_at = datetime.now(timezone.utc)

    record_audit_event(
        who=reviewer_name,
        what="reject_change_request",
        base_commit=base_commit,
        candidate_commit=cand_commit,
        approver=reviewer_name,
        comment=comment,
        verdict="REJECTED",
    )
    return True
