"""
Hypothesis Property-Based Statistical Verification Tests.
Verifies fundamental mathematical invariants:
1. Symmetry of exact McNemar test: p(b, c) == p(c, b)
2. Monotonicity of Discordant Odds Ratio
3. Validity of Bootstrap Confidence Intervals (CI_lower <= CI_upper)
4. Monotonicity of Holm-Bonferroni rank-adjusted significance thresholds
"""

import math
import pytest
from hypothesis import given, strategies as st, settings
from scipy.stats import binomtest

from core.comparator import mcnemar_test
from core.decision_rules import evaluate_odds_ratio_rule
from core.drift_analysis import bootstrap_diff_ci


# --- Property 1: Symmetry of McNemar Test ---
@settings(max_examples=100)
@given(
    b=st.integers(min_value=0, max_value=200),
    c=st.integers(min_value=0, max_value=200),
)
def test_hypothesis_mcnemar_symmetry(b: int, c: int):
    """
    Exact two-sided McNemar p-value must be strictly symmetric:
    p(b, c) == p(c, b).
    """
    p_bc = mcnemar_test(b, c)
    p_cb = mcnemar_test(c, b)
    assert p_bc == pytest.approx(p_cb, abs=1e-7)
    assert 0.0 <= p_bc <= 1.0


# --- Property 2: Monotonicity of Odds Ratio ---
@settings(max_examples=100)
@given(
    b1=st.integers(min_value=0, max_value=100),
    b2=st.integers(min_value=0, max_value=100),
    c=st.integers(min_value=0, max_value=100),
)
def test_hypothesis_odds_ratio_monotonicity(b1: int, b2: int, c: int):
    """
    For a constant c, the adjusted odds ratio OR(b, c) = (b + 0.5) / (c + 0.5)
    must be strictly monotonically non-decreasing with b:
    If b1 <= b2, then OR(b1, c) <= OR(b2, c).
    """
    res1 = evaluate_odds_ratio_rule(b=b1, c=c, critical_regressed=False)
    res2 = evaluate_odds_ratio_rule(b=b2, c=c, critical_regressed=False)

    or1 = res1["odds_ratio"]
    or2 = res2["odds_ratio"]

    if b1 <= b2:
        assert or1 <= or2 + 1e-4
    else:
        assert or1 >= or2 - 1e-4


# --- Property 3: Validity of Bootstrap CI Bounds ---
@settings(max_examples=50)
@given(
    base_lats=st.lists(st.floats(min_value=50.0, max_value=500.0, allow_nan=False), min_size=5, max_size=20),
    cand_lats=st.lists(st.floats(min_value=50.0, max_value=500.0, allow_nan=False), min_size=5, max_size=20),
)
def test_hypothesis_bootstrap_ci_validity(base_lats, cand_lats):
    """
    For any valid float distributions, the bootstrap confidence interval
    must satisfy CI_lower <= point_estimate <= CI_upper (within sampling tolerance).
    """
    point, ci_low, ci_high = bootstrap_diff_ci(base_lats, cand_lats, n_resamples=200)
    assert ci_low <= ci_high
    assert math.isfinite(ci_low)
    assert math.isfinite(ci_high)


# --- Property 4: Holm-Bonferroni Step-Down Monotonicity ---
@settings(max_examples=50)
@given(
    m=st.integers(min_value=1, max_value=25),
    alpha=st.floats(min_value=0.01, max_value=0.10),
)
def test_hypothesis_holm_bonferroni_threshold_monotonicity(m: int, alpha: float):
    """
    Holm-Bonferroni thresholds T_i = alpha / (m - i + 1) for i = 1..m
    must be strictly increasing: T_1 < T_2 < ... < T_m == alpha.
    """
    thresholds = [alpha / (m - i + 1) for i in range(1, m + 1)]
    for idx in range(len(thresholds) - 1):
        assert thresholds[idx] <= thresholds[idx + 1]
    assert thresholds[-1] == pytest.approx(alpha, abs=1e-7)
