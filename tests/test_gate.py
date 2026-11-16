"""
Unit tests for core/gate.py.
Verifies gate policy:
- Significant regression (b > c and p < alpha) blocks.
- Fixed > regressed (c > b) must NOT block (PROMOTE).
- Critical test regression blocks unconditionally.
- Promotion updates baseline registry.
"""

import pytest
from core.gate import evaluate_gate
from core.models import Artifact, BaselineRegistry
from core.db import get_session
from core.versioner import get_current_baseline


def test_gate_fixed_greater_than_regressed_promotes():
    """
    When candidate improves (fixed=12 > regressed=3), p_value is 0.0352 < 0.05.
    The gate must NOT block because fixed > regressed is an improvement.
    Verdict must be PROMOTE.
    """
    comparison = {
        "regressed_count": 3,
        "fixed_count": 12,
        "unchanged_count": 10,
        "still_failing_count": 2,
        "delta_pass_rate": 0.3333,
        "p_value": 0.0352,
        "flips": [
            {"test_id": "t1", "critical": False, "outcome": "regressed"},
            {"test_id": "t2", "critical": False, "outcome": "fixed"},
        ],
    }

    verdict, report = evaluate_gate(comparison, alpha=0.05)
    assert verdict == "PROMOTE"
    assert "Passed gate policy" in report or "PROMOTE" in report


def test_gate_statistically_significant_regression_blocks():
    """
    When b=12 (regressed) > c=3 (fixed) and p=0.0352 < 0.05,
    the gate must BLOCK.
    """
    comparison = {
        "regressed_count": 12,
        "fixed_count": 3,
        "unchanged_count": 10,
        "still_failing_count": 2,
        "delta_pass_rate": -0.3333,
        "p_value": 0.0352,
        "flips": [
            {"test_id": f"t_reg_{i}", "critical": False, "outcome": "regressed"}
            for i in range(12)
        ] + [
            {"test_id": f"t_fix_{i}", "critical": False, "outcome": "fixed"}
            for i in range(3)
        ],
    }

    verdict, report = evaluate_gate(comparison, alpha=0.05)
    assert verdict == "BLOCK"
    assert "Statistically significant regression" in report or "BLOCK" in report


def test_gate_critical_test_regression_blocks():
    """
    Even if overall fixed > regressed and p is not significant,
    if a test marked critical regressed, the gate must BLOCK.
    """
    comparison = {
        "regressed_count": 1,
        "fixed_count": 5,
        "unchanged_count": 10,
        "still_failing_count": 0,
        "delta_pass_rate": 0.25,
        "p_value": 0.2188,
        "flips": [
            {"test_id": "crit_test", "critical": True, "outcome": "regressed"},
            {"test_id": "normal_fix", "critical": False, "outcome": "fixed"},
        ],
    }

    verdict, report = evaluate_gate(comparison, alpha=0.05)
    assert verdict == "BLOCK"
    assert "critical" in report.lower()


def test_gate_promotion_sets_baseline():
    """
    When a candidate is promoted, it should be registered as the new baseline.
    """
    # Create dummy candidate artifact in DB
    with get_session() as session:
        art = Artifact(
            hash="test_candidate_hash_12345",
            type="prompt",
            name="candidate_prompt",
            path="prompts/test.md",
        )
        session.add(art)
        session.flush()
        cand_id = art.id

    comparison = {
        "regressed_count": 0,
        "fixed_count": 4,
        "unchanged_count": 15,
        "still_failing_count": 1,
        "delta_pass_rate": 0.20,
        "p_value": 0.125,
        "flips": [
            {"test_id": "t1", "critical": False, "outcome": "fixed"},
        ],
    }

    verdict, report = evaluate_gate(comparison, alpha=0.05, candidate_id=cand_id)
    assert verdict == "PROMOTE"

    current = get_current_baseline()
    assert current is not None
    assert current["id"] == cand_id

