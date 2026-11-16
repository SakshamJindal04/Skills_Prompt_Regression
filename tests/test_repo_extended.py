"""
Unit tests for extended Git operations in core.repo.
"""

import tempfile
import shutil
from pathlib import Path
from core.repo import (
    init_repo,
    commit_changes,
    checkout_version,
    restore_file_from_version,
    revert_commit,
    list_versions,
)


def test_repo_checkout_and_restore():
    tmp_dir = tempfile.mkdtemp(prefix="test_repo_ext_")
    ws = Path(tmp_dir)
    try:
        init_repo(str(ws))
        p = ws / "prompts" / "p.md"
        p.parent.mkdir(parents=True, exist_ok=True)

        p.write_text("Version 1 content", encoding="utf-8")
        c1 = commit_changes("Commit 1", workspace_dir=str(ws))

        p.write_text("Version 2 content", encoding="utf-8")
        c2 = commit_changes("Commit 2", workspace_dir=str(ws))

        # Test checkout
        checkout_version(c1, workspace_dir=str(ws))
        assert p.read_text(encoding="utf-8") == "Version 1 content"

        # Checkout c2
        checkout_version(c2, workspace_dir=str(ws))
        assert p.read_text(encoding="utf-8") == "Version 2 content"

        # Restore file from c1 while on c2
        restore_file_from_version(c1, "prompts/p.md", workspace_dir=str(ws))
        assert p.read_text(encoding="utf-8") == "Version 1 content"
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_repo_revert_commit():
    tmp_dir = tempfile.mkdtemp(prefix="test_repo_revert_")
    ws = Path(tmp_dir)
    try:
        init_repo(str(ws))
        p = ws / "prompts" / "sample.md"
        p.parent.mkdir(parents=True, exist_ok=True)

        p.write_text("Initial text", encoding="utf-8")
        c1 = commit_changes("Initial commit", workspace_dir=str(ws))

        p.write_text("Broken text", encoding="utf-8")
        c2 = commit_changes("Breaking commit", workspace_dir=str(ws))
        assert p.read_text(encoding="utf-8") == "Broken text"

        # Revert c2
        c_rev = revert_commit(c2, workspace_dir=str(ws))
        assert len(c_rev) == 40
        assert p.read_text(encoding="utf-8") == "Initial text"

        versions = list_versions(workspace_dir=str(ws))
        assert len(versions) >= 3
        assert "Revert" in versions[0]["message"]
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
