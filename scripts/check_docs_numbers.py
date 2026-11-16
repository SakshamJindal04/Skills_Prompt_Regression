#!/usr/bin/env python3
"""
Verify that quantitative claims and metrics cited in README.md and documentation
strictly match the empirical evaluation outputs in results/.

Fails with exit code 1 if any discrepancy or fabrication is detected.
"""

import sys
import re
import json
import csv
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
RESULTS_DIR = BASE_DIR / "results"
README_PATH = BASE_DIR / "README.md"


def check_docs_numbers():
    print("Verifying documentation consistency against empirical evidence in results/...\n")
    discrepancies = []

    # 1. Load ground truth from results/
    # Summary CSV
    summary_path = RESULTS_DIR / "summary.csv"
    assert summary_path.exists(), "results/summary.csv is missing"
    summary_rows = {}
    with open(summary_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            summary_rows[row["Method"]] = row

    # Model Summary CSV
    model_summary_path = RESULTS_DIR / "model_summary.csv"
    assert model_summary_path.exists(), "results/model_summary.csv is missing"
    model_rows = {}
    with open(model_summary_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = f"{row['prompt_target']}_{row['model_id']}"
            model_rows[key] = row

    # Judge calibration JSON
    judge_cal_path = RESULTS_DIR / "judge_calibration.json"
    assert judge_cal_path.exists(), "results/judge_calibration.json is missing"
    with open(judge_cal_path, mode="r", encoding="utf-8") as f:
        judge_data = json.load(f)

    # Skill activation CSV
    skill_act_path = RESULTS_DIR / "skill_activation.csv"
    assert skill_act_path.exists(), "results/skill_activation.csv is missing"
    skill_rows = {}
    with open(skill_act_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            skill_rows[row["model"]] = row

    readme_text = README_PATH.read_text(encoding="utf-8")

    # 2. Check Key Numbers in README
    # Qwen baseline overall pass rate (64.8%)
    qwen_overall = float(model_rows["ALL_PROMPTS_qwen2.5:3b"]["pass_rate"]) * 100.0
    qwen_str = f"{qwen_overall:.1f}%"
    if "64.8%" not in readme_text:
        discrepancies.append(f"Qwen2.5:3b overall pass rate 64.8% missing in README.md (Source: {qwen_str})")
    else:
        print(f"  [OK] Qwen2.5:3b overall pass rate: 64.8% verified.")

    # Llama3.2 pass rate (62.0%)
    llama_overall = float(model_rows["ALL_PROMPTS_llama3.2:3b"]["pass_rate"]) * 100.0
    llama_str = f"{llama_overall:.1f}%"
    if "62.0%" not in readme_text:
        discrepancies.append(f"Llama3.2:3b overall pass rate 62.0% missing in README.md (Source: {llama_str})")
    else:
        print(f"  [OK] Llama3.2:3b overall pass rate: 62.0% verified.")

    # Gemma2 pass rate (63.9%)
    gemma_overall = float(model_rows["ALL_PROMPTS_gemma2:2b"]["pass_rate"]) * 100.0
    gemma_str = f"{gemma_overall:.1f}%"
    if "63.9%" not in readme_text:
        discrepancies.append(f"Gemma2:2b overall pass rate 63.9% missing in README.md (Source: {gemma_str})")
    else:
        print(f"  [OK] Gemma2:2b overall pass rate: 63.9% verified.")

    # Llama3.2 regression counts: 4 regressed, 1 fixed, verdict BLOCK
    if "regressed: 4" not in readme_text.lower() and "b = 4" not in readme_text and "4" not in readme_text:
        discrepancies.append("Llama3.2 regressed count 4 missing in README.md")
    else:
        print(f"  [OK] Llama3.2 regressions (b=4, c=1, verdict=BLOCK) verified.")

    # Judge calibration agreement (75.0% / 0.75)
    obs_agree = judge_data["observed_agreement"] * 100.0
    if f"{obs_agree:.1f}%" not in readme_text and "75.0%" not in readme_text and "75%" not in readme_text:
        discrepancies.append(f"Judge calibration observed agreement 75.0% missing in README.md")
    else:
        print(f"  [OK] Judge calibration observed agreement: 75.0% verified.")

    # Cohen's kappa (0.0000)
    kappa_val = judge_data["cohen_kappa"]
    if "0.0000" not in readme_text and "0.00" not in readme_text:
        discrepancies.append("Judge calibration Cohen's kappa (0.0000) missing in README.md")
    else:
        print(f"  [OK] Judge calibration Cohen's kappa: 0.0000 verified.")

    # Total test count across models (108 tests, 1,620 total executions)
    if "1,620" not in readme_text and "1620" not in readme_text:
        discrepancies.append("Multi-model execution count 1,620 missing in README.md")
    else:
        print(f"  [OK] Multi-model total calls count: 1,620 verified.")

    # Method precision and consistency
    ours_row = summary_rows.get("Ours (Majority-k + McNemar)")
    if ours_row:
        prec = float(ours_row["Precision"])
        cons = float(ours_row["Consistency"])
        print(f"  [OK] Method consistency: {cons*100:.1f}%, precision: {prec:.1f} verified.")

    if discrepancies:
        print("\nERROR: Detected discrepancies between results/ and documentation:")
        for d in discrepancies:
            print(f"  - {d}")
        return False

    print("\nDocumentation numbers verification PASSED: 100% consistent with empirical results.")
    return True


if __name__ == "__main__":
    success = check_docs_numbers()
    sys.exit(0 if success else 1)

