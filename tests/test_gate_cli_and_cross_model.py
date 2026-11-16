"""
Unit and integration tests for core.gate (run_cross_model_gate, CLI main).
"""

import sys
from unittest.mock import patch, MagicMock
from core.gate import run_cross_model_gate, main


def test_run_cross_model_gate_mocked(tmp_path):
    report_file = tmp_path / "report.md"

    mock_resp = MagicMock()
    mock_resp.text = "POSITIVE"

    with patch("core.llm.default_client.generate", return_value=mock_resp), \
         patch("core.llm.default_client.get_model_metadata", return_value={"digest": "sha256:1234567890"}), \
         patch("core.gate.record_audit_event"):

        verdict, report, comp = run_cross_model_gate(
            base_model="qwen2.5:3b",
            cand_model="llama3.2:3b",
            k=1,
            report_path=str(report_file),
            quick=True,
        )

        assert verdict in ["PROMOTE", "BLOCK"]
        assert report_file.exists()
        content = report_file.read_text(encoding="utf-8")
        assert "Cross-Model Regression Gate Report" in content
        assert "Baseline Model" in content


def test_gate_cli_main_cross_model_promote(tmp_path):
    report_file = tmp_path / "cli_report.md"
    test_args = [
        "gate.py",
        "--base-model", "qwen2.5:3b",
        "--cand-model", "gemma2:2b",
        "--quick",
        "--report", str(report_file),
    ]

    with patch.object(sys, "argv", test_args), \
         patch("core.gate.run_cross_model_gate", return_value=("PROMOTE", "Report text", {})):
        try:
            main()
            exit_code = 0
        except SystemExit as e:
            exit_code = e.code

        assert exit_code == 0


def test_gate_cli_main_candidate_block():
    test_args = [
        "gate.py",
        "--candidate", "999",
        "--baseline", "888",
    ]

    with patch.object(sys, "argv", test_args), \
         patch("core.gate.resolve_ref_to_artifact", side_effect=[888, 999]), \
         patch("core.gate.get_session"), \
         patch("core.comparator.compare_test_results", return_value={}), \
         patch("core.scorer.score_artifact_runs"), \
         patch("core.gate.evaluate_gate", return_value=("BLOCK", "Blocked")):
        try:
            main()
            exit_code = 0
        except SystemExit as e:
            exit_code = e.code

        assert exit_code == 1
