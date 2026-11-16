"""
Unit tests for rule-based checkers and JSON parsing.
"""

import pytest
from core.checkers import Checker, evaluate_checks, extract_json_from_text


def test_extract_json():
    # Direct JSON
    assert extract_json_from_text('{"key": "value"}') == {"key": "value"}
    # Markdown-wrapped JSON
    text_md = "Here is the result:\n```json\n{\"entities\": [\"Apple\", \"Google\"]}\n```\nHope that helps!"
    assert extract_json_from_text(text_md) == {"entities": ["Apple", "Google"]}
    # Malformed text
    assert extract_json_from_text("No json here") is None


def test_exact_match():
    # Basic
    passed, _ = Checker.check_exact_match("POSITIVE", {"value": "POSITIVE"})
    assert passed
    # Case insensitive
    passed, _ = Checker.check_exact_match("positive", {"value": "POSITIVE", "case_sensitive": False})
    assert passed
    # Case sensitive mismatch
    passed, _ = Checker.check_exact_match("positive", {"value": "POSITIVE", "case_sensitive": True})
    assert not passed
    # Stripping whitespace
    passed, _ = Checker.check_exact_match("  NEUTRAL \n", {"value": "NEUTRAL", "strip": True})
    assert passed


def test_contains_and_not_contains():
    text = "Satya Nadella spoke at Microsoft headquarters in Seattle."
    # Contains single
    passed, _ = Checker.check_contains(text, {"value": "Microsoft"})
    assert passed
    # Contains multiple
    passed, _ = Checker.check_contains(text, {"values": ["Satya Nadella", "Seattle"]})
    assert passed
    # Contains missing
    passed, _ = Checker.check_contains(text, {"values": ["Google"]})
    assert not passed

    # Not contains
    passed, _ = Checker.check_not_contains(text, {"values": ["Google", "Amazon"]})
    assert passed
    passed, _ = Checker.check_not_contains(text, {"values": ["Microsoft"]})
    assert not passed


def test_regex():
    text = "Order confirmation: #ORD-98421 on 2026-05-12"
    passed, _ = Checker.check_regex(text, {"pattern": r"#ORD-\d{5}"})
    assert passed
    passed, _ = Checker.check_regex(text, {"pattern": r"#ORD-\d{8}"})
    assert not passed


def test_json_schema_valid():
    valid_json = '{"entities": [{"text": "Apple", "type": "ORG"}], "count": 1}'
    passed, _ = Checker.check_json_schema_valid(valid_json, {"required_keys": ["entities"]})
    assert passed

    # Missing required key
    passed, _ = Checker.check_json_schema_valid(valid_json, {"required_keys": ["entities", "metadata"]})
    assert not passed

    # Type check
    passed, _ = Checker.check_json_schema_valid(valid_json, {
        "required_keys": ["entities"],
        "expected_types": {"count": "int", "entities": "list"}
    })
    assert passed

    # Invalid type
    passed, _ = Checker.check_json_schema_valid(valid_json, {
        "expected_types": {"count": "str"}
    })
    assert not passed

    # Non-JSON
    passed, _ = Checker.check_json_schema_valid("Just regular text", {})
    assert not passed


def test_max_words():
    short_text = "This is a concise summary of the quarterly report facts."
    passed, _ = Checker.check_max_words(short_text, {"count": 15})
    assert passed

    long_text = "word " * 50
    passed, _ = Checker.check_max_words(long_text, {"count": 40})
    assert not passed


def test_evaluate_checks():
    output = "POSITIVE"
    checks = [
        {"type": "exact_match", "value": "POSITIVE"},
        {"type": "max_words", "count": 1},
    ]
    all_passed, details = evaluate_checks(output, checks)
    assert all_passed
    assert len(details) == 2
    assert all(d["passed"] for d in details)

