"""
Decision Rules and Multi-Testing Statistical Verification Engine.
Implements:
1. Exact McNemar Test with Critical Test Gating (baseline)
2. Non-Inferiority Margin Test (95% Bootstrap CI lower bound >= -margin)
3. Holm-Bonferroni Family-Wise Error Rate Step-Down Multi-Slice Correction
4. Discordant Odds Ratio Effect Size (with Haldane-Anscombe continuity correction)
"""

import math
from typing import Dict, Any, List, Optional, Tuple
from scipy.stats import binomtest
import numpy as np


def evaluate_mcnemar_rule(
    b: int,
    c: int,
    p_value: float,
    critical_regressed: bool,
    alpha: float = 0.05,
) -> Dict[str, Any]:
    """
    Rule 1: Exact McNemar test plus critical test regressions.
    """
    if critical_regressed:
        return {
            "rule": "mcnemar_exact",
            "verdict": "BLOCK",
            "passed": False,
            "reason": "A critical test suffered a regression.",
            "metrics": {"b": b, "c": c, "p_value": p_value, "alpha": alpha, "critical_regressed": True},
        }

    is_significant = (p_value < alpha) and (b > c)
    if is_significant:
        verdict = "BLOCK"
        reason = f"Statistically significant regression: regressed (b={b}) > fixed (c={c}) with p={p_value:.4f} < {alpha}."
    else:
        verdict = "PROMOTE"
        reason = f"Passed exact McNemar gate: p={p_value:.4f} >= {alpha} or b <= c."

    return {
        "rule": "mcnemar_exact",
        "verdict": verdict,
        "passed": verdict == "PROMOTE",
        "reason": reason,
        "metrics": {"b": b, "c": c, "p_value": p_value, "alpha": alpha, "critical_regressed": False},
    }


def evaluate_non_inferiority_rule(
    delta_pass_rate: float,
    ci_95: Tuple[float, float],
    critical_regressed: bool,
    margin: float = 0.05,
) -> Dict[str, Any]:
    """
    Rule 2: Non-inferiority margin test.
    BLOCK if the lower bound of the 95% bootstrap CI of pass-rate delta is below -margin.
    """
    if critical_regressed:
        return {
            "rule": "non_inferiority",
            "verdict": "BLOCK",
            "passed": False,
            "reason": "Critical test regression detected.",
            "ci_lower": ci_95[0],
            "margin": margin,
            "metrics": {"margin": margin, "delta": delta_pass_rate, "ci_lower": ci_95[0], "ci_upper": ci_95[1]},
        }

    ci_lower = ci_95[0]
    # Block if lower bound is below -margin (e.g. -0.06 < -0.05)
    if ci_lower < -margin:
        verdict = "BLOCK"
        reason = (
            f"Non-inferiority margin violated: 95% CI lower bound ({ci_lower:+.2%}) "
            f"falls below allowable degradation threshold (-{margin:.2%})."
        )
    else:
        verdict = "PROMOTE"
        reason = (
            f"Non-inferiority satisfied: 95% CI lower bound ({ci_lower:+.2%}) "
            f"is above allowable margin (-{margin:.2%})."
        )

    return {
        "rule": "non_inferiority",
        "verdict": verdict,
        "passed": verdict == "PROMOTE",
        "reason": reason,
        "ci_lower": ci_lower,
        "margin": margin,
        "metrics": {"margin": margin, "delta": delta_pass_rate, "ci_lower": ci_lower, "ci_upper": ci_95[1]},
    }


def evaluate_holm_bonferroni_rule(
    slices: List[Dict[str, Any]],
    critical_regressed: bool,
    alpha: float = 0.05,
) -> Dict[str, Any]:
    """
    Rule 3: Holm-Bonferroni step-down family-wise error rate correction across test slices.
    """
    if critical_regressed:
        return {
            "rule": "holm_bonferroni",
            "verdict": "BLOCK",
            "passed": False,
            "reason": "Critical test regression detected.",
            "metrics": {"slices_evaluated": len(slices), "alpha": alpha, "regressed_slices": []},
        }

    if not slices:
        return {
            "rule": "holm_bonferroni",
            "verdict": "PROMOTE",
            "passed": True,
            "reason": "No test slices defined.",
            "metrics": {"slices_evaluated": 0, "alpha": alpha, "regressed_slices": []},
        }

    # Extract p-value and delta for each slice
    slice_records = []
    for s in slices:
        s_name = s.get("slice", s.get("name", "unknown"))
        b_s = s.get("b", 0)
        c_s = s.get("c", 0)
        p_s = s.get("p_value")
        if p_s is None:
            if b_s + c_s > 0:
                p_s = float(binomtest(min(b_s, c_s), b_s + c_s, 0.5).pvalue)
            else:
                p_s = 1.0

        delta_s = s.get("delta", 0.0)
        slice_records.append({
            "name": s_name,
            "b": b_s,
            "c": c_s,
            "p_value": p_s,
            "delta": delta_s,
        })

    # Sort ascending by p-value
    slice_records.sort(key=lambda x: x["p_value"])
    m = len(slice_records)

    regressed_slices = []
    for rank_idx, s_info in enumerate(slice_records):
        i = rank_idx + 1  # 1-indexed
        threshold = alpha / (m - i + 1)
        s_info["holm_threshold"] = threshold

        # If p-value <= threshold and delta is negative (or b > c)
        if s_info["p_value"] <= threshold and (s_info["delta"] < 0 or s_info["b"] > s_info["c"]):
            s_info["statistically_significant"] = True
            regressed_slices.append(s_info)
        else:
            s_info["statistically_significant"] = False

    if regressed_slices:
        worst = regressed_slices[0]
        verdict = "BLOCK"
        reason = (
            f"Statistically significant slice regression in '{worst['name']}': "
            f"p={worst['p_value']:.4f} <= adjusted alpha={worst['holm_threshold']:.4f} "
            f"(b={worst['b']}, c={worst['c']}, delta={worst['delta']:+.2%})."
        )
    else:
        verdict = "PROMOTE"
        reason = f"Passed Holm-Bonferroni correction across all {m} slices at FWER alpha={alpha}."

    return {
        "rule": "holm_bonferroni",
        "verdict": verdict,
        "passed": verdict == "PROMOTE",
        "reason": reason,
        "metrics": {
            "slices_evaluated": m,
            "alpha": alpha,
            "regressed_slices": [r["name"] for r in regressed_slices],
            "slice_details": slice_records,
        },
    }


def evaluate_odds_ratio_rule(
    b: int,
    c: int,
    critical_regressed: bool,
    threshold: float = 1.0,
) -> Dict[str, Any]:
    """
    Rule 4: Discordant odds ratio effect size with Haldane-Anscombe continuity correction.
    OR = (b + 0.5) / (c + 0.5).
    SE(ln OR) = sqrt(1/(b+0.5) + 1/(c+0.5)).
    CI = exp(ln OR +- 1.96 * SE).
    """
    # Haldane-Anscombe continuity correction
    b_adj = b + 0.5
    c_adj = c + 0.5
    or_val = b_adj / c_adj
    ln_or = math.log(or_val)
    se_ln_or = math.sqrt((1.0 / b_adj) + (1.0 / c_adj))

    ci_lower = math.exp(ln_or - 1.96 * se_ln_or)
    ci_upper = math.exp(ln_or + 1.96 * se_ln_or)

    if critical_regressed:
        return {
            "rule": "odds_ratio",
            "verdict": "BLOCK",
            "passed": False,
            "reason": "Critical test regression detected.",
            "odds_ratio": round(or_val, 3),
            "ci_lower": round(ci_lower, 3),
            "ci_upper": round(ci_upper, 3),
            "metrics": {
                "b": b,
                "c": c,
                "odds_ratio": round(or_val, 3),
                "ci_lower": round(ci_lower, 3),
                "ci_upper": round(ci_upper, 3),
                "se_ln_or": round(se_ln_or, 3),
            },
        }

    # If b > c and either CI lower bound > threshold or substantial discordant count with c=0
    is_effect_regression = (b > c) and (ci_lower > threshold or (b >= 4 and c == 0))

    if is_effect_regression:
        verdict = "BLOCK"
        reason = (
            f"Discordant odds ratio effect size demonstrates regression: OR={or_val:.2f} "
            f"(95% CI [{ci_lower:.2f}, {ci_upper:.2f}], b={b}, c={c})."
        )
    else:
        verdict = "PROMOTE"
        reason = (
            f"Discordant odds ratio within acceptable bound: OR={or_val:.2f} "
            f"(95% CI [{ci_lower:.2f}, {ci_upper:.2f}])."
        )

    return {
        "rule": "odds_ratio",
        "verdict": verdict,
        "passed": verdict == "PROMOTE",
        "reason": reason,
        "odds_ratio": round(or_val, 3),
        "ci_lower": round(ci_lower, 3),
        "ci_upper": round(ci_upper, 3),
        "metrics": {
            "odds_ratio": round(or_val, 3),
            "ci_lower": round(ci_lower, 3),
            "ci_upper": round(ci_upper, 3),
            "se_ln_or": round(se_ln_or, 3),
            "b": b,
            "c": c,
        },
    }


def evaluate_all_decision_rules(
    b_or_comp: Any,
    c: Optional[int] = None,
    p_value: Optional[float] = None,
    delta_pass_rate: Optional[float] = None,
    ci_95: Optional[Tuple[float, float]] = None,
    critical_regressed: Optional[bool] = None,
    slices: Optional[List[Dict[str, Any]]] = None,
    policy: Optional[Dict[str, Any]] = None,
    **kwargs,
) -> Dict[str, Any]:
    """
    Evaluates all 4 decision rules simultaneously.
    Can accept either a single comparison dictionary or individual positional arguments.
    """
    if isinstance(b_or_comp, dict):
        comp = b_or_comp
        b = comp.get("regressed_count", comp.get("b", 0))
        c = comp.get("fixed_count", comp.get("c", 0))
        p_value = comp.get("p_value", 1.0)
        delta_pass_rate = comp.get("delta_pass_rate", comp.get("delta", 0.0))
        ci_95 = comp.get("ci_delta", (0.0, 0.0))
        policy_crit_ids = set(kwargs.get("policy_critical_ids", []))
        critical_regressed = any(
            (f.get("critical", False) or f.get("test_id") in policy_crit_ids)
            and (f.get("outcome") == "regressed" or str(f.get("status", "")).lower() == "regressed")
            for f in comp.get("flips", [])
        )
        slices = comp.get("slices", [])
        pol = policy or kwargs
    else:
        b = int(b_or_comp)
        c = int(c if c is not None else 0)
        p_value = float(p_value if p_value is not None else 1.0)
        delta_pass_rate = float(delta_pass_rate if delta_pass_rate is not None else 0.0)
        ci_95 = ci_95 or (0.0, 0.0)
        critical_regressed = bool(critical_regressed)
        pol = policy or kwargs
    active_rule = pol.get("decision_rule", "mcnemar_exact")
    alpha = float(pol.get("alpha", 0.05))
    margin = float(pol.get("non_inferiority_margin", 0.05))
    hb_alpha = float(pol.get("holm_bonferroni_alpha", alpha))
    or_threshold = float(pol.get("odds_ratio_threshold", 1.0))

    r_mcnemar = evaluate_mcnemar_rule(b, c, p_value, critical_regressed, alpha=alpha)
    r_non_inf = evaluate_non_inferiority_rule(delta_pass_rate, ci_95, critical_regressed, margin=margin)
    r_holm = evaluate_holm_bonferroni_rule(slices or [], critical_regressed, alpha=hb_alpha)
    r_or = evaluate_odds_ratio_rule(b, c, critical_regressed, threshold=or_threshold)

    rules_map = {
        "mcnemar_exact": r_mcnemar,
        "non_inferiority": r_non_inf,
        "holm_bonferroni": r_holm,
        "odds_ratio": r_or,
    }

    governing_result = rules_map.get(active_rule, r_mcnemar)

    return {
        "governing_rule": active_rule,
        "governing_verdict": governing_result["verdict"],
        "governing_reason": governing_result["reason"],
        "mcnemar_exact": r_mcnemar,
        "non_inferiority": r_non_inf,
        "holm_bonferroni": r_holm,
        "odds_ratio": r_or,
        "rules": {
            "mcnemar_exact": r_mcnemar,
            "non_inferiority": r_non_inf,
            "holm_bonferroni": r_holm,
            "odds_ratio": r_or,
        },
    }
