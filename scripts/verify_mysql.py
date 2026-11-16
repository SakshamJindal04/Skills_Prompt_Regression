#!/usr/bin/env python3
"""
Verify MySQL 8 database connectivity, table schema, write/read capabilities,
and graceful fallback to SQLite.
"""

import sys
import os
from datetime import datetime, timezone

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.db import get_engine, get_session, get_active_db_type, reset_engine, init_db
from core.models import Artifact, Run, Base
from sqlalchemy import text


def verify_mysql_live():
    print("[1/3] Verifying primary database connection...")
    reset_engine()
    engine = get_engine()
    db_type = get_active_db_type()
    print(f"  Active database type: {db_type}")
    print(f"  Engine URL: {engine.url}")

    if db_type != "mysql":
        print("  WARNING: Expected mysql as active database, got", db_type)
        return False

    print("[2/3] Verifying tables and write/read operations in MySQL...")
    init_db(engine)

    with get_session() as session:
        # Check tables
        with engine.connect() as conn:
            tables = conn.execute(text("SHOW TABLES;")).fetchall()
            table_names = [t[0] for t in tables]
            print(f"  Tables detected ({len(table_names)}): {', '.join(sorted(table_names))}")

        # Insert a verification artifact and run
        test_hash = f"test_hash_{int(datetime.now(timezone.utc).timestamp())}"
        test_artifact = Artifact(
            hash=test_hash,
            type="prompt",
            name="verification_prompt.md",
            path="prompts/verification_prompt.md",
            manifest={"test": True},
            created_at=datetime.now(timezone.utc),
        )
        session.add(test_artifact)
        session.flush()

        test_run = Run(
            artifact_id=test_artifact.id,
            model_name="qwen2.5:3b",
            temperature=0.7,
            n_runs=5,
            overall_pass_rate=1.0,
            consistency=1.0,
            created_at=datetime.now(timezone.utc),
        )
        session.add(test_run)
        session.flush()
        run_id = test_run.id
        print(f"  Successfully inserted verification records: Artifact ID={test_artifact.id}, Run ID={run_id}")

        # Read back
        read_run = session.query(Run).filter(Run.id == run_id).first()
        assert read_run is not None, "Failed to read back written run"
        assert read_run.artifact_id == test_artifact.id, "Artifact ID mismatch"
        print("  Successfully verified read-after-write consistency in MySQL.")

        # Clean up (child Run first, then parent Artifact)
        session.delete(read_run)
        session.flush()
        session.delete(test_artifact)
        session.flush()
        print("  Successfully cleaned up verification records.")

    print("[3/3] Verifying graceful fallback to SQLite when MySQL is unreachable...")
    # Simulate unreachable MySQL by setting bad DB_URL
    original_url = os.environ.get("DB_URL")
    os.environ["DB_URL"] = "mysql+pymysql://invalid_user:invalid_pass@127.0.0.1:9999/nonexistent"
    reset_engine()

    fallback_engine = get_engine()
    fallback_type = get_active_db_type()
    print(f"  Fallback database type: {fallback_type}")
    print(f"  Fallback engine URL: {fallback_engine.url}")
    assert fallback_type == "sqlite", f"Expected sqlite fallback, got {fallback_type}"
    print("  Successfully fell back to local SQLite on connection failure.")

    # Restore environment
    if original_url is not None:
        os.environ["DB_URL"] = original_url
    else:
        os.environ.pop("DB_URL", None)
    reset_engine()

    print("\nMySQL verification completed successfully: All checks passed.")
    return True


if __name__ == "__main__":
    success = verify_mysql_live()
    sys.exit(0 if success else 1)
