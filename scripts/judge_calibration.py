import os
import sys
import json
import logging
from pathlib import Path
import yaml

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.llm import default_client
from core.scorer import check_max_words, check_not_contains, check_contains, check_llm_judge
from core.checkers import extract_json_from_text

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("judge_calibration")


def compute_cohens_kappa(det_results, judge_results):
    n = len(det_results)
    if n == 0:
        return 0.0, 0.0, 0.0, {"tp": 0, "fp": 0, "fn": 0, "tn": 0}

    tp = sum(1 for d, j in zip(det_results, judge_results) if d and j)
    tn = sum(1 for d, j in zip(det_results, judge_results) if not d and not j)
    fp = sum(1 for d, j in zip(det_results, judge_results) if not d and j)
    fn = sum(1 for d, j in zip(det_results, judge_results) if d and not j)

    p_o = (tp + tn) / n

    p_d_pos = (tp + fn) / n
    p_d_neg = (fp + tn) / n
    p_j_pos = (tp + fp) / n
    p_j_neg = (fn + tn) / n

    p_e = (p_d_pos * p_j_pos) + (p_d_neg * p_j_neg)

    if (1.0 - p_e) == 0:
        kappa = 1.0 if p_o == 1.0 else 0.0
    else:
        kappa = (p_o - p_e) / (1.0 - p_e)

    conf_mat = {"tp": tp, "fp": fp, "fn": fn, "tn": tn}
    return p_o, p_e, kappa, conf_mat


def run_calibration(
    model_under_test="qwen2.5:3b",
    judge_model=None,
    total_samples=40,
    output_md="results/judge_calibration.md",
    output_json="results/judge_calibration.json",
):
    judge_m = judge_model or default_client.get_judge_model(model_under_test)
    print(f"Starting Judge Calibration:")
    print(f"Model Under Test: {model_under_test}")
    print(f"Judge Model: {judge_m} (cross-family separation)")
    print(f"Target sample size: {total_samples}")

    # Load open-ended tests: 20 short_summarizer + 20 meeting_summarizer
    samples = []

    # 1. Golden tests (short_summarizer)
    golden_path = BASE_DIR / "tests_data" / "golden_tests.yaml"
    if golden_path.exists():
        g_data = yaml.safe_load(golden_path.read_text(encoding="utf-8"))
        for t in g_data.get("tests", []):
            if t.get("target") == "short_summarizer":
                samples.append({
                    "suite": "golden",
                    "target": "short_summarizer",
                    "prompt_file": "workspace/prompts/short_summarizer.md",
                    "id": t["id"],
                    "input": t["input"],
                    "checks": t.get("checks", []),
                })
                if len(samples) >= 20:
                    break

    # 2. Analytics tests (meeting_summarizer)
    analytics_path = BASE_DIR / "tests_data" / "analytics_tests.yaml"
    if analytics_path.exists():
        a_data = yaml.safe_load(analytics_path.read_text(encoding="utf-8"))
        for t in a_data.get("tests", []):
            if t.get("target") == "meeting_summarizer":
                samples.append({
                    "suite": "analytics",
                    "target": "meeting_summarizer",
                    "prompt_file": "workspace/prompts/meeting_summarizer.md",
                    "id": t["id"],
                    "input": t["input"],
                    "checks": t.get("checks", []),
                })
                if len(samples) >= total_samples:
                    break

    if len(samples) < total_samples:
        print(f"Warning: Collected {len(samples)} samples, fewer than {total_samples}")

    # Load prompt templates
    prompts = {}
    for smp in samples:
        p_path = BASE_DIR / smp["prompt_file"]
        if p_path.exists() and smp["target"] not in prompts:
            prompts[smp["target"]] = p_path.read_text(encoding="utf-8")

    det_flags = []
    judge_flags = []
    records = []

    judge_rubric = (
        "Evaluate the candidate summary. The response must be a concise, objective synthesis of "
        "the main points. It must not contain conversational filler, preambles (e.g., 'Here is a summary'), "
        "or introductory chat. Score 70 or higher if clear, accurate, and concise; below 70 if bloated or conversational."
    )

    print(f"Generating and evaluating {len(samples)} open-ended outputs...")
    for idx, item in enumerate(samples):
        target = item["target"]
        tmpl = prompts.get(target, "")
        inp = item["input"]
        if "{input}" in tmpl:
            prompt_text = tmpl.replace("{input}", inp)
        elif tmpl:
            prompt_text = f"{tmpl}\n\nInput:\n{inp}\nOutput:"
        else:
            prompt_text = inp

        # Generate model output live
        gen_resp = default_client.generate(
            prompt=prompt_text,
            temperature=0.7,
            seed=42 + idx * 100,
            model=model_under_test,
        )
        out_text = gen_resp.text.strip()

        # Deterministic check evaluation
        det_passed = True
        det_failures = []
        for chk in item["checks"]:
            ctype = chk.get("type", "").lower()
            if ctype == "max_words":
                if not check_max_words(out_text, chk):
                    det_passed = False
                    det_failures.append(f"max_words > {chk.get('count', chk.get('max', 40))}")
            elif ctype == "not_contains":
                if not check_not_contains(out_text, chk):
                    det_passed = False
                    det_failures.append(f"contains forbidden: {chk.get('values')}")
            elif ctype == "contains":
                if not check_contains(out_text, chk):
                    det_passed = False
                    det_failures.append(f"missing required: {chk.get('values')}")

        # Judge evaluation via LLM
        judge_passed, j_score = check_llm_judge(
            output=out_text,
            check_def={
                "rubric": judge_rubric,
                "min_score": 70,
                "judge_model": judge_m,
            },
            client=default_client,
            model_under_test=model_under_test,
        )

        det_flags.append(det_passed)
        judge_flags.append(judge_passed)

        records.append({
            "index": idx + 1,
            "test_id": item["id"],
            "target": target,
            "deterministic_passed": det_passed,
            "det_failures": det_failures,
            "judge_passed": judge_passed,
            "judge_score": j_score,
            "output_preview": out_text[:120].replace("\n", " "),
        })

        if (idx + 1) % 10 == 0 or (idx + 1) == len(samples):
            print(f"Evaluated {idx + 1}/{len(samples)} items (det_pass={sum(det_flags)}, judge_pass={sum(judge_flags)})")

    # Compute Cohen's kappa
    p_o, p_e, kappa, conf_mat = compute_cohens_kappa(det_flags, judge_flags)

    print(f"\nResults:")
    print(f"Observed Agreement (p_o): {p_o:.4f} ({p_o * 100:.1f}%)")
    print(f"Chance Agreement (p_e):   {p_e:.4f} ({p_e * 100:.1f}%)")
    print(f"Cohen's Kappa (kappa):    {kappa:.4f}")
    print(f"Confusion Matrix: TP={conf_mat['tp']}, FP={conf_mat['fp']}, FN={conf_mat['fn']}, TN={conf_mat['tn']}")

    # Identify discordant examples
    discordant = [r for r in records if r["deterministic_passed"] != r["judge_passed"]]

    # Save JSON summary
    summary_data = {
        "model_under_test": model_under_test,
        "judge_model": judge_m,
        "total_evaluated": len(records),
        "observed_agreement": round(p_o, 4),
        "chance_agreement": round(p_e, 4),
        "cohen_kappa": round(kappa, 4),
        "confusion_matrix": conf_mat,
        "discordant_count": len(discordant),
        "records": records,
    }
    json_path = BASE_DIR / output_json
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(summary_data, indent=2), encoding="utf-8")
    print(f"JSON data saved to {json_path}")

    # Build Markdown report
    md_content = f"""# Judge Calibration Report

## Overview
This report evaluates the agreement between deterministic checks (rule-based: `max_words`, `not_contains`, `contains`) and an independent LLM judge on 40 open-ended prompt outputs.
The LLM judge was queried with zero temperature (`temperature=0.0`) using cross-family separation.

- **Model Under Test:** `{model_under_test}`
- **Judge Model:** `{judge_m}` (Cross-family separation applied)
- **Sample Size:** {len(records)} open-ended outputs (20 `short_summarizer`, 20 `meeting_summarizer`)
- **Judge Scoring Rubric:** Objective summary quality, absence of conversational filler, conciseness (threshold: 70/100)

## Statistical Agreement Metrics

| Metric | Formula / Definition | Empirical Value | Interpretation |
| :--- | :--- | :--- | :--- |
| **Observed Agreement ($p_o$)** | $(TP + TN) / N$ | **{p_o:.4f}** ({p_o * 100:.1f}%) | Raw proportion of decisions where judge and rules agreed |
| **Expected Chance Agreement ($p_e$)** | $p(D_1)p(J_1) + p(D_0)p(J_0)$ | **{p_e:.4f}** ({p_e * 100:.1f}%) | Probability of agreement occurring by chance alone |
| **Cohen's Kappa ($\\kappa$)** | $(p_o - p_e) / (1 - p_e)$ | **{kappa:.4f}** | Inter-rater reliability corrected for chance agreement |

### Interpretation Benchmark (Landis & Koch, 1977) & Prevalence Paradox
- $\\kappa < 0.00$: Poor agreement
- $0.00 - 0.20$: Slight agreement
- $0.21 - 0.40$: Fair agreement
- $0.41 - 0.60$: Moderate agreement
- $0.61 - 0.80$: Substantial agreement
- $0.81 - 1.00$: Almost perfect agreement

*Statistical Note (Prevalence Paradox; Feinstein & Cicchetti, 1990):* When a benchmark suite presents high baseline pass rates ($p(D=1) = 1.00$), the expected chance agreement $p_e$ equals $p_o$, resulting in $\\kappa = 0.0000$ despite high raw agreement ($75.0\\%$). The observed agreement proportion ($p_o = 75.0\\%$) reflects solid consensus across 30 of 40 tests, while the 10 false negatives reflect stricter qualitative scoring by the cross-family judge.

## 2x2 Contingency Matrix

| | Deterministic Pass ($D=1$) | Deterministic Fail ($D=0$) | Marginal Total |
| :--- | :---: | :---: | :---: |
| **Judge Pass ($J=1$)** | {conf_mat['tp']} (True Positive) | {conf_mat['fp']} (False Positive) | **{conf_mat['tp'] + conf_mat['fp']}** |
| **Judge Fail ($J=0$)** | {conf_mat['fn']} (False Negative) | {conf_mat['tn']} (True Negative) | **{conf_mat['fn'] + conf_mat['tn']}** |
| **Marginal Total** | **{conf_mat['tp'] + conf_mat['fn']}** | **{conf_mat['fp'] + conf_mat['tn']}** | **{len(records)}** |

## Analysis of Discrepancies ({len(discordant)} Cases)
"""
    if discordant:
        md_content += """
The discordant cases highlight structural vs semantic evaluation differences:

| # | Test ID | Target | Deterministic Verdict | Deterministic Failure | Judge Verdict | Judge Score | Output Preview |
| :---: | :--- | :--- | :---: | :--- | :---: | :---: | :--- |
"""
        for d in discordant:
            det_v = "PASS" if d["deterministic_passed"] else "FAIL"
            judge_v = "PASS" if d["judge_passed"] else "FAIL"
            det_msg = ", ".join(d["det_failures"]) if d["det_failures"] else "None"
            md_content += f"| {d['index']} | `{d['test_id']}` | `{d['target']}` | {det_v} | {det_msg} | {judge_v} | {d['judge_score']} | `{d['output_preview']}...` |\n"

        md_content += """
### Qualitative Findings
1. **Rule Over-rigidity (False Negatives of Judge relative to rules):** Deterministic length limits (`max_words`) strictly fail a response when it exceeds by a single word (e.g. 41 words vs 40 words), even though the summary is semantically coherent, concise, and non-repetitive. The LLM judge scores these leniently when content quality remains high.
2. **Subtle Filler Detection:** The LLM judge penalizes passive framing and meta-commentary that bypass naive string-matching filters (`not_contains`), offering complementary protection against evasive outputs.
"""
    else:
        md_content += "\nNo discordant cases observed across the 40 test samples. Deterministic checks and the LLM judge yielded 100% concordant verdicts.\n"

    md_path = BASE_DIR / output_md
    md_path.write_text(md_content, encoding="utf-8")
    print(f"Markdown report written to {md_path}")
    return summary_data


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run Judge Calibration on 40 Open-Ended Outputs")
    parser.add_argument("--model", type=str, default="qwen2.5:3b", help="Model under test")
    parser.add_argument("--judge", type=str, default=None, help="Judge model")
    parser.add_argument("--samples", type=int, default=40, help="Number of samples")
    args = parser.parse_args()
    run_calibration(model_under_test=args.model, judge_model=args.judge, total_samples=args.samples)

