"""
Statistical Power and Sample Size Analysis Module.
Calculates minimum detectable regression rate, power curves,
and actionable sample-size guidance for exact McNemar testing and majority voting.
"""

import math
from typing import Dict, Any, List
from scipy.stats import binomtest


def compute_mcnemar_power(
    n: int,
    k: int = 5,
    alpha: float = 0.05,
) -> Dict[str, Any]:
    """
    Computes statistical power and minimum detectable regression for given test count N and repetitions k.
    """
    # Minimum discordant regressions b required for p <= alpha assuming c = 0
    # 2 * 0.5^b <= alpha => b >= 1 - log2(alpha)
    b_min = 1
    while True:
        p_val = float(binomtest(0, b_min, 0.5).pvalue)
        if p_val <= alpha:
            break
        b_min += 1

    min_detectable_rate = b_min / max(1, n)

    # Power for hypothetical regression rates: 5%, 10%, 15%, 20%, 30%
    hypothetical_drops = [0.05, 0.10, 0.15, 0.20, 0.30]
    power_table = []

    for drop in hypothetical_drops:
        expected_flips = int(round(drop * n))
        if expected_flips < b_min:
            powered = False
            p_val = float(binomtest(0, max(1, expected_flips), 0.5).pvalue) if expected_flips > 0 else 1.0
        else:
            powered = True
            p_val = float(binomtest(0, expected_flips, 0.5).pvalue)

        power_table.append({
            "regression_drop": f"{drop * 100:.0f}%",
            "expected_regressed_tests": expected_flips,
            "statistically_detectable": powered,
            "p_value_at_zero_fixes": round(p_val, 4),
        })

    # Variance reduction from majority-k voting
    # Filter non-deterministic pass rate variance: sigma_k = sigma_1 / sqrt(k)
    variance_reduction_pct = (1.0 - (1.0 / math.sqrt(k))) * 100.0

    # Actionable guidance
    if n < 30:
        advice = (
            f"LOW POWER WARNING: With N={n}, the test suite requires at least {b_min} discordant test failures "
            f"({min_detectable_rate * 100:.1f}% drop) to achieve statistical significance at alpha={alpha}. "
            "Subtle or localized regressions will fail to reach significance under aggregate McNemar testing alone. "
            "Recommendation: expand test suite to N >= 60 or tag critical tests for deterministic zero-tolerance blocking."
        )
    elif n < 80:
        advice = (
            f"MODERATE POWER: With N={n}, minimum detectable regression is {b_min} tests "
            f"({min_detectable_rate * 100:.1f}% drop). Suitable for catching moderate to severe prompt degradations."
        )
    else:
        advice = (
            f"HIGH POWER: With N={n}, minimum detectable regression is {b_min} tests "
            f"({min_detectable_rate * 100:.1f}% drop). The suite has high statistical sensitivity to detect "
            "subtle regressions without relying solely on critical override rules."
        )

    return {
        "n": n,
        "k": k,
        "alpha": alpha,
        "b_min_for_significance": b_min,
        "min_detectable_b": b_min,
        "min_detectable_regression_rate": min_detectable_rate,
        "min_detectable_rate": min_detectable_rate,
        "variance_reduction_from_k_pct": round(variance_reduction_pct, 1),
        "power_table": power_table,
        "advice": advice,
        "recommendation": advice,
    }


def format_power_report(n: int, k: int, alpha: float = 0.05) -> str:
    """Formats human-readable power report for CLI and documentation."""
    res = compute_mcnemar_power(n=n, k=k, alpha=alpha)

    lines = [
        "==================================================================",
        "  REGGUARD STATISTICAL POWER & SAMPLE-SIZE ADVISORY",
        "==================================================================",
        f"  Total Test Cases (N)    : {res['n']}",
        f"  Repetitions per Test (k): {res['k']} (majority voting)",
        f"  Significance Level (alpha): {res['alpha']}",
        f"  Minimum Discordant (b)  : {res['b_min_for_significance']} regressed tests (with c=0)",
        f"  Minimum Detectable Drop : {res['min_detectable_regression_rate'] * 100:.2f}%",
        f"  Noise Variance Reduction: {res['variance_reduction_from_k_pct']:.1f}% reduction via k={res['k']}",
        "------------------------------------------------------------------",
        "  Hypothetical Regression Detection Profile:",
        "    Drop (%) | Expected Regressed (b) | Detectable? | p-value",
    ]

    for p in res["power_table"]:
        det_str = "YES" if p["statistically_detectable"] else "NO (Underpowered)"
        lines.append(
            f"    {p['regression_drop']:>8} | {p['expected_regressed_tests']:>22} | {det_str:<15} | {p['p_value_at_zero_fixes']:.4f}"
        )

    lines.extend([
        "------------------------------------------------------------------",
        "  Sample-Size Recommendation:",
        f"  {res['advice']}",
        "==================================================================",
    ])

    return "\n".join(lines)
