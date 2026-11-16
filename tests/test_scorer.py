"""
Unit tests for core/scorer.py.
Verifies all deterministic checks (exact, contains, not_contains, regex,
valid_json, json_schema, max_words) and the LLM-as-judge scoring.
"""

import pytest
from unittest.mock import MagicMock
from core.scorer import (
    check_exact,
    check_contains,
    check_not_contains,
    check_regex,
    check_valid_json,
    check_json_schema,
    check_max_words,
    check_llm_judge,
    score_trace,
)


def test_check_exact():
    assert check_exact("POSITIVE", {"value": "positive", "case_sensitive": False})
    assert not check_exact("POSITIVE", {"value": "positive", "case_sensitive": True})
    assert check_exact("hello world\n", {"value": "hello world"})


def test_check_contains_and_not_contains():
    text = "The quick brown fox jumps over the lazy dog"
    assert check_contains(text, {"values": ["quick", "fox"]})
    assert not check_contains(text, {"values": ["quick", "cat"]})

    assert check_not_contains(text, {"values": ["cat", "elephant"]})
    assert not check_not_contains(text, {"values": ["fox", "elephant"]})


def test_check_regex():
    output = "Order ID: ORD-98124 confirmed"
    assert check_regex(output, {"pattern": r"ORD-\d{5}"})
    assert not check_regex(output, {"pattern": r"^Error"})


def test_check_valid_json():
    assert check_valid_json('{"sentiment": "positive", "score": 0.95}', {})
    assert check_valid_json('Here is your json: ```json\n{"status": "ok"}\n```', {})
    assert not check_valid_json("Not a json at all", {})


def test_check_json_schema():
    valid = '{"sentiment": "positive", "confidence": 0.9, "reason": "happy words"}'
    assert check_json_schema(valid, {"required_keys": ["sentiment", "confidence"]})
    assert not check_json_schema(valid, {"required_keys": ["sentiment", "missing_key"]})


def test_check_max_words():
    short_text = "This is a short five word sentence."
    assert check_max_words(short_text, {"count": 10})
    assert not check_max_words(short_text, {"count": 4})


def test_check_llm_judge_mocked():
    mock_client = MagicMock()
    # High score mock
    mock_client.generate.return_value = MagicMock(
        text='{"score": 90, "reason": "Follows all instructions clearly."}'
    )
    passed_h, score_h = check_llm_judge("Some output", {"min_score": 70}, client=mock_client)
    assert passed_h is True
    assert score_h == 90

    # Low score mock
    mock_client.generate.return_value = MagicMock(
        text='{"score": 45, "reason": "Failed to adhere to constraints."}'
    )
    passed_l, score_l = check_llm_judge("Some output", {"min_score": 70}, client=mock_client)
    assert passed_l is False
    assert score_l == 45


def test_score_trace_combination():
    checks = [
        {"type": "contains", "values": ["summary"]},
        {"type": "max_words", "count": 15},
    ]

    passing_trace = {"output": "This is a brief summary of the text."}
    res_pass = score_trace(passing_trace, checks)
    assert res_pass["passed"] is True
    assert res_pass["score"] == 1.0
    assert len(res_pass["check_details"]) == 2

    failing_trace = {"output": "This text does not have the magic word."}
    res_fail = score_trace(failing_trace, checks)
    assert res_fail["passed"] is False
    assert res_fail["score"] == 0.0
