import pytest
from core.db import get_session, get_engine
from core.models import AuditLog
from core.audit import record_audit_event, verify_audit_hash_chain
from sqlalchemy import text


def test_audit_hash_chain_creation_and_tamper_detection():
    # 1. Record two audit events
    e1 = record_audit_event(
        who="tester_1",
        what="action_test_1",
        verdict="PROMOTE",
        b=0,
        c=2,
        candidate_commit="commit_aaa"
    )
    e2 = record_audit_event(
        who="tester_2",
        what="action_test_2",
        verdict="BLOCK",
        b=3,
        c=0,
        candidate_commit="commit_bbb"
    )

    assert e1["entry_hash"] is not None
    assert e2["prev_hash"] == e1["entry_hash"]

    # 2. Verify chain is valid initially
    status_initial = verify_audit_hash_chain()
    assert status_initial["valid"] is True
    assert status_initial["checked_count"] >= 2

    # 3. Simulate unauthorized database tamper bypass (via raw SQL connection avoiding ORM event hooks)
    engine = get_engine()
    target_id = e2["id"]

    with engine.connect() as conn:
        conn.execute(
            text(f"UPDATE audit_logs SET verdict = 'PROMOTE' WHERE id = {target_id}")
        )
        conn.commit()

    # 4. Assert verification detects tamper
    status_tampered = verify_audit_hash_chain()
    assert status_tampered["valid"] is False
    assert any(f"Tampered record at ID {target_id}" in err for err in status_tampered["errors"])

    # 5. Restore original value and assert verification passes again
    with engine.connect() as conn:
        conn.execute(
            text(f"UPDATE audit_logs SET verdict = 'BLOCK' WHERE id = {target_id}")
        )
        conn.commit()

    status_restored = verify_audit_hash_chain()
    assert status_restored["valid"] is True

