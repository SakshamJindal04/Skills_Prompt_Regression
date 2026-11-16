"""
Unit tests for PromptPex test generator (core.testgen).
"""

from unittest.mock import MagicMock
from core.testgen import extract_prompt_rules, generate_tests_for_rules


class MockLLMResponse:
    def __init__(self, text):
        self.text = text


def test_extract_prompt_rules_mocked():
    mock_client = MagicMock()
    mock_client.generate.return_value = MockLLMResponse(
        """```json
        {
          "input_spec": "Customer reviews in English",
          "rules": [
            {
              "id": "rule_sentiment_label",
              "description": "Output must be POSITIVE or NEGATIVE",
              "check_type": "exact_match",
              "parameter": "POSITIVE"
            },
            {
              "id": "rule_conciseness",
              "description": "Output must not exceed 10 words",
              "check_type": "max_words",
              "parameter": 10
            }
          ]
        }
        ```"""
    )

    spec = extract_prompt_rules("Classify sentiment of customer review into POSITIVE or NEGATIVE.", client=mock_client)
    assert spec is not None
    assert "rules" in spec
    assert len(spec["rules"]) == 2
    assert spec["rules"][0]["id"] == "rule_sentiment_label"
    assert spec["rules"][1]["parameter"] == 10


def test_extract_prompt_rules_fallback():
    mock_client = MagicMock()
    mock_client.generate.side_effect = RuntimeError("LLM unavailable")

    prompt_text = "Return valid json with sentiment. Must not exceed 40 words. Label POSITIVE or NEGATIVE."
    spec = extract_prompt_rules(prompt_text, client=mock_client)
    assert spec is not None
    assert len(spec["rules"]) >= 2
    rule_ids = [r["id"] for r in spec["rules"]]
    assert "rule_json" in rule_ids
    assert "rule_words" in rule_ids


def test_generate_tests_for_rules_mocked():
    mock_client = MagicMock()
    mock_client.generate.return_value = MockLLMResponse(
        """```json
        {
          "inverse_rule": "Customer writes sarcastic praise with negative intent",
          "tests": [
            {
              "input": "Loved the battery life and display quality.",
              "difficulty": "easy",
              "edge_case": false,
              "expected": "POSITIVE"
            },
            {
              "input": "Great job shipping a broken brick in two pieces!",
              "difficulty": "hard",
              "edge_case": true,
              "expected": "NEGATIVE"
            }
          ]
        }
        ```"""
    )

    rules_spec = {
        "rules": [
            {
                "id": "rule_sentiment",
                "description": "Label must be POSITIVE",
                "check_type": "exact_match",
                "parameter": "POSITIVE",
            }
        ]
    }

    tests = generate_tests_for_rules("sentiment", "Prompt text", rules_spec, client=mock_client)
    assert len(tests) == 2
    assert tests[0]["id"] == "pex_sentiment_rule_sentiment_std_1"
    assert tests[0]["slices"]["is_inverse"] == "false"
    assert tests[0]["checks"][0]["type"] == "exact_match"

    assert tests[1]["id"] == "pex_sentiment_rule_sentiment_inv_2"
    assert tests[1]["slices"]["is_inverse"] == "true"
    assert tests[1]["slices"]["edge_case"] == "true"


def test_generate_tests_for_rules_fallback_check_types():
    mock_client = MagicMock()
    mock_client.generate.side_effect = Exception("LLM call timeout")

    rules_spec = {
        "rules": [
            {"id": "r_json", "description": "JSON check", "check_type": "json_schema_valid", "parameter": ["sentiment"]},
            {"id": "r_words", "description": "Word limit", "check_type": "max_words", "parameter": 30},
            {"id": "r_cont", "description": "Contains word", "check_type": "contains", "parameter": "summary"},
            {"id": "r_judge", "description": "Open ended judge", "check_type": "llm_judge", "parameter": "High accuracy"},
        ]
    }

    tests = generate_tests_for_rules("prompt_foo", "Prompt text", rules_spec, client=mock_client)
    assert len(tests) == 8  # 2 tests per rule x 4 rules
    check_types = [t["checks"][0]["type"] for t in tests]
    assert "json_schema_valid" in check_types
    assert "max_words" in check_types
    assert "contains" in check_types
    assert "llm_judge" in check_types

