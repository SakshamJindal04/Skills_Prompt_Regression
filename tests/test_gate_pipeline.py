"""
Integration and unit tests for gate pipeline (core.gate).
"""

from unittest.mock import patch, MagicMock
from core.gate import (
    send_alert,
    evaluate_gate,
    resolve_ref_to_artifact,
)
from core.models import Comparison, Artifact
from core.db import get_session


def test_send_alert_logging(tmp_path):
    with patch("core.gate.Path") as mock_path:
        mock_path.return_value.resolve.return_value.parent.parent = tmp_path
        send_alert("Regression detected on critical test", "BLOCK", 42)

    log_file = tmp_path / "logs" / "alerts.log"
    assert log_file.exists()
    content = log_file.read_text(encoding="utf-8")
    assert "[BLOCK] Candidate 42: Regression detected" in content


def test_evaluate_gate_critical_override():
    with get_session() as session:
        art_base = Artifact(hash="hash_gate_base", type="prompt", name="base.md", path="workspace")
        art_cand = Artifact(hash="hash_gate_cand", type="prompt", name="cand.md", path="workspace")
        session.add_all([art_base, art_cand])
        session.flush()
        base_id = art_base.id
        cand_id = art_cand.id

    comp = {
        "baseline_id": base_id,
        "candidate_id": cand_id,
        "base_pass_rate": 0.85,
        "cand_pass_rate": 0.82,
        "delta": 0.03,
        "p_value": 0.45,
        "regressed_count": 1,
        "fixed_count": 2,
        "flips": [
            {"test_id": "sent_08", "base_pass": True, "cand_pass": False, "status": "REGRESSED", "critical": True},
        ],
    }
    # Even if p > alpha and fixed > regressed, if sent_08 is critical in policy, verdict must be BLOCK
    verdict, report = evaluate_gate(comp, candidate_id=cand_id, baseline_id=base_id, auto_promote=False)
    assert verdict == "BLOCK"
    assert "sent_08" in report
    assert "YES" in report


def test_resolve_ref_to_artifact_numeric():
    with get_session() as session:
        art = Artifact(
            hash="dummy_hash_resolve",
            type="prompt",
            name="dummy.md",
            path="prompts/dummy.md",
        )
        session.add(art)
        session.flush()
        art_id = art.id

    resolved = resolve_ref_to_artifact(str(art_id))
    assert resolved == art_id
