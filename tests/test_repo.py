"""
Unit tests for Git repository operations in workspace/.
"""

import shutil
import tempfile
from pathlib import Path
import pytest

from core.repo import (
    init_repo,
    commit_changes,
    list_versions,
    get_diff,
    get_file_at_version,
    revert_commit,
)


@pytest.fixture
def temp_workspace():
    tmp_dir = tempfile.mkdtemp(prefix="test_ws_")
    yield tmp_dir
    shutil.rmtree(tmp_dir, ignore_errors=True)


def test_repo_init_and_commits(temp_workspace):
    ws = Path(temp_workspace)
    repo = init_repo(str(ws))
    assert repo is not None
    assert (ws / ".git").exists()

    # Create prompt file
    prompt_file = ws / "prompts" / "test_prompt.md"
    prompt_file.parent.mkdir(parents=True, exist_ok=True)
    prompt_file.write_text("Prompt content v1", encoding="utf-8")

    c1 = commit_changes("Initial test commit", workspace_dir=str(ws))
    assert len(c1) == 40  # Full SHA

    versions = list_versions(workspace_dir=str(ws))
    assert len(versions) >= 1
    assert versions[0]["git_hash"] == c1

    # Modify file
    prompt_file.write_text("Prompt content v2 - updated", encoding="utf-8")
    c2 = commit_changes("Second update commit", workspace_dir=str(ws))
    assert c2 != c1

    # Read at version 1
    v1_text = get_file_at_version(c1, "prompts/test_prompt.md", workspace_dir=str(ws))
    assert v1_text == "Prompt content v1"

    # Read at version 2
    v2_text = get_file_at_version(c2, "prompts/test_prompt.md", workspace_dir=str(ws))
    assert v2_text == "Prompt content v2 - updated"

    # Diff
    diff = get_diff(c1, c2, workspace_dir=str(ws))
    assert "-Prompt content v1" in diff
    assert "+Prompt content v2 - updated" in diff

    # Non-destructive revert
    c3 = revert_commit(c2, message="Revert to v1", workspace_dir=str(ws))
    assert c3 != c2
    reverted_text = (ws / "prompts" / "test_prompt.md").read_text(encoding="utf-8")
    assert reverted_text == "Prompt content v1"

