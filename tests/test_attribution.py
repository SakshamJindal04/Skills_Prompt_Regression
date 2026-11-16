"""
Unit tests for change attribution and auto-bisect logic.
"""

import tempfile
import shutil
from pathlib import Path
import pytest

from core.repo import init_repo, commit_changes
from core.attribution import auto_bisect


@pytest.fixture
def temp_repo_with_commits():
    tmp_dir = tempfile.mkdtemp(prefix="test_bisect_")
    ws = Path(tmp_dir)
    init_repo(str(ws))

    p = ws / "prompts" / "test.md"
    p.parent.mkdir(parents=True, exist_ok=True)

    # Commit 1: good
    p.write_text("Good prompt v1", encoding="utf-8")
    c1 = commit_changes("Commit 1: baseline good", workspace_dir=str(ws))

    # Commit 2: harmless
    p.write_text("Good prompt v1 - minor comment", encoding="utf-8")
    c2 = commit_changes("Commit 2: harmless edit", workspace_dir=str(ws))

    # Commit 3: broken
    p.write_text("Broken corrupted prompt v2", encoding="utf-8")
    c3 = commit_changes("Commit 3: breaking regression", workspace_dir=str(ws))

    # Commit 4: post-regression
    p.write_text("Broken corrupted prompt v2 - release notes", encoding="utf-8")
    c4 = commit_changes("Commit 4: release commit", workspace_dir=str(ws))

    yield str(ws), [c1, c2, c3, c4]
    shutil.rmtree(tmp_dir, ignore_errors=True)


def test_commit_timeline_discovery(temp_repo_with_commits):
    ws_dir, shas = temp_repo_with_commits
    c_good, _, c_bad, _ = shas

    repo = init_repo(ws_dir)
    commits_range = list(repo.iter_commits(f"{c_good}..{c_bad}"))
    assert len(commits_range) == 2  # c2 and c3

