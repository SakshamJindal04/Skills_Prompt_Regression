"""
Unit tests for Skill Registry, Embedding similarity, BM25 retrieval, and Skill Benchmarking.
"""

import tempfile
import shutil
from pathlib import Path
import pytest

from core.skills import (
    Skill,
    SkillRegistry,
    BM25Selector,
    EmbeddingSelector,
    cosine_similarity,
    run_skill_benchmark,
)


@pytest.fixture
def temp_skills_dir():
    tmp_dir = tempfile.mkdtemp(prefix="test_skills_")
    ws = Path(tmp_dir)

    # Create 3 skills
    s1 = ws / "write-sql"
    s1.mkdir(parents=True)
    (s1 / "SKILL.md").write_text(
        "---\nname: write-sql\ndescription: Generate, write and optimize SQL database queries, joins, and schema.\n---\n# SQL Skill\n",
        encoding="utf-8"
    )

    s2 = ws / "translate-text"
    s2.mkdir(parents=True)
    (s2 / "SKILL.md").write_text(
        "---\nname: translate-text\ndescription: Translate text between languages preserving idiom and meaning.\n---\n# Translation Skill\n",
        encoding="utf-8"
    )

    s3 = ws / "summarize-text"
    s3.mkdir(parents=True)
    (s3 / "SKILL.md").write_text(
        "---\nname: summarize-text\ndescription: Condense lengthy text and documents into concise executive summaries.\n---\n# Summarize Skill\n",
        encoding="utf-8"
    )

    yield tmp_dir
    shutil.rmtree(tmp_dir, ignore_errors=True)


def test_skill_registry_parsing(temp_skills_dir):
    registry = SkillRegistry(skills_dir=temp_skills_dir)
    skills = registry.list_skills()
    assert len(skills) == 3

    sql = registry.get_skill("write-sql")
    assert sql is not None
    assert "SQL database queries" in sql.description
    assert sql.name == "write-sql"


def test_cosine_similarity():
    v1 = [1.0, 0.0, 0.0]
    v2 = [1.0, 0.0, 0.0]
    v3 = [0.0, 1.0, 0.0]

    assert round(cosine_similarity(v1, v2), 4) == 1.0
    assert round(cosine_similarity(v1, v3), 4) == 0.0


def test_bm25_selector(temp_skills_dir):
    registry = SkillRegistry(skills_dir=temp_skills_dir)
    selector = BM25Selector(registry)

    # SQL query
    ranked, lat = selector.select("Write a PostgreSQL query with CTE joins", top_k=2)
    assert len(ranked) >= 1
    assert ranked[0][0] == "write-sql"

    # Translation query
    ranked_t, _ = selector.select("Translate this English email into French", top_k=2)
    assert len(ranked_t) >= 1
    assert ranked_t[0][0] == "translate-text"


def test_skill_benchmark_evaluation(temp_skills_dir):
    registry = SkillRegistry(skills_dir=temp_skills_dir)
    items = [
        {"task": "Write an SQL SELECT query", "expected_skill": "write-sql"},
        {"task": "Translate paragraph from Spanish to English", "expected_skill": "translate-text"},
        {"task": "Summarize this 10 page meeting transcript", "expected_skill": "summarize-text"},
    ]

    res = run_skill_benchmark(items, selector_method="bm25", registry=registry)
    assert res["top1"] == 1.0
    assert res["top3"] == 1.0
    assert res["latency_mean"] >= 0.0

