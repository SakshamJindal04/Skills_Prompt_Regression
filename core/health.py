from typing import List, Dict, Any, Optional
from core.db import get_session
from core.models import Score, TestCase, Artifact
from core.policy import load_policy


def analyze_test_health(
    scores_by_test: Optional[Dict[str, List[bool]]] = None,
    test_cases: Optional[List[Dict[str, Any]]] = None,
    quarantine_threshold: Optional[float] = None
) -> Dict[str, Any]:
    """
    Analyzes test health across runs:
    - flaky: pass rate between 0.2 and 0.8 on repeated runs of the same artifact.
    - always_pass: pass rate == 1.0 on all tested runs.
    - always_fail: pass rate == 0.0 on all tested runs.
    - stale: test target prompt has 3+ commit revisions.
    - quarantined: test consistency < quarantine_threshold.
    """
    policy = load_policy()
    if quarantine_threshold is None:
        quarantine_threshold = policy.get("quarantine_consistency_threshold", 0.70)

    # If scores not provided, load from DB
    if scores_by_test is None:
        scores_by_test = {}
        with get_session() as session:
            scores = session.query(Score).all()
            for s in scores:
                scores_by_test.setdefault(s.test_id, []).append(bool(s.passed))

    if test_cases is None:
        with get_session() as session:
            test_cases = [tc.to_dict() for tc in session.query(TestCase).all()]

    test_meta_map = {tc.get("id"): tc for tc in test_cases}

    flaky_tests = []
    always_pass_tests = []
    always_fail_tests = []
    quarantined_tests = []
    healthy_tests = []
    stale_tests = []

    # Get prompt revision counts for staleness detection
    prompt_revisions: Dict[str, int] = {}
    try:
        from core.repo import list_versions
        versions = list_versions(limit=50)
        # Count modifications per prompt file
        for v in versions:
            for f in v.get("files", []):
                prompt_revisions[f] = prompt_revisions.get(f, 0) + 1
    except Exception:
        pass

    for t_id, runs in scores_by_test.items():
        if not runs:
            continue
        total = len(runs)
        passes = sum(1 for r in runs if r)
        pass_rate = round(passes / total, 4)

        # Consistency metric: how deterministic is the outcome
        consistency = round(max(pass_rate, 1.0 - pass_rate), 4)
        is_quarantined = consistency < quarantine_threshold

        meta = test_meta_map.get(t_id, {})
        target = meta.get("target", "unknown")
        suite = meta.get("suite", "unknown")
        family = meta.get("family", meta.get("slices", {}).get("family", "functional"))

        # Staleness check
        rev_count = prompt_revisions.get(f"prompts/{target}.md", 0)
        is_stale = rev_count >= 3

        item = {
            "test_id": t_id,
            "suite": suite,
            "target": target,
            "family": family,
            "total_runs": total,
            "passes": passes,
            "pass_rate": pass_rate,
            "consistency": consistency,
            "quarantined": is_quarantined,
            "stale": is_stale,
            "recommendation": ""
        }

        if is_quarantined:
            item["recommendation"] = "Quarantine test; relax strict token checks or evaluate with LLM judge."
            quarantined_tests.append(item)

        if 0.2 <= pass_rate <= 0.8:
            item["category"] = "flaky"
            if not is_quarantined:
                item["recommendation"] = "Flaky run-to-run variation; inspect prompt ambiguity or model sampling temperature."
            flaky_tests.append(item)
        elif pass_rate == 1.0:
            item["category"] = "always_pass"
            item["recommendation"] = "Consistently passes; candidate for lower-frequency regression or baseline sanity."
            always_pass_tests.append(item)
        elif pass_rate == 0.0:
            item["category"] = "always_fail"
            item["recommendation"] = "Consistently fails; check for impossible assertion or ungrounded rule."
            always_fail_tests.append(item)
        else:
            item["category"] = "healthy"
            item["recommendation"] = "Nominal performance."
            healthy_tests.append(item)

        if is_stale:
            stale_tests.append(item)

    return {
        "summary": {
            "total_evaluated": len(scores_by_test),
            "flaky_count": len(flaky_tests),
            "always_pass_count": len(always_pass_tests),
            "always_fail_count": len(always_fail_tests),
            "quarantined_count": len(quarantined_tests),
            "stale_count": len(stale_tests),
            "quarantine_threshold": quarantine_threshold,
        },
        "flaky": flaky_tests,
        "always_pass": always_pass_tests,
        "always_fail": always_fail_tests,
        "quarantined": quarantined_tests,
        "stale": stale_tests,
        "healthy": healthy_tests,
    }

