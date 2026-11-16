"""
Unit tests for core.attribution (ablate_and_attribute, auto_bisect, run_test_suite_on_workspace).
"""

import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock
from core.repo import init_repo, commit_changes
from core.attribution import (
    run_test_suite_on_workspace,
    ablate_and_attribute,
    auto_bisect,
)


def test_run_test_suite_on_workspace_empty():
    res = run_test_suite_on_workspace(target_suite="nonexistent_suite_xyz")
    assert res["overall_pass_rate"] == 0.0
    assert res["total_evals"] == 0


def test_ablate_and_attribute_no_prompt_changes():
    tmp_dir = tempfile.mkdtemp(prefix="test_attr_")
    ws = Path(tmp_dir)
    try:
        init_repo(str(ws))
        other_file = ws / "notes.txt"
        other_file.write_text("Hello", encoding="utf-8")
        c1 = commit_changes("Initial commit", workspace_dir=str(ws))

        other_file.write_text("World", encoding="utf-8")
        c2 = commit_changes("Edit notes", workspace_dir=str(ws))

        with patch("core.attribution.init_repo") as mock_init:
            import git
            mock_init.return_value = git.Repo(str(ws))
            res = ablate_and_attribute(c1, c2)
            assert res["guilty_file"] is None
            assert "No prompt or skill files modified" in res["message"]
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_ablate_and_attribute_with_prompt_change():
    tmp_dir = tempfile.mkdtemp(prefix="test_attr_prompt_")
    ws = Path(tmp_dir)
    try:
        init_repo(str(ws))
        p_dir = ws / "prompts"
        p_dir.mkdir(parents=True, exist_ok=True)
        p1 = p_dir / "sentiment.md"
        p1.write_text("Good baseline prompt", encoding="utf-8")
        c1 = commit_changes("Baseline prompt", workspace_dir=str(ws))

        p1.write_text("Corrupted bad prompt", encoding="utf-8")
        c2 = commit_changes("Corrupted prompt", workspace_dir=str(ws))

        with patch("core.attribution.init_repo") as mock_init, \
             patch("core.attribution.run_test_suite_on_workspace") as mock_run, \
             patch("core.attribution.get_workspace_path") as mock_ws:
            import git
            mock_init.return_value = git.Repo(str(ws))
            mock_ws.return_value = ws

            # Simulate bad_stats giving 0.40, and ablated_stats giving 0.90
            mock_run.side_effect = [
                {"overall_pass_rate": 0.40, "total_passed": 4, "total_evals": 10},
                {"overall_pass_rate": 0.90, "total_passed": 9, "total_evals": 10},
            ]

            res = ablate_and_attribute(c1, c2, n_repeats=1, workspace_dir=str(ws))
            assert res["guilty_file"] == "prompts/sentiment.md"
            assert len(res["file_impacts"]) == 1
            assert res["file_impacts"][0]["recovery_delta"] == 0.50
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_auto_bisect_mocked():
    tmp_dir = tempfile.mkdtemp(prefix="test_bisect_run_")
    ws = Path(tmp_dir)
    try:
        init_repo(str(ws))
        p = ws / "prompts" / "test.md"
        p.parent.mkdir(parents=True, exist_ok=True)

        p.write_text("v1", encoding="utf-8")
        c1 = commit_changes("v1", workspace_dir=str(ws))

        p.write_text("v2", encoding="utf-8")
        c2 = commit_changes("v2", workspace_dir=str(ws))

        p.write_text("v3 bad", encoding="utf-8")
        c3 = commit_changes("v3 bad", workspace_dir=str(ws))

        with patch("core.attribution.init_repo") as mock_init, \
             patch("core.attribution.run_test_suite_on_workspace") as mock_run:
            import git
            mock_init.return_value = git.Repo(str(ws))

            # good=1.0, c2=1.0, c3=0.5 (regressed by > 0.10)
            mock_run.side_effect = [
                {"overall_pass_rate": 1.0},
                {"overall_pass_rate": 1.0},
                {"overall_pass_rate": 0.5},
            ]

            res = auto_bisect(c1, c3, reg_threshold=0.10, n_repeats=1, workspace_dir=str(ws))
            assert res["first_bad_commit"] is not None
            assert res["first_bad_commit"]["git_hash"] == c3
            assert res["first_bad_commit"]["status"] == "REGRESSED"
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
