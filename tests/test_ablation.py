import pytest
from unittest.mock import MagicMock
from core.attribution import parse_prompt_sections, ablate_prompt_sections
from core.llm import LLMResponse


def test_parse_prompt_sections():
    prompt = """# Role
You are an expert SQL engineer.

# Rules
1. Use standard PostgreSQL.
2. Output raw SQL only.

# Examples
SELECT * FROM orders;
"""
    sections = parse_prompt_sections(prompt)
    assert "Role" in sections
    assert "Rules" in sections
    assert "Examples" in sections
    assert len(sections) == 3


def test_ablate_prompt_sections_mocked():
    prompt = """# Role
You are an expert SQL engineer.

# Rules
Output SELECT queries only.
"""
    mock_client = MagicMock()
    mock_client.generate.return_value = LLMResponse(
        text="SELECT * FROM orders;",
        latency_ms=100.0,
        model="qwen2.5:3b"
    )

    tests = [
        {"id": "t1", "input": "Find orders", "checks": [{"type": "contains", "values": ["SELECT"]}]}
    ]

    res = ablate_prompt_sections(prompt, target_tests=tests, n_repeats=1, client=mock_client)
    assert res["sections_count"] >= 2
    assert "section_impacts" in res
    assert "limitation_note" in res
    assert "interaction effects" in res["limitation_note"].lower()

