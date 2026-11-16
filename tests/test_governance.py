import pytest
from core.db import get_session, init_db
from core.models import AuditLog, ChangeRequest, Artifact, BaselineRegistry
from core.audit import record_audit_event, get_audit_logs, export_audit_report
from core.policy import load_policy, load_approvers, is_valid_approver, validate_candidate_model
from core.workflow import (
    submit_change_request,
    get_change_request,
    list_change_requests,
    approve_change_request,
    reject_change_request,
)
from core.versioner import set_current_baseline, get_current_baseline


@pytest.fixture(autouse=True)
def setup_database():
    init_db()


def test_audit_log_append_only_enforcement():
    """
    Test requirement 2: Proves the audit log cannot be edited or deleted
    through the application code paths or ORM operations.
    """
    event = record_audit_event(
        who="security_tester",
        what="test_audit_event",
        comment="Initial immutable record",
    )
    log_id = event["id"]
    assert log_id is not None

    # Attempt modification: must raise PermissionError
    with pytest.raises(PermissionError) as excinfo_update:
        with get_session() as session:
            entry = session.get(AuditLog, log_id)
            assert entry is not None
            entry.comment = "Malicious unauthorized modification"
            session.flush()

    assert "append-only" in str(excinfo_update.value).lower()

    # Attempt deletion: must raise PermissionError
    with pytest.raises(PermissionError) as excinfo_delete:
        with get_session() as session:
            entry = session.get(AuditLog, log_id)
            assert entry is not None
            session.delete(entry)
            session.flush()

    assert "append-only" in str(excinfo_delete.value).lower()


def test_policy_loading_and_validation():
    """
    Test requirement 4: policy.yaml specifies alpha, minimum_tests,
    critical_test_ids, required_approvers, k, and allowed_models.
    """
    policy = load_policy()
    assert "version" in policy
    assert "alpha" in policy
    assert isinstance(policy["alpha"], (int, float))
    assert policy["alpha"] == 0.05
    assert "minimum_tests" in policy
    assert policy["minimum_tests"] >= 10
    assert "critical_test_ids" in policy
    assert isinstance(policy["critical_test_ids"], list)
    assert len(policy["critical_test_ids"]) > 0
    assert "allowed_models" in policy
    assert "qwen2.5:3b" in policy["allowed_models"]

    # Allowed models check
    assert validate_candidate_model("qwen2.5:3b", policy) is True
    assert validate_candidate_model("unapproved_frontier_model_xyz", policy) is False


def test_approvers_configuration():
    """
    Test requirement 1 & 4: approvers are loaded from approvers.yaml.
    """
    approvers = load_approvers()
    assert len(approvers) >= 3
    assert "Alice Reviewer" in approvers
    assert "Bob Lead" in approvers
    assert "Carol Admin" in approvers

    assert is_valid_approver("Alice Reviewer") is True
    assert is_valid_approver("alice reviewer") is True  # Case insensitive
    assert is_valid_approver("Mallory Attacker") is False
    assert is_valid_approver("") is False
    assert is_valid_approver(None) is False


def test_change_request_approval_workflow_end_to_end():
    """
    Test requirement 1: Change request lifecycle:
    submit -> gate -> approval check -> promotion.
    """
    # 1. Create dummy candidate and baseline artifacts
    with get_session() as session:
        art_base = Artifact(name="test_base", path="workspace", type="commit", hash="sha_base_001")
        art_cand = Artifact(name="test_cand", path="workspace", type="commit", hash="sha_cand_002")
        session.add(art_base)
        session.add(art_cand)
        session.flush()
        base_id = art_base.id
        cand_id = art_cand.id

    set_current_baseline(base_id, notes="Baseline before test CR")

    # 2. Submit change request
    cr_id = submit_change_request(
        base_commit="sha_base_001",
        candidate_commit="sha_cand_002",
        requester="Dan Developer",
        artifact_id=cand_id,
    )
    assert cr_id is not None
    cr_data = get_change_request(cr_id)
    assert cr_data["status"] == "submitted"
    assert cr_data["requester"] == "Dan Developer"

    # Simulate automated gate passing
    with get_session() as session:
        cr_entry = session.get(ChangeRequest, cr_id)
        cr_entry.gate_verdict = "PROMOTE"
        cr_entry.status = "gated"

    # 3. Unauthorized approver cannot approve
    with pytest.raises(PermissionError):
        approve_change_request(cr_id, approver_name="Unauthorized Person", comment="Looks good to me")

    # 4. Approver cannot approve without required comment
    with pytest.raises(ValueError):
        approve_change_request(cr_id, approver_name="Alice Reviewer", comment="")

    with pytest.raises(ValueError):
        approve_change_request(cr_id, approver_name="Alice Reviewer", comment="   ")

    # 5. Authorized approver with non-empty comment approves successfully
    approved = approve_change_request(
        cr_id,
        approver_name="Alice Reviewer",
        comment="All regression checks verified, approving baseline promotion.",
    )
    assert approved is True

    # Verify status is promoted
    updated_cr = get_change_request(cr_id)
    assert updated_cr["status"] == "promoted"
    assert updated_cr["approver"] == "Alice Reviewer"

    # Verify baseline registry was updated
    active_baseline = get_current_baseline()
    assert active_baseline is not None
    assert active_baseline["id"] == cand_id


def test_change_request_rejection():
    """
    Test rejection flow with mandatory comment.
    """
    cr_id = submit_change_request(
        base_commit="sha_base_003",
        candidate_commit="sha_cand_004",
        requester="Eve Engineer",
    )
    # Rejection requires comment
    with pytest.raises(ValueError):
        reject_change_request(cr_id, "Bob Lead", comment="")

    # Valid rejection
    rejected = reject_change_request(cr_id, "Bob Lead", comment="Regressions detected in benchmark suite.")
    assert rejected is True

    updated_cr = get_change_request(cr_id)
    assert updated_cr["status"] == "rejected"
    assert updated_cr["rejection_reason"] == "Regressions detected in benchmark suite."
