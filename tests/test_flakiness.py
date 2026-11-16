import pytest
from core.health import analyze_test_health


def test_test_health_categorization_and_quarantine():
    mock_scores = {
        "t_flaky": [True, False, True, False, True],      # 60% pass rate -> consistency = 0.60 (< 0.70 threshold)
        "t_always_pass": [True, True, True, True, True],  # 100% pass rate -> consistency = 1.0
        "t_always_fail": [False, False, False, False, False], # 0% pass rate -> consistency = 1.0 (consistently failing)
        "t_stable": [True, True, True, True, False],      # 80% pass rate -> consistency = 0.80 (>= 0.70)
    }

    test_meta = [
        {"id": "t_flaky", "target": "prompt_a", "suite": "test"},
        {"id": "t_always_pass", "target": "prompt_a", "suite": "test"},
        {"id": "t_always_fail", "target": "prompt_a", "suite": "test"},
        {"id": "t_stable", "target": "prompt_a", "suite": "test"},
    ]

    res = analyze_test_health(
        scores_by_test=mock_scores,
        test_cases=test_meta,
        quarantine_threshold=0.70
    )

    summary = res["summary"]
    assert summary["flaky_count"] >= 1
    assert summary["always_pass_count"] >= 1
    assert summary["always_fail_count"] >= 1

    # Check quarantine
    quarantined_ids = [t["test_id"] for t in res["quarantined"]]
    assert "t_flaky" in quarantined_ids
    assert "t_stable" not in quarantined_ids

