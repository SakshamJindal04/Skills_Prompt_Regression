import re
import json
import logging
from core.db import get_session
from core.models import Score
from core.llm import default_client
from core.checkers import extract_json_from_text

logger = logging.getLogger(__name__)


def check_exact(output, check_def):
    expected = str(check_def.get("value", "")).strip()
    actual = str(output).strip()
    case_sensitive = check_def.get("case_sensitive", False)
    if not case_sensitive:
        return actual.lower() == expected.lower()
    return actual == expected


def check_contains(output, check_def):
    values = check_def.get("values")
    if values is None:
        val = check_def.get("value", "")
        values = [val] if val else []
    target = output.lower()
    for v in values:
        if str(v).lower() not in target:
            return False
    return True


def check_not_contains(output, check_def):
    values = check_def.get("values")
    if values is None:
        val = check_def.get("value", "")
        values = [val] if val else []
    target = output.lower()
    for v in values:
        if str(v).lower() in target:
            return False
    return True


def check_regex(output, check_def):
    pattern = check_def.get("pattern", "")
    flags = re.IGNORECASE if check_def.get("ignore_case", False) else 0
    return re.search(pattern, output, flags) is not None


def check_valid_json(output, check_def):
    data = extract_json_from_text(output)
    return data is not None


def check_json_schema(output, check_def):
    data = extract_json_from_text(output)
    if data is None:
        return False
    req_keys = check_def.get("required_keys", [])
    if req_keys:
        if not isinstance(data, dict):
            return False
        for k in req_keys:
            if k not in data:
                return False
    return True


def check_max_words(output, check_def):
    limit = int(check_def.get("count", check_def.get("max", 40)))
    words = output.strip().split()
    return len(words) <= limit


def check_llm_judge(output, check_def, client=None, model_under_test=None):
    client = client or default_client
    judge_model = check_def.get("judge_model") or client.get_judge_model(model_under_test)
    rubric = check_def.get("rubric", "Evaluate output quality")
    min_score = int(check_def.get("min_score", 70))

    prompt = f"""You are an impartial judge evaluating an LLM response.
Rubric:
{rubric}

Response to evaluate:
\"\"\"
{output}
\"\"\"

Score from 0 to 100.
Respond JSON only:
{{
  "score": <0-100>,
  "reason": "<short explanation>"
}}
"""
    try:
        resp = client.generate(prompt=prompt, temperature=0.0, format_json=True, model=judge_model)
        data = extract_json_from_text(resp.text)
        if data and isinstance(data, dict) and "score" in data:
            score = int(data["score"])
            return score >= min_score, score
    except Exception:
        pass
    return False, 0.0


def score_trace(trace, checks, client=None):
    client = client or default_client
    output = trace.get("output", "") or ""
    model_under_test = trace.get("model", "qwen2.5:3b")
    all_passed = True
    check_details = []

    for c in checks:
        ctype = c.get("type", "").lower()
        passed = False
        score_val = 1.0

        if ctype in ("exact_match", "exact"):
            passed = check_exact(output, c)
        elif ctype == "contains":
            passed = check_contains(output, c)
        elif ctype == "not_contains":
            passed = check_not_contains(output, c)
        elif ctype == "regex":
            passed = check_regex(output, c)
        elif ctype == "valid_json":
            passed = check_valid_json(output, c)
        elif ctype in ("json_schema", "json_schema_valid"):
            passed = check_json_schema(output, c)
        elif ctype == "max_words":
            passed = check_max_words(output, c)
        elif ctype == "llm_judge":
            passed, score_val = check_llm_judge(output, c, client=client, model_under_test=model_under_test)
        else:
            passed = False

        if not passed:
            all_passed = False
            score_val = 0.0

        check_details.append({"type": ctype, "passed": passed, "score": score_val})

    # Save to database if trace has id
    trace_id = trace.get("id")
    if trace_id:
        model_meta = client.get_model_metadata(model_under_test)
        digest = trace.get("model_digest") or model_meta.get("digest")
        with get_session() as session:
            rec = Score(
                trace_id=trace_id,
                test_id=trace.get("test_id", ""),
                artifact_id=trace.get("artifact_id", 0),
                run_index=trace.get("run_index", 0),
                passed=all_passed,
                score=1.0 if all_passed else 0.0,
                check_details=check_details,
                model_id=model_under_test,
                model_digest=digest,
            )
            session.add(rec)

    return {
        "passed": all_passed,
        "score": 1.0 if all_passed else 0.0,
        "check_details": check_details,
    }


def compute_majority_vote(run_scores):
    """
    Given a list of pass/fail booleans for runs of one test:
    Test PASSES if at least 3 of 5 runs pass (majority).
    Returns (majority_passed, agreement_ratio).
    """
    total = len(run_scores)
    if total == 0:
        return False, 1.0

    passes = sum(1 for p in run_scores if p)
    threshold = (total // 2) + 1  # 3 for k=5, 2 for k=3
    majority_passed = passes >= threshold

    # Agreement ratio: runs that agreed with the majority outcome / total
    maj_count = passes if majority_passed else (total - passes)
    agreement = maj_count / total

    return majority_passed, agreement


def score_artifact_runs(artifact_id, test_cases, client=None):
    from core.models import Trace
    tc_map = {tc["id"]: tc.get("checks", []) for tc in test_cases}
    scores = []
    with get_session() as session:
        traces = session.query(Trace).filter_by(artifact_id=artifact_id).all()
        trace_dicts = [t.to_dict() for t in traces]

    for tr in trace_dicts:
        tid = tr.get("test_id")
        checks = tc_map.get(tid, [])
        res = score_trace(tr, checks, client=client)
        scores.append(res)
    return scores

