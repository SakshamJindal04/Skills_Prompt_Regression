"""
Unit tests for core/versioner.py.
Verifies artifact hashing, manifest generation, parameter sorting invariance,
and baseline registry tracking.
"""

import tempfile
import shutil
from pathlib import Path
import pytest

from core.versioner import (
    hash_content,
    build_manifest,
    register_artifact,
    get_current_baseline,
    set_current_baseline,
)
from core.models import Artifact
from core.db import get_session


def test_hash_content_determinism():
    files = {
        "prompts/a.md": "Rule 1: Always respond in JSON.",
        "prompts/b.md": "Rule 2: Never include markdown fences.",
    }
    model = "qwen2.5:3b"
    params1 = {"temperature": 0.7, "max_tokens": 512}
    params2 = {"max_tokens": 512, "temperature": 0.7}

    h1 = hash_content(files, model, params1)
    h2 = hash_content(files, model, params2)

    assert len(h1) == 64
    assert h1 == h2  # Key order in params must not alter hash


def test_hash_content_sensitivity():
    files1 = {"prompts/a.md": "Rule 1: Always respond in JSON."}
    files2 = {"prompts/a.md": "Rule 1: Always respond in XML."}
    model = "qwen2.5:3b"
    params = {"temperature": 0.7}

    h1 = hash_content(files1, model, params)
    h2 = hash_content(files2, model, params)

    assert h1 != h2

    # Model sensitivity
    h3 = hash_content(files1, "qwen2.5:7b", params)
    assert h1 != h3


def test_build_manifest():
    files = {"prompts/sentiment.md": "Analyze the tone of the input text."}
    manifest = build_manifest(files, "qwen2.5:3b", {"temperature": 0.0})

    assert "files" in manifest
    assert "prompts/sentiment.md" in manifest["files"]
    assert len(manifest["files"]["prompts/sentiment.md"]) == 64
    assert manifest["model_id"] == "qwen2.5:3b"
    assert manifest["params"]["temperature"] == 0.0


def test_register_artifact_and_baseline():
    tmp_dir = tempfile.mkdtemp(prefix="test_ver_")
    ws = Path(tmp_dir)
    p = ws / "prompts" / "sample.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("Test prompt body", encoding="utf-8")

    art_id, manifest = register_artifact(
        ["prompts/sample.md"],
        model_id="qwen2.5:3b",
        params={"temperature": 0.7},
        artifact_type="prompt",
        name="sample_prompt",
        workspace_dir=str(ws),
    )

    assert art_id is not None
    assert "prompts/sample.md" in manifest["files"]

    # Registering identical artifact returns same ID
    art_id_dup, _ = register_artifact(
        ["prompts/sample.md"],
        model_id="qwen2.5:3b",
        params={"temperature": 0.7},
        artifact_type="prompt",
        name="sample_prompt",
        workspace_dir=str(ws),
    )
    assert art_id == art_id_dup

    # Set as baseline
    set_current_baseline(art_id, notes="Initial test baseline")
    curr = get_current_baseline()
    assert curr is not None
    assert curr["id"] == art_id

    shutil.rmtree(tmp_dir, ignore_errors=True)

