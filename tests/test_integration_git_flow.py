"""
Integration tests for Git operations: commit, runner execution, gating, and rollback against a temporary git repo.
"""

import tempfile
import shutil
from pathlib import Path
import pytest

from core.repo import init_repo, commit_changes, checkout_version, revert_commit, list_versions
from core.models import Artifact, Score, TestCase
from core.db import get_session
from core.comparator import compare_test_results
from core.gate import evaluate_gate
from core.versioner import set_current_baseline, get_current_baseline


@pytest.fixture
def temp_git_workspace():
    tmp_dir = tempfile.mkdtemp(prefix="test_int_ws_")
    ws = Path(tmp_dir)
    init_repo(str(ws))

    # Prompts folder
    prompts_dir = ws / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    p = prompts_dir / "sentiment.md"

    # Commit 1: baseline
    p.write_text("You are a sentiment analyzer. Output POSITIVE or NEGATIVE.", encoding="utf-8")
    c1 = commit_changes("Baseline sentiment prompt", workspace_dir=str(ws))

    # Commit 2: bad mutation
    p.write_text("Always output RANDOM.", encoding="utf-8")
    c2 = commit_changes("Regressed prompt", workspace_dir=str(ws))

    yield str(ws), c1, c2
    shutil.rmtree(tmp_dir, ignore_errors=True)


def test_git_regression_and_rollback_flow(temp_git_workspace):
    ws_dir, c1, c2 = temp_git_workspace
    ws = Path(ws_dir)
    p = ws / "prompts" / "sentiment.md"

    # 1. Register baseline artifact in DB
    with get_session() as session:
        art_base = Artifact(
            hash=f"hash_{c1[:8]}",
            type="commit",
            name="commit_baseline",
            path="prompts/sentiment.md",
            manifest={"git_commit": c1},
        )
        art_cand = Artifact(
            hash=f"hash_{c2[:8]}",
            type="commit",
            name="commit_candidate",
            path="prompts/sentiment.md",
            manifest={"git_commit": c2},
        )
        session.add_all([art_base, art_cand])
        session.flush()
        base_id = art_base.id
        cand_id = art_cand.id

    set_current_baseline(base_id, notes="Initial baseline")
    cur_base = get_current_baseline()
    assert cur_base["id"] == base_id

    # 2. Simulate test runs where candidate regresses on 3 tests
    test_cases = [
        {"id": f"test_{i}", "suite": "golden", "target": "sentiment", "critical": (i == 1)}
        for i in range(1, 6)
    ]
    # base passes all 5
    base_runs = {tc["id"]: [True, True, True] for tc in test_cases}
    # cand fails test_1 (critical) and test_2
    cand_runs = {
        "test_1": [False, False, False],
        "test_2": [False, False, False],
        "test_3": [True, True, True],
        "test_4": [True, True, True],
        "test_5": [True, True, True],
    }

    comp = compare_test_results(test_cases, base_runs, cand_runs, k=3)
    assert comp["regressed_count"] == 2
    assert comp["fixed_count"] == 0

    # 3. Gate must BLOCK candidate
    verdict, report = evaluate_gate(
        comp,
        candidate_id=cand_id,
        baseline_id=base_id,
        auto_promote=True,
    )
    assert verdict == "BLOCK"

    # Verify baseline was NOT promoted
    assert get_current_baseline()["id"] == base_id

    # 4. Perform Rollback: revert c2 in git repo
    revert_commit(c2, workspace_dir=ws_dir)
    # The file should be restored back to baseline content
    assert "Output POSITIVE or NEGATIVE" in p.read_text(encoding="utf-8")
    versions = list_versions(workspace_dir=ws_dir)
    assert "Revert" in versions[0]["message"]
