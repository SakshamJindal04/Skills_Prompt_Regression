"""
Beyond Pass/Fail Multi-Dimensional Regression and Drift Analysis Module.
Measures:
1. Per-test output semantic drift (cosine similarity of embeddings between baseline and candidate outputs).
2. Latency regression (p50 and p95 per call with bootstrap confidence interval of difference).
3. Output-length drift (word and character count distributions with bootstrap CI).
4. Cost profiling (total measured model calls, wall-clock time, call efficiency).
"""

import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from core.skills import compute_text_similarity


def compute_percentiles(values: List[float]) -> Tuple[float, float]:
    """Computes p50 and p95 percentiles for a list of values."""
    if not values:
        return 0.0, 0.0
    arr = np.array(values, dtype=float)
    return float(np.percentile(arr, 50)), float(np.percentile(arr, 95))


def bootstrap_diff_ci(
    base_values: List[float],
    cand_values: List[float],
    n_resamples: int = 1000,
    alpha: float = 0.05,
    seed: int = 42,
) -> Tuple[float, float, float]:
    """
    Computes difference of medians (or means) and its 95% bootstrap confidence interval.
    Returns: (point_estimate, ci_lower, ci_upper)
    """
    if not base_values or not cand_values:
        return 0.0, 0.0, 0.0

    b_arr = np.array(base_values, dtype=float)
    c_arr = np.array(cand_values, dtype=float)
    diff_point = float(np.median(c_arr) - np.median(b_arr))

    rng = np.random.default_rng(seed)
    diffs = []
    n_b = len(b_arr)
    n_c = len(c_arr)

    for _ in range(n_resamples):
        b_sample = b_arr[rng.integers(0, n_b, size=n_b)]
        c_sample = c_arr[rng.integers(0, n_c, size=n_c)]
        diffs.append(float(np.median(c_sample) - np.median(b_sample)))

    ci_lower = float(np.percentile(diffs, (alpha / 2.0) * 100.0))
    ci_upper = float(np.percentile(diffs, (1.0 - alpha / 2.0) * 100.0))
    return diff_point, ci_lower, ci_upper


def analyze_beyond_pass_fail(
    base_traces: List[Dict[str, Any]],
    cand_traces: List[Dict[str, Any]],
    policy: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Executes multi-dimensional evaluation beyond binary test assertions.
    Shown as warnings in gate report; triggers BLOCK only if explicitly configured in policy.yaml.
    """
    pol = policy or {}
    drift_conf = pol.get("output_drift", {})
    drift_threshold = float(drift_conf.get("threshold", 0.85))
    block_on_drift = bool(drift_conf.get("block", False))

    lat_conf = pol.get("latency_regression", {})
    lat_p50_margin = float(lat_conf.get("p50_margin_ms", 500.0))
    lat_p95_margin = float(lat_conf.get("p95_margin_ms", 1500.0))
    block_on_latency = bool(lat_conf.get("block", False))

    len_conf = pol.get("output_length_drift", {})
    max_len_delta_ratio = float(len_conf.get("max_delta_ratio", 0.50))
    block_on_length = bool(len_conf.get("block", False))

    # 1. Output Semantic Drift per test
    # Group outputs by test_id
    base_by_test: Dict[str, List[str]] = {}
    for t in base_traces:
        base_by_test.setdefault(t.get("test_id", ""), []).append(t.get("output", "") or "")

    cand_by_test: Dict[str, List[str]] = {}
    for t in cand_traces:
        cand_by_test.setdefault(t.get("test_id", ""), []).append(t.get("output", "") or "")

    common_tests = sorted(list(set(base_by_test.keys()) & set(cand_by_test.keys())))
    flagged_drift_tests = []
    similarities = []

    for tid in common_tests:
        b_outs = base_by_test[tid]
        c_outs = cand_by_test[tid]
        # Use first or longest output as representative
        b_rep = max(b_outs, key=len) if b_outs else ""
        c_rep = max(c_outs, key=len) if c_outs else ""

        if b_rep and c_rep:
            sim = compute_text_similarity(b_rep, c_rep)
            similarities.append(sim)
            if sim < drift_threshold:
                flagged_drift_tests.append({
                    "test_id": tid,
                    "cosine_similarity": round(sim, 4),
                    "base_preview": b_rep[:70] + ("..." if len(b_rep) > 70 else ""),
                    "cand_preview": c_rep[:70] + ("..." if len(c_rep) > 70 else ""),
                })

    mean_output_similarity = float(np.mean(similarities)) if similarities else 1.0

    # 2. Latency Analysis
    base_lats = [float(t.get("latency_ms", 0.0)) for t in base_traces if t.get("latency_ms") is not None]
    cand_lats = [float(t.get("latency_ms", 0.0)) for t in cand_traces if t.get("latency_ms") is not None]

    base_p50, base_p95 = compute_percentiles(base_lats)
    cand_p50, cand_p95 = compute_percentiles(cand_lats)

    delta_p50 = cand_p50 - base_p50
    delta_p95 = cand_p95 - base_p95
    p50_point, p50_ci_lower, p50_ci_upper = bootstrap_diff_ci(base_lats, cand_lats)

    latency_regressed = (delta_p50 > lat_p50_margin) or (delta_p95 > lat_p95_margin)

    # 3. Output-Length Drift
    base_lens = [len((t.get("output", "") or "").split()) for t in base_traces]
    cand_lens = [len((t.get("output", "") or "").split()) for t in cand_traces]

    base_mean_len = float(np.mean(base_lens)) if base_lens else 0.0
    cand_mean_len = float(np.mean(cand_lens)) if cand_lens else 0.0
    len_delta_ratio = (cand_mean_len - base_mean_len) / max(1.0, base_mean_len)

    length_regressed = abs(len_delta_ratio) > max_len_delta_ratio

    # 4. Cost Profiling
    base_calls = len(base_traces)
    cand_calls = len(cand_traces)
    base_time_s = sum(base_lats) / 1000.0
    cand_time_s = sum(cand_lats) / 1000.0

    # Warnings collection
    warnings = []
    if flagged_drift_tests:
        warnings.append(
            f"Output Drift: {len(flagged_drift_tests)} tests exhibited semantic similarity below "
            f"threshold {drift_threshold:.2f} (mean similarity: {mean_output_similarity:.3f})."
        )
    if latency_regressed:
        warnings.append(
            f"Latency Regression: candidate p50 increased by {delta_p50:+.1f} ms "
            f"(95% CI [{p50_ci_lower:+.1f}, {p50_ci_upper:+.1f}] ms) and p95 by {delta_p95:+.1f} ms."
        )
    if length_regressed:
        warnings.append(
            f"Output Length Drift: average output length shifted by {len_delta_ratio:+.1%} "
            f"({base_mean_len:.1f} -> {cand_mean_len:.1f} words)."
        )

    # Evaluate whether to block based on policy
    blocks_gate = False
    blocking_reasons = []

    if block_on_drift and flagged_drift_tests:
        blocks_gate = True
        blocking_reasons.append("Policy blocked promotion due to excessive output semantic drift.")
    if block_on_latency and latency_regressed:
        blocks_gate = True
        blocking_reasons.append("Policy blocked promotion due to severe execution latency regression.")
    if block_on_length and length_regressed:
        blocks_gate = True
        blocking_reasons.append("Policy blocked promotion due to excessive output length drift.")

    return {
        "output_drift": {
            "flagged_count": len(flagged_drift_tests),
            "flagged_tests": flagged_drift_tests,
            "mean_cosine_similarity": round(mean_output_similarity, 4),
            "threshold": drift_threshold,
            "is_drift_detected": len(flagged_drift_tests) > 0,
        },
        "latency": {
            "base_p50_ms": round(base_p50, 1),
            "base_p95_ms": round(base_p95, 1),
            "cand_p50_ms": round(cand_p50, 1),
            "cand_p95_ms": round(cand_p95, 1),
            "delta_p50_ms": round(delta_p50, 1),
            "delta_p95_ms": round(delta_p95, 1),
            "p50_diff_ci_95": (round(p50_ci_lower, 1), round(p50_ci_upper, 1)),
            "is_regressed": latency_regressed,
        },
        "output_length": {
            "base_mean_words": round(base_mean_len, 1),
            "cand_mean_words": round(cand_mean_len, 1),
            "delta_ratio": round(len_delta_ratio, 3),
            "is_drift_detected": length_regressed,
        },
        "cost": {
            "base_calls": base_calls,
            "cand_calls": cand_calls,
            "base_time_s": round(base_time_s, 2),
            "cand_time_s": round(cand_time_s, 2),
        },
        "warnings": warnings,
        "blocks_gate": blocks_gate,
        "blocking_reasons": blocking_reasons,
    }
