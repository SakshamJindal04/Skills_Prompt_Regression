"""
Unit tests for Change Request gate execution (core.workflow).
"""

import uuid
from unittest.mock import patch, MagicMock
from core.workflow import (
    submit_change_request,
    run_change_request_gate,
    get_change_request,
)
from core.models import Artifact, Score, TestCase, Trace
from core.db import get_session


def test_run_change_request_gate_promote():
    uid = uuid.uuid4().hex[:8]
    tc_id = f"tc_wf_{uid}"
    # Setup test DB artifacts
    with get_session() as session:
        art_base = Artifact(hash=f"art_base_{uid}", type="prompt", name="base", path="workspace")
        art_cand = Artifact(hash=f"art_cand_{uid}", type="prompt", name="cand", path="workspace", manifest={"model": "qwen2.5:3b"})
        session.add_all([art_base, art_cand])
        session.flush()

        tc = TestCase(id=tc_id, suite="golden", target="p", input="test", checks=[])
        session.add(tc)
        session.flush()

        tr_base = Trace(artifact_id=art_base.id, test_id=tc_id, run_index=0, output="out1")
        tr_cand = Trace(artifact_id=art_cand.id, test_id=tc_id, run_index=0, output="out2")
        session.add_all([tr_base, tr_cand])
        session.flush()

        s_base = Score(trace_id=tr_base.id, artifact_id=art_base.id, test_id=tc_id, passed=False, score=0.0)
        s_cand = Score(trace_id=tr_cand.id, artifact_id=art_cand.id, test_id=tc_id, passed=True, score=1.0)
        session.add_all([s_base, s_cand])
        session.flush()

        base_id = art_base.id
        cand_id = art_cand.id

    cr_id = submit_change_request(base_commit="c_base", candidate_commit="c_cand", requester="Engineer Alice")

    with patch("core.workflow.resolve_ref_to_artifact") as mock_resolve, \
         patch("core.workflow.record_audit_event"):
        mock_resolve.side_effect = [base_id, cand_id]

        verdict, report = run_change_request_gate(cr_id)
        assert verdict == "PROMOTE"

    cr = get_change_request(cr_id)
    assert cr["status"] == "gated"
    assert cr["gate_verdict"] == "PROMOTE"
