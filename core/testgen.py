import json
import logging
from core.llm import default_client
from core.checkers import extract_json_from_text

logger = logging.getLogger(__name__)


def extract_prompt_rules(prompt_text, client=None):
    client = client or default_client

    prompt = f"""You are a test engineer analyzing a prompt.
Prompt text:
\"\"\"
{prompt_text}
\"\"\"

Extract:
1. Input specification (what input the prompt expects).
2. Concrete checkable output rules.
For each rule give:
- id: e.g. rule_1
- description: concise description of the rule
- check_type: one of [exact_match, contains, not_contains, regex, json_schema_valid, max_words, llm_judge]
- parameter: expected parameter (e.g. 40 for max_words, list of required keys for json_schema_valid, or expected string)

Output JSON only:
{{
  "input_spec": "<input description>",
  "rules": [
    {{
      "id": "rule_1",
      "description": "<rule>",
      "check_type": "max_words",
      "parameter": 40
    }}
  ]
}}
"""
    try:
        resp = client.generate(prompt=prompt, temperature=0.0, format_json=True)
        data = extract_json_from_text(resp.text)
        if data and isinstance(data, dict) and "rules" in data:
            return data
    except Exception as e:
        logger.warning(f"Rule extraction failed: {e}")

    # Fallback rules
    rules = []
    lower = prompt_text.lower()
    if "json" in lower:
        rules.append({"id": "rule_json", "description": "Output must be valid JSON", "check_type": "json_schema_valid", "parameter": []})
    if "words" in lower:
        rules.append({"id": "rule_words", "description": "Output must not exceed 40 words", "check_type": "max_words", "parameter": 40})
    if "positive" in lower or "negative" in lower:
        rules.append({"id": "rule_label", "description": "Output must be single label POSITIVE/NEGATIVE/NEUTRAL", "check_type": "exact_match", "parameter": "POSITIVE"})
    if not rules:
        rules.append({"id": "rule_general", "description": "Complies with prompt instructions", "check_type": "llm_judge", "parameter": "Accurate response"})

    return {
        "input_spec": "Arbitrary text",
        "rules": rules,
    }


def generate_tests_for_rules(prompt_name, prompt_text, rules_spec, client=None):
    client = client or default_client
    generated_tests = []
    rules = rules_spec.get("rules", [])

    for r in rules:
        rule_id = r.get("id", "rule")
        rule_desc = r.get("description", "")
        check_type = r.get("check_type", "llm_judge")
        param = r.get("parameter", "")

        prompt = f"""You are PromptPex, an adversarial test generator.
Prompt:
\"\"\"
{prompt_text}
\"\"\"

Target Rule ({rule_id}):
\"{rule_desc}\"

1. Write an inverse rule (a contradictory counter-case or adversarial trap).
2. Generate 2 inputs:
   - Test 1: standard positive compliance test for this rule.
   - Test 2: boundary or adversarial test challenging the rule using the inverse rule.

Output JSON only:
{{
  "inverse_rule": "<adversarial counter-concept>",
  "tests": [
    {{
      "input": "<test 1 input>",
      "difficulty": "medium",
      "edge_case": false,
      "expected": "<expected output or empty>"
    }},
    {{
      "input": "<test 2 adversarial input>",
      "difficulty": "hard",
      "edge_case": true,
      "expected": "<expected output or empty>"
    }}
  ]
}}
"""
        tests_list = []
        try:
            resp = client.generate(prompt=prompt, temperature=0.3, format_json=True)
            res_json = extract_json_from_text(resp.text)
            tests_list = res_json.get("tests", []) if res_json else []
        except Exception:
            pass

        if not tests_list:
            tests_list = [
                {"input": f"Standard input testing {rule_desc}", "difficulty": "medium", "edge_case": False, "expected": str(param)},
                {"input": f"Adversarial input testing {rule_desc}", "difficulty": "hard", "edge_case": True, "expected": str(param)},
            ]

        for i, t in enumerate(tests_list):
            is_inverse = (i == 1)
            tid = f"pex_{prompt_name}_{rule_id}_{'inv' if is_inverse else 'std'}_{i+1}"

            checks = []
            if check_type == "exact_match":
                checks.append({"type": "exact_match", "value": t.get("expected") or str(param)})
            elif check_type == "max_words":
                limit = int(param) if str(param).isdigit() else 40
                checks.append({"type": "max_words", "count": limit})
            elif check_type == "json_schema_valid":
                req_keys = param if isinstance(param, list) else []
                checks.append({"type": "json_schema_valid", "required_keys": req_keys})
            elif check_type == "contains":
                checks.append({"type": "contains", "value": str(param)})
            else:
                checks.append({"type": "llm_judge", "rubric": rule_desc, "min_score": 70})

            generated_tests.append({
                "id": tid,
                "suite": "promptpex",
                "target": prompt_name,
                "input": t.get("input", ""),
                "slices": {
                    "rule": rule_id,
                    "difficulty": t.get("difficulty", "medium"),
                    "edge_case": str(t.get("edge_case", False)).lower(),
                    "is_inverse": str(is_inverse).lower(),
                },
                "checks": checks,
                "origin": "promptpex",
                "rule_id": rule_id,
                "critical": False,
            })

    return generated_tests


# Aliases for Panel Lab interface
extract_prompt_spec = extract_prompt_rules


def generate_test_suite_from_spec(spec, count=20, prompt_text="", client=None):
    tests = generate_tests_for_rules("prompt", prompt_text, spec, client=client)
    return tests[:count]

