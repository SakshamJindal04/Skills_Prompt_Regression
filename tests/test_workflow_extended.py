"""
Unit tests for Change Request workflow edge cases and authorizations (core.workflow).
"""

import pytest
from core.workflow import (
    submit_change_request,
    get_change_request,
    list_change_requests,
    approve_change_request,
    reject_change_request,
)
from core.models import ChangeRequest
from core.db import get_session


def test_change_request_authorization_and_validation():
    cr_id = submit_change_request(
        base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        candidate_commit="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        requester="Dev Bob",
    )

    cr = get_change_request(cr_id)
    assert cr is not None
    assert cr["requester"] == "Dev Bob"
    assert cr["status"] == "submitted"

    # Test rejection with empty comment
    with pytest.raises(ValueError, match="comment is required"):
        reject_change_request(cr_id, "Dev Bob", "")

    # Test rejection with valid comment
    success = reject_change_request(cr_id, "Senior Approver", "Rejected due to code quality")
    assert success is True

    cr_rejected = get_change_request(cr_id)
    assert cr_rejected["status"] == "rejected"
    assert cr_rejected["rejection_reason"] == "Rejected due to code quality"


def test_approve_unauthorized_user():
    cr_id = submit_change_request(
        base_commit="1111111111111111111111111111111111111111",
        candidate_commit="2222222222222222222222222222222222222222",
        requester="Dev Charlie",
    )

    # Set gate_verdict to PROMOTE
    with get_session() as session:
        cr = session.get(ChangeRequest, cr_id)
        cr.gate_verdict = "PROMOTE"
        cr.status = "gated"

    # Unauthorized approver
    with pytest.raises(PermissionError, match="not an authorized approver"):
        approve_change_request(cr_id, "RandomUserXYZ", "Approved!")

    # Authorized approver with empty justification
    with pytest.raises(ValueError, match="comment is required"):
        approve_change_request(cr_id, "Alice Reviewer", "   ")


def test_list_change_requests_filters():
    all_crs = list_change_requests(status_filter="All")
    assert len(all_crs) >= 1

    rejected_crs = list_change_requests(status_filter="rejected")
    assert all(cr["status"] == "rejected" for cr in rejected_crs)
