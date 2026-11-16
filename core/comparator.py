import numpy as np
from scipy.stats import binomtest


def classify_outcome(base_pass, cand_pass):
    if base_pass and not cand_pass:
        return "regressed"
    if not base_pass and cand_pass:
        return "fixed"
    if not base_pass and not cand_pass:
        return "still_failing"
    return "unchanged"


def mcnemar_test(b, c):
    """
    Exact two-sided McNemar test on regressed (b) vs fixed (c).
    Uses scipy.stats.binomtest(min(b, c), b + c, 0.5).
    b=12, c=3 yields p=0.0352.
    """
    total = b + c
    if total == 0:
        return 1.0

    k = min(b, c)
    res = binomtest(k, total, 0.5)
    return round(float(res.pvalue), 4)


def bootstrap_ci(base_outcomes, cand_outcomes, n_resamples=10000, seed=42):
    """
    95% bootstrap CI (10,000 resamples) for:
    - delta pass rate
    - regression rate (pass -> fail)
    - fix rate (fail -> pass)
    """
    n = len(base_outcomes)
    if n == 0:
        return (0.0, 0.0), (0.0, 0.0), (0.0, 0.0)

    base_arr = np.array(base_outcomes, dtype=bool)
    cand_arr = np.array(cand_outcomes, dtype=bool)

    rng = np.random.default_rng(seed)
    indices = rng.integers(0, n, size=(n_resamples, n))

    boot_base = base_arr[indices]
    boot_cand = cand_arr[indices]

    # Delta pass rate = mean(cand) - mean(base)
    boot_deltas = np.mean(boot_cand, axis=1) - np.mean(boot_base, axis=1)

    # Regression rate = (base & ~cand) / n
    boot_rr = np.mean(boot_base & ~boot_cand, axis=1)

    # Fix rate = (~base & cand) / n
    boot_fr = np.mean(~boot_base & boot_cand, axis=1)

    def get_ci(arr):
        low = float(np.percentile(arr, 2.5))
        high = float(np.percentile(arr, 97.5))
        return round(low, 4), round(high, 4)

    return get_ci(boot_deltas), get_ci(boot_rr), get_ci(boot_fr)


# Aliases for consistent naming across evaluation and attribution modules
compute_bootstrap_ci = bootstrap_ci
mcnemar_exact_test = mcnemar_test


def wilson_score_interval(successes: int, total: int, confidence: float = 0.95):
    """
    Wilson 95% score interval for proportions.
    Used for precision, recall, and classification metrics over binary outcomes.
    """
    if total == 0:
        return 0.0, 0.0
    z = 1.959963984540054  # 95% two-sided normal quantile
    p = successes / total
    denom = 1.0 + (z**2) / total
    center = (p + (z**2) / (2 * total)) / denom
    margin = (z / denom) * (((p * (1.0 - p) / total) + (z**2) / (4 * (total**2))) ** 0.5)
    low = max(0.0, center - margin)
    high = min(1.0, center + margin)
    return round(float(low), 3), round(float(high), 3)


def compare_test_results(test_cases, base_runs_map, cand_runs_map, k=5):
    """
    Compare baseline and candidate test scores.
    base_runs_map: {test_id: [bool, bool, ...]}
    cand_runs_map: {test_id: [bool, bool, ...]}
    """
    flips = []
    base_majority_passes = []
    cand_majority_passes = []
    consistencies = []

    b_count = 0  # regressed
    c_count = 0  # fixed
    unchanged_count = 0
    still_failing_count = 0

    slices_data = {}

    for tc in test_cases:
        tid = tc["id"]
        b_runs = base_runs_map.get(tid, [False] * k)
        c_runs = cand_runs_map.get(tid, [False] * k)

        # Majority vote: passes if at least 3 of 5 (or majority) pass
        threshold = (k // 2) + 1
        b_pass = sum(1 for p in b_runs if p) >= threshold
        c_pass = sum(1 for p in c_runs if p) >= threshold

        base_majority_passes.append(b_pass)
        cand_majority_passes.append(c_pass)

        # Consistency: fraction of candidate runs agreeing with majority outcome
        c_maj_count = sum(1 for p in c_runs if p) if c_pass else sum(1 for p in c_runs if not p)
        consistencies.append(c_maj_count / k)

        outcome = classify_outcome(b_pass, c_pass)
        if outcome == "regressed":
            b_count += 1
        elif outcome == "fixed":
            c_count += 1
        elif outcome == "still_failing":
            still_failing_count += 1
        else:
            unchanged_count += 1

        flip_rec = {
            "test_id": tid,
            "target": tc.get("target", ""),
            "slices": tc.get("slices", {}),
            "critical": bool(tc.get("critical", False)),
            "base_passed": b_pass,
            "cand_passed": c_pass,
            "outcome": outcome,
            "base_runs_passed": sum(1 for p in b_runs if p),
            "cand_runs_passed": sum(1 for p in c_runs if p),
        }
        flips.append(flip_rec)

        # Slices aggregation
        for s_k, s_v in tc.get("slices", {}).items():
            s_name = f"{s_k}:{s_v}"
            if s_name not in slices_data:
                slices_data[s_name] = {"base_pass": 0, "cand_pass": 0, "total": 0}
            slices_data[s_name]["total"] += 1
            if b_pass:
                slices_data[s_name]["base_pass"] += 1
            if c_pass:
                slices_data[s_name]["cand_pass"] += 1

    n_tests = len(test_cases) or 1
    base_rate = sum(1 for p in base_majority_passes if p) / n_tests
    cand_rate = sum(1 for p in cand_majority_passes if p) / n_tests
    delta_rate = round(cand_rate - base_rate, 4)

    p_val = mcnemar_test(b_count, c_count)
    ci_delta, ci_rr, ci_fr = bootstrap_ci(base_majority_passes, cand_majority_passes, n_resamples=10000)

    # Slice deltas
    slices_report = []
    for s_name, s_d in sorted(slices_data.items()):
        tot = s_d["total"] or 1
        b_s = s_d["base_pass"] / tot
        c_s = s_d["cand_pass"] / tot
        slices_report.append({
            "slice": s_name,
            "n_tests": tot,
            "base_rate": round(b_s, 4),
            "cand_rate": round(c_s, 4),
            "delta": round(c_s - b_s, 4),
        })

    # Case where aggregate pass rate stays flat but tests flipped
    hidden_flips_detected = (delta_rate >= -0.02) and (b_count > 0)

    return {
        "n_tests": n_tests,
        "base_pass_rate": round(base_rate, 4),
        "cand_pass_rate": round(cand_rate, 4),
        "delta_pass_rate": delta_rate,
        "ci_delta": ci_delta,
        "ci_regression_rate": ci_rr,
        "ci_fix_rate": ci_fr,
        "regressed_count": b_count,
        "fixed_count": c_count,
        "unchanged_count": unchanged_count,
        "still_failing_count": still_failing_count,
        "regression_rate": round(b_count / n_tests, 4),
        "fix_rate": round(c_count / n_tests, 4),
        "consistency": round(float(np.mean(consistencies)), 4) if consistencies else 1.0,
        "p_value": p_val,
        "flips": flips,
        "slices": slices_report,
        "hidden_flips_detected": hidden_flips_detected,
    }

