"""
Unit tests for core.audit (record_audit_event, get_audit_logs, export_audit_report).
"""

from pathlib import Path
from core.audit import record_audit_event, get_audit_logs, export_audit_report


def test_audit_event_recording_and_filtering():
    rec = record_audit_event(
        who="Auditor_Alice",
        what="gate_evaluation_block",
        base_commit="1111111111111111111111111111111111111111",
        candidate_commit="2222222222222222222222222222222222222222",
        model_id="qwen2.5:3b",
        p_value=0.0123,
        b=3,
        c=0,
        verdict="BLOCK",
        comment="Test audit recording",
    )

    assert rec["who"] == "Auditor_Alice"
    assert rec["verdict"] == "BLOCK"

    # Query with filters
    logs = get_audit_logs(limit=10, filter_what="gate_evaluation_block", filter_verdict="BLOCK")
    assert len(logs) >= 1
    assert any(item["who"] == "Auditor_Alice" for item in logs)


def test_export_audit_report(tmp_path):
    report_file = tmp_path / "audit_report.md"
    out_path = export_audit_report(output_path=report_file)

    assert Path(out_path).exists()
    content = Path(out_path).read_text(encoding="utf-8")
    assert "Regression Manager System Audit Trail Report" in content
    assert "Append-Only Security Verification" in content

