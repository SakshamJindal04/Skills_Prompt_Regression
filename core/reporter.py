from datetime import datetime, timezone


def generate_markdown_report(
    comparison,
    candidate_id=None,
    baseline_id=None,
    verdict="BLOCK",
    policy_version="1.0.0",
    base_model=None,
    cand_model=None,
    base_digest=None,
    cand_digest=None,
):
    d_pct = comparison.get("delta_pass_rate", 0.0) * 100
    p_val = comparison.get("p_value", 1.0)
    ci_d = comparison.get("ci_delta", (0.0, 0.0))
    ci_rr = comparison.get("ci_regression_rate", (0.0, 0.0))
    b_rate = comparison.get("base_pass_rate", 0.0) * 100
    c_rate = comparison.get("cand_pass_rate", 0.0) * 100
    rr = comparison.get("regression_rate", 0.0) * 100
    fr = comparison.get("fix_rate", 0.0) * 100
    consistency = comparison.get("consistency", 1.0) * 100

    report_title = "Cross-Model Regression Gate Report" if (base_model or cand_model) else "Regression Test Gate Report"

    md = f"""# {report_title}

- **Verdict**: **{verdict}**
- **Date**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}
- **Policy Version**: `{policy_version}`
"""
    if base_model or cand_model:
        b_dig = f" (`{base_digest[:12]}`)" if base_digest and base_digest != "unknown" else ""
        c_dig = f" (`{cand_digest[:12]}`)" if cand_digest and cand_digest != "unknown" else ""
        md += f"- **Baseline Model**: `{base_model or 'qwen2.5:3b'}`{b_dig}\n"
        md += f"- **Candidate Model**: `{cand_model or 'qwen2.5:3b'}`{c_dig}\n"

    if baseline_id or candidate_id:
        md += f"- **Baseline Artifact**: `{baseline_id}`\n"
        md += f"- **Candidate Artifact**: `{candidate_id}`\n"

    md += f"""
## Summary Statistics

| Metric | Value |
| :--- | :--- |
| **Baseline Pass Rate** | {b_rate:.1f}% |
| **Candidate Pass Rate** | {c_rate:.1f}% |
| **Delta Pass Rate** | {d_pct:+.1f}% (95% CI [{ci_d[0]*100:+.1f}%, {ci_d[1]*100:+.1f}%]) |
| **Regressed Tests (b)** | {comparison.get('regressed_count', 0)} (Rate: {rr:.1f}%, 95% CI [{ci_rr[0]*100:+.1f}%, {ci_rr[1]*100:+.1f}%]) |
| **Fixed Tests (c)** | {comparison.get('fixed_count', 0)} (Rate: {fr:.1f}%) |
| **Unchanged Tests** | {comparison.get('unchanged_count', 0)} |
| **Still Failing Tests** | {comparison.get('still_failing_count', 0)} |
| **McNemar p-value** | {p_val:.4f} |
| **Consistency** | {consistency:.1f}% |

"""

    if comparison.get("hidden_flips_detected"):
        md += """
> **Note**: Overall aggregate pass rate remained flat/positive, but per-test regressions were detected. This confirms why per-test paired tracking is required.
"""

    md += """
## Regressed Tests (Pass -> Fail)

"""
    regressed_flips = [
        f for f in comparison.get("flips", [])
        if f.get("outcome") == "regressed" or str(f.get("status", "")).lower() == "regressed"
    ]
    if not regressed_flips:
        md += "None. No tests regressed.\n\n"
    else:
        md += "| Test ID | Target | Critical | Baseline Passed Runs | Candidate Passed Runs |\n"
        md += "| :--- | :--- | :--- | :--- | :--- |\n"
        for f in regressed_flips:
            crit = "YES" if f.get("critical") else "no"
            b_runs = f.get("base_runs_passed", "-")
            c_runs = f.get("cand_runs_passed", "-")
            md += f"| `{f.get('test_id')}` | `{f.get('target', '')}` | {crit} | {b_runs}/5 | {c_runs}/5 |\n"
        md += "\n"

    md += """
## Secondary Slice View

| Slice Tag | Tests | Baseline Rate | Candidate Rate | Delta |
| :--- | :--- | :--- | :--- | :--- |\n"""
    for s in comparison.get("slices", []):
        md += f"| `{s['slice']}` | {s['n_tests']} | {s['base_rate']*100:.1f}% | {s['cand_rate']*100:.1f}% | {s['delta']*100:+.1f}% |\n"

    return md

    return md
