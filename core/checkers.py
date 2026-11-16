"""
Rule-based checkers and LLM-as-judge evaluation engine.
Supports exact_match, contains, not_contains, regex, json_schema_valid, max_words, and llm_judge.
"""

import re
import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from core.llm import OllamaClient, default_client

logger = logging.getLogger(__name__)


def extract_json_from_text(text: str) -> Optional[Any]:
    """Extract valid JSON from text, stripping markdown backticks if present."""
    text = text.strip()
    # Strip markdown json blocks
    if "```" in text:
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
        if match:
            text = match.group(1).strip()

    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try finding first { ... } or [ ... ]
    match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", text)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    return None


class Checker:
    """Evaluates an output against a single check definition."""

    @staticmethod
    def check_exact_match(output: str, check_def: Dict[str, Any]) -> Tuple[bool, str]:
        expected = str(check_def.get("value", ""))
        case_sensitive = check_def.get("case_sensitive", False)
        strip = check_def.get("strip", True)

        actual = output.strip() if strip else output
        target = expected.strip() if strip else expected

        if not case_sensitive:
            actual = actual.lower()
            target = target.lower()

        passed = actual == target
        details = f"Expected '{expected}', got '{output.strip()}'" if not passed else "Exact match passed"
        return passed, details

    @staticmethod
    def check_contains(output: str, check_def: Dict[str, Any]) -> Tuple[bool, str]:
        case_sensitive = check_def.get("case_sensitive", False)
        values = check_def.get("values")
        if values is None:
            val = check_def.get("value", "")
            values = [val] if val else []

        target_text = output if case_sensitive else output.lower()

        missing = []
        for val in values:
            v_match = val if case_sensitive else str(val).lower()
            if v_match not in target_text:
                missing.append(val)

        passed = len(missing) == 0
        details = f"Missing required substring(s): {missing}" if not passed else "Contains check passed"
        return passed, details

    @staticmethod
    def check_not_contains(output: str, check_def: Dict[str, Any]) -> Tuple[bool, str]:
        case_sensitive = check_def.get("case_sensitive", False)
        values = check_def.get("values")
        if values is None:
            val = check_def.get("value", "")
            values = [val] if val else []

        target_text = output if case_sensitive else output.lower()

        found = []
        for val in values:
            v_match = val if case_sensitive else str(val).lower()
            if v_match in target_text:
                found.append(val)

        passed = len(found) == 0
        details = f"Found forbidden substring(s): {found}" if not passed else "Not contains check passed"
        return passed, details

    @staticmethod
    def check_regex(output: str, check_def: Dict[str, Any]) -> Tuple[bool, str]:
        pattern = check_def.get("pattern", "")
        ignore_case = check_def.get("ignore_case", False)
        flags = re.IGNORECASE if ignore_case else 0

        match = re.search(pattern, output, flags)
        passed = match is not None
        details = f"Regex /{pattern}/ failed to match output" if not passed else "Regex check passed"
        return passed, details

    @staticmethod
    def check_json_schema_valid(output: str, check_def: Dict[str, Any]) -> Tuple[bool, str]:
        data = extract_json_from_text(output)
        if data is None:
            return False, "Output does not contain valid JSON"

        required_keys = check_def.get("required_keys", [])
        if required_keys:
            if not isinstance(data, dict):
                return False, f"Expected JSON dictionary, got {type(data).__name__}"
            missing_keys = [k for k in required_keys if k not in data]
            if missing_keys:
                return False, f"JSON missing required key(s): {missing_keys}"

        expected_types = check_def.get("expected_types", {})
        if expected_types and isinstance(data, dict):
            type_map = {
                "str": str,
                "string": str,
                "int": int,
                "integer": int,
                "float": (int, float),
                "number": (int, float),
                "list": list,
                "array": list,
                "dict": dict,
                "object": dict,
                "bool": bool,
                "boolean": bool,
            }
            for k, expected_t in expected_types.items():
                if k in data:
                    target_cls = type_map.get(str(expected_t).lower())
                    if target_cls and not isinstance(data[k], target_cls):
                        return False, f"Key '{k}' expected type {expected_t}, got {type(data[k]).__name__}"

        return True, "JSON schema check passed"

    @staticmethod
    def check_max_words(output: str, check_def: Dict[str, Any]) -> Tuple[bool, str]:
        max_words = int(check_def.get("count", check_def.get("max", 40)))
        words = output.strip().split()
        count = len(words)
        passed = count <= max_words
        details = f"Word count {count} exceeded maximum of {max_words}" if not passed else f"Word count ({count}) <= {max_words}"
        return passed, details

    @staticmethod
    def check_llm_judge(
        output: str,
        check_def: Dict[str, Any],
        client: Optional[OllamaClient] = None,
    ) -> Tuple[bool, str, Dict[str, Any]]:
        client = client or default_client
        rubric = check_def.get("rubric", "Evaluate if the response adheres to all instructions.")
        min_score = int(check_def.get("min_score", 70))

        judge_prompt = f"""You are an expert impartial AI quality judge evaluating an LLM response.
Rubric:
{rubric}

Response to evaluate:
\"\"\"
{output}
\"\"\"

Score the response strictly from 0 to 100 based on the rubric.
Respond ONLY with a valid JSON object matching this schema:
{{
  "score": <integer from 0 to 100>,
  "reason": "<one or two sentence explanation>"
}}
"""
        try:
            resp = client.generate(
                prompt=judge_prompt,
                temperature=0.0,
                format_json=True,
            )
            parsed = extract_json_from_text(resp.text)
            if parsed and isinstance(parsed, dict) and "score" in parsed:
                score = int(parsed["score"])
                reason = parsed.get("reason", "")
                passed = score >= min_score
                details = f"Score: {score}/{100} (threshold: {min_score}). Reason: {reason}"
                return passed, details, {"score": score, "reason": reason}
            else:
                return False, f"LLM judge output was not parseable: {resp.text[:100]}", {"raw": resp.text}
        except Exception as e:
            logger.error(f"LLM judge failed: {e}")
            return False, f"LLM judge execution failed: {e}", {"error": str(e)}


def evaluate_checks(
    output: str,
    checks: List[Dict[str, Any]],
    client: Optional[OllamaClient] = None,
) -> Tuple[bool, List[Dict[str, Any]]]:
    """
    Run all checks on the output.
    Returns (all_passed, check_details).
    """
    if not checks:
        return True, [{"check": "none", "passed": True, "details": "No checks specified"}]

    all_passed = True
    check_details = []

    for check in checks:
        check_type = check.get("type", "").lower()
        passed = False
        details = ""
        extra_meta = {}

        if check_type == "exact_match":
            passed, details = Checker.check_exact_match(output, check)
        elif check_type == "contains":
            passed, details = Checker.check_contains(output, check)
        elif check_type == "not_contains":
            passed, details = Checker.check_not_contains(output, check)
        elif check_type == "regex":
            passed, details = Checker.check_regex(output, check)
        elif check_type == "json_schema_valid":
            passed, details = Checker.check_json_schema_valid(output, check)
        elif check_type == "max_words":
            passed, details = Checker.check_max_words(output, check)
        elif check_type == "llm_judge":
            passed, details, extra_meta = Checker.check_llm_judge(output, check, client=client)
        else:
            passed = False
            details = f"Unknown check type: {check_type}"

        if not passed:
            all_passed = False

        record = {
            "type": check_type,
            "passed": passed,
            "details": details,
        }
        if extra_meta:
            record["meta"] = extra_meta
        check_details.append(record)

    return all_passed, check_details

