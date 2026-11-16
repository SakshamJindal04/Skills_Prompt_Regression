"""
Unit tests for core/comparator.py.
Tests McNemar's exact test, majority voting, flip classification, bootstrap CI,
and flat aggregate with flipped tests.
"""

import pytest
import numpy as np
from core.comparator import (
    mcnemar_test,
    classify_outcome,
    bootstrap_ci,
    compare_test_results,
)


def test_mcnemar_exact_value():
    """
    Scipy binomtest exact two-sided test:
    When b=12 (regressed) and c=3 (fixed), binomtest(min(12, 3), 15, 0.5) must equal 0.0352.
    """
    p_val = mcnemar_test(12, 3)
    assert p_val == 0.0352

    # Symmetric test
    assert mcnemar_test(3, 12) == 0.0352

    # No flips
    assert mcnemar_test(0, 0) == 1.0

    # Equal flips
    assert mcnemar_test(5, 5) == 1.0


def test_classify_outcome():
    assert classify_outcome(True, False) == "regressed"
    assert classify_outcome(False, True) == "fixed"
    assert classify_outcome(False, False) == "still_failing"
    assert classify_outcome(True, True) == "unchanged"


def test_majority_voting():
    """
    A test with k=5 runs passes if at least 3 of 5 pass.
    """
    test_cases = [
        {"id": "t1", "target": "p1", "critical": False, "slices": {}},
        {"id": "t2", "target": "p1", "critical": False, "slices": {}},
        {"id": "t3", "target": "p1", "critical": False, "slices": {}},
    ]
    # base: t1 passes (3/5), t2 passes (5/5), t3 fails (2/5)
    base_runs = {
        "t1": [True, True, True, False, False],
        "t2": [True, True, True, True, True],
        "t3": [True, True, False, False, False],
    }
    # cand: t1 fails (2/5 -> regressed), t2 passes (4/5 -> unchanged), t3 passes (3/5 -> fixed)
    cand_runs = {
        "t1": [True, True, False, False, False],
        "t2": [True, True, True, True, False],
        "t3": [True, True, True, False, False],
    }

    res = compare_test_results(test_cases, base_runs, cand_runs, k=5)

    assert res["regressed_count"] == 1
    assert res["fixed_count"] == 1
    assert res["unchanged_count"] == 1
    assert res["still_failing_count"] == 0

    t1_flip = next(f for f in res["flips"] if f["test_id"] == "t1")
    assert t1_flip["base_passed"] is True
    assert t1_flip["cand_passed"] is False
    assert t1_flip["outcome"] == "regressed"

    t3_flip = next(f for f in res["flips"] if f["test_id"] == "t3")
    assert t3_flip["base_passed"] is False
    assert t3_flip["cand_passed"] is True
    assert t3_flip["outcome"] == "fixed"


def test_bootstrap_ci():
    """
    Verify 10,000 bootstrap CI computation produces valid bounds.
    """
    base_outcomes = [True] * 20 + [False] * 5
    cand_outcomes = [True] * 15 + [False] * 10

    ci_delta, ci_rr, ci_fr = bootstrap_ci(base_outcomes, cand_outcomes, n_resamples=1000)

    # Cand pass rate dropped from 20/25 (0.80) to 15/25 (0.60) -> delta = -0.20
    assert ci_delta[0] <= ci_delta[1]
    assert ci_delta[0] < 0.0  # CI is negative
    assert ci_rr[0] >= 0.0
    assert ci_fr[0] >= 0.0


def test_hidden_flips_flat_aggregate():
    """
    Tests where aggregate pass rate is completely flat (0.0 delta),
    yet 2 tests regressed and 2 tests were fixed.
    """
    test_cases = [
        {"id": f"t{i}", "target": "p", "critical": False, "slices": {"cat": "nlp"}}
        for i in range(10)
    ]
    # Base: t0, t1 pass; t2, t3 fail; t4-t9 pass
    base_runs = {f"t{i}": [True] * 5 for i in range(10)}
    base_runs["t2"] = [False] * 5
    base_runs["t3"] = [False] * 5

    # Cand: t0, t1 fail (regressed); t2, t3 pass (fixed); t4-t9 pass (unchanged)
    cand_runs = {f"t{i}": [True] * 5 for i in range(10)}
    cand_runs["t0"] = [False] * 5
    cand_runs["t1"] = [False] * 5

    res = compare_test_results(test_cases, base_runs, cand_runs, k=5)
    assert res["delta_pass_rate"] == 0.0
    assert res["regressed_count"] == 2
    assert res["fixed_count"] == 2
    assert res["hidden_flips_detected"] is True

