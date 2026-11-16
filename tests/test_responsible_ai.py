import pytest
from core.responsible_ai import compute_responsible_ai_metrics, wilson_score_interval


def test_wilson_score_interval():
    low, high = wilson_score_interval(successes=95, total=100)
    assert 0.85 <= low <= 0.95
    assert 0.95 <= high <= 1.0


def test_responsible_ai_metrics():
    test_cases = [
        # Safety / Adversarial
        {
            "id": "tc_safe_01",
            "family": "safety",
            "slices": {"adversarial": True, "category": "jailbreak_override"},
        },
        # Privacy / PII
        {
            "id": "tc_priv_01",
            "family": "privacy",
            "slices": {"contains_pii": True, "category": "pii_redaction"},
        },
        # Fairness Counterfactual Pair 1
        {
            "id": "tc_fair_a",
            "family": "fairness",
            "slices": {"pair_id": "pair_01", "slice_group": "group_a", "pair_type": "names"},
        },
        {
            "id": "tc_fair_b",
            "family": "fairness",
            "slices": {"pair_id": "pair_01", "slice_group": "group_b", "pair_type": "names"},
        },
    ]

    scores = {
        "tc_safe_01": [True, True, True],   # Refused safely (pass)
        "tc_priv_01": [True, True, True],   # Redacted PII (pass)
        "tc_fair_a": [True, True, True],    # Group A: 100% pass
        "tc_fair_b": [True, True, False],   # Group B: 66.7% pass
    }

    metrics = compute_responsible_ai_metrics(test_cases, scores)

    # Assert metrics
    assert metrics["refusal_rate"] == 1.0
    assert metrics["injection_success_rate"] == 0.0
    assert metrics["pii_leakage_rate"] == 0.0
    assert metrics["overall_fairness_gap"] > 0.0  # Detected parity gap between A and B
    assert len(metrics["fairness_pairs"]) == 1
    assert "safety" in metrics["family_summary"]
    assert "privacy" in metrics["family_summary"]
    assert "fairness" in metrics["family_summary"]

