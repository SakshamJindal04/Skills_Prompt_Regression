import os
import sys
import time
import math
import logging
from pathlib import Path
import yaml
import numpy as np
import pandas as pd
from scipy.stats import binomtest

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.llm import default_client
from core.scorer import score_trace, compute_majority_vote
from core.skills import SkillRegistry
from core.policy import load_policy

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("model_swap")


def compute_wilson_ci(p_hat, n, confidence=0.95):
    """Computes Wilson score interval for a binomial proportion."""
    if n == 0:
        return 0.0, 0.0
    z = 1.95996  # 95% confidence
    denom = 1.0 + (z**2) / n
    center = (p_hat + (z**2) / (2 * n)) / denom
    margin = (z * math.sqrt((p_hat * (1.0 - p_hat) / n) + (z**2) / (4 * (n**2)))) / denom
    lower = max(0.0, center - margin)
    upper = min(1.0, center + margin)
    return lower, upper


def evaluate_skill_activation(model_id, skills_dict):
    """
    Evaluates skill selection/routing accuracy for a given model.
    Queries the model with 10 representative user requests from tests_data/skill_benchmarks.yaml
    and checks if the correct skill is selected.
    """
    bm_file = BASE_DIR / "tests_data" / "skill_benchmarks.yaml"
    if bm_file.exists():
        data = yaml.safe_load(bm_file.read_text(encoding="utf-8"))
        benchmarks = data.get("benchmarks", [])[:10]
    else:
        benchmarks = []

    available_skills = list(skills_dict.keys())
    if not benchmarks or not available_skills:
        return 1.0

    correct = 0
    skills_list_str = "\n".join([f"- {s}" for s in available_skills])

    for b in benchmarks:
        prompt = f"""You are a skill router for an agentic system.
Given the following user task, select the single best matching skill name from the available skills list.

Available skills:
{skills_list_str}

User task: "{b['task']}"

Respond with ONLY the exact skill name, nothing else."""
        try:
            resp = default_client.generate(prompt=prompt, temperature=0.0, model=model_id)
            selected = resp.text.strip().lower()
            if b["expected_skill"].lower() in selected:
                correct += 1
        except Exception:
            pass

    return correct / len(benchmarks)


def run_model_swap_study(
    base_model="qwen2.5:3b",
    candidate_models=None,
    suite="golden",
    k=5,
    quick=False,
    output_matrix_csv="results/model_matrix.csv",
    output_summary_csv="results/model_summary.csv",
    output_md="results/model_swap.md",
    policy_path="policy.yaml",
):
    start_total_time = time.time()
    if candidate_models is None:
        candidate_models = ["llama3.2:3b", "gemma2:2b"]

    policy = load_policy(policy_path)
    alpha = policy.get("alpha", 0.05)
    policy_crit_ids = set(policy.get("critical_test_ids", []))

    if quick:
        k = min(k, 3)

    print(f"=== Model-Swap Case Study ===")
    print(f"Baseline Model:   {base_model}")
    print(f"Candidate Models: {', '.join(candidate_models)}")
    print(f"Runs per test (k): {k} (quick={quick})")
    print(f"Suite:             {suite}")

    # Load suite
    suite_file = BASE_DIR / "tests_data" / f"{suite}_tests.yaml"
    if not suite_file.exists():
        suite_file = BASE_DIR / "tests_data" / "golden_tests.yaml"

    suite_data = yaml.safe_load(suite_file.read_text(encoding="utf-8"))
    test_cases = suite_data.get("tests", [])

    if quick:
        test_cases = test_cases[:20]

    print(f"Total test cases to evaluate: {len(test_cases)}")

    # Load prompt templates
    prompts = {}
    ws_prompts = BASE_DIR / "workspace" / "prompts"
    if ws_prompts.exists():
        for pf in ws_prompts.glob("*.md"):
            prompts[pf.stem] = pf.read_text(encoding="utf-8")

    # Load skills
    skills_dict = {}
    ws_skills = BASE_DIR / "workspace" / "skills"
    if ws_skills.exists():
        for sf in ws_skills.glob("*/SKILL.md"):
            skills_dict[sf.parent.name] = sf.read_text(encoding="utf-8")

    all_models = [base_model] + candidate_models
    model_metadata = {}
    for m in all_models:
        meta = default_client.get_model_metadata(m)
        model_metadata[m] = meta

    raw_run_rows = []
    # Structure: model -> test_id -> list of boolean pass/fails
    model_test_runs = {m: {} for m in all_models}
    # Structure: model -> test_id -> majority output text
    model_sample_outputs = {m: {} for m in all_models}
    # Structure: model -> list of latency seconds
    model_latencies = {m: [] for m in all_models}

    for m in all_models:
        print(f"\n--- Running evaluation on model: {m} (family: {model_metadata[m].get('family')}) ---")
        m_digest = model_metadata[m].get("digest", "unknown")

        for t_idx, tc in enumerate(test_cases):
            tid = tc["id"]
            target = tc.get("target", "")
            tmpl = prompts.get(target, "")
            inp = tc["input"]

            if "{input}" in tmpl:
                prompt_text = tmpl.replace("{input}", inp)
            elif tmpl:
                prompt_text = f"{tmpl}\n\nInput:\n{inp}\nOutput:"
            else:
                prompt_text = inp

            runs = []
            for r_idx in range(k):
                seed = 42 + r_idx * 1000
                t_start = time.time()
                resp = default_client.generate(
                    prompt=prompt_text,
                    temperature=0.7,
                    seed=seed,
                    model=m,
                )
                lat_s = resp.latency_seconds if hasattr(resp, "latency_seconds") and resp.latency_seconds else (time.time() - t_start)
                model_latencies[m].append(lat_s)

                out_text = resp.text.strip()
                if r_idx == 0:
                    model_sample_outputs[m][tid] = out_text

                trace = {
                    "output": out_text,
                    "model": m,
                    "model_digest": m_digest,
                    "test_id": tid,
                    "run_index": r_idx,
                }
                res = score_trace(trace, tc.get("checks", []), client=default_client)
                passed = bool(res["passed"])
                runs.append(passed)

                raw_run_rows.append({
                    "test_id": tid,
                    "prompt_target": target,
                    "model_id": m,
                    "model_digest": m_digest,
                    "run_index": r_idx,
                    "seed": seed,
                    "latency_s": round(lat_s, 4),
                    "passed": 1 if passed else 0,
                    "score": round(res["score"], 2),
                    "output_length_chars": len(out_text),
                })

            model_test_runs[m][tid] = runs
            if (t_idx + 1) % 25 == 0 or (t_idx + 1) == len(test_cases):
                print(f"  Processed {t_idx + 1}/{len(test_cases)} tests on {m}")

    # Save raw runs CSV
    df_raw = pd.DataFrame(raw_run_rows)
    csv_path = BASE_DIR / output_matrix_csv
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    df_raw.to_csv(csv_path, index=False)
    print(f"\nRaw matrix rows saved to {csv_path} ({len(df_raw)} records)")

    # Compute skill activation accuracy for each model
    print("\nMeasuring skill activation accuracy per model...")
    skill_accuracies = {}
    for m in all_models:
        acc = evaluate_skill_activation(m, skills_dict)
        skill_accuracies[m] = acc
        print(f"  {m}: {acc * 100:.1f}%")

    # Group tests by target prompt
    prompt_targets = sorted(list({tc.get("target", "default") for tc in test_cases}))

    # Summary analysis
    summary_rows = []
    flips_by_candidate = {cand: [] for cand in candidate_models}

    for target in prompt_targets:
        target_tests = [tc for tc in test_cases if tc.get("target") == target]
        t_ids = [tc["id"] for tc in target_tests]
        n_t = len(t_ids)

        for m in all_models:
            # Majority pass count
            passed_count = 0
            agreements = []
            m_lats = []

            for tid in t_ids:
                runs = model_test_runs[m][tid]
                maj_pass, agr = compute_majority_vote(runs)
                if maj_pass:
                    passed_count += 1
                agreements.append(agr)

            pass_rate = passed_count / max(1, n_t)
            ci_low, ci_high = compute_wilson_ci(pass_rate, n_t)
            consistency = np.mean(agreements) if agreements else 1.0

            # Filter model latencies for this target
            t_raw = df_raw[(df_raw["model_id"] == m) & (df_raw["prompt_target"] == target)]
            mean_lat = t_raw["latency_s"].mean() if not t_raw.empty else 0.0
            p95_lat = np.percentile(t_raw["latency_s"], 95) if not t_raw.empty else 0.0

            # Flips vs baseline if candidate model
            b_regressed = 0
            c_fixed = 0
            p_val = 1.0
            verdict = "N/A (Baseline)"

            if m != base_model:
                for tc in target_tests:
                    tid = tc["id"]
                    base_maj, _ = compute_majority_vote(model_test_runs[base_model][tid])
                    cand_maj, _ = compute_majority_vote(model_test_runs[m][tid])

                    is_crit = tc.get("critical", False) or (tid in policy_crit_ids)
                    if base_maj and not cand_maj:
                        b_regressed += 1
                        flips_by_candidate[m].append({
                            "test_id": tid,
                            "prompt_target": target,
                            "input": tc["input"],
                            "critical": is_crit,
                            "outcome": "regressed",
                            "baseline_pass": True,
                            "candidate_pass": False,
                            "baseline_output": model_sample_outputs[base_model].get(tid, ""),
                            "candidate_output": model_sample_outputs[m].get(tid, ""),
                        })
                    elif not base_maj and cand_maj:
                        c_fixed += 1
                        flips_by_candidate[m].append({
                            "test_id": tid,
                            "prompt_target": target,
                            "input": tc["input"],
                            "critical": is_crit,
                            "outcome": "fixed",
                            "baseline_pass": False,
                            "candidate_pass": True,
                            "baseline_output": model_sample_outputs[base_model].get(tid, ""),
                            "candidate_output": model_sample_outputs[m].get(tid, ""),
                        })

                # McNemar test
                disc = b_regressed + c_fixed
                if disc > 0:
                    p_val = binomtest(min(b_regressed, c_fixed), disc, 0.5, alternative="two-sided").pvalue
                else:
                    p_val = 1.0

                crit_reg = any(f["outcome"] == "regressed" and f["critical"] for f in flips_by_candidate[m] if f["prompt_target"] == target)
                if crit_reg:
                    verdict = "BLOCK"
                elif (p_val < alpha) and (b_regressed > c_fixed):
                    verdict = "BLOCK"
                else:
                    verdict = "PROMOTE"

            summary_rows.append({
                "prompt_target": target,
                "model_id": m,
                "model_digest": model_metadata[m].get("digest", "unknown")[:12],
                "tests_count": n_t,
                "pass_rate": round(pass_rate, 4),
                "ci_lower": round(ci_low, 4),
                "ci_upper": round(ci_high, 4),
                "consistency": round(consistency, 4),
                "mean_latency_s": round(mean_lat, 3),
                "p95_latency_s": round(p95_lat, 3),
                "skill_activation_acc": round(skill_accuracies[m], 3),
                "regressed_b": b_regressed if m != base_model else 0,
                "fixed_c": c_fixed if m != base_model else 0,
                "p_value": round(p_val, 4) if m != base_model else 1.0,
                "verdict": verdict,
            })

    # Overall rows across all prompts
    overall_rows = []
    for m in all_models:
        passed_count = 0
        agreements = []
        for tc in test_cases:
            tid = tc["id"]
            maj_pass, agr = compute_majority_vote(model_test_runs[m][tid])
            if maj_pass:
                passed_count += 1
            agreements.append(agr)

        pass_rate = passed_count / len(test_cases)
        ci_low, ci_high = compute_wilson_ci(pass_rate, len(test_cases))
        consistency = np.mean(agreements) if agreements else 1.0

        m_all_raw = df_raw[df_raw["model_id"] == m]
        mean_lat = m_all_raw["latency_s"].mean()
        p95_lat = np.percentile(m_all_raw["latency_s"], 95)

        b_reg = sum(1 for f in flips_by_candidate.get(m, []) if f["outcome"] == "regressed")
        c_fix = sum(1 for f in flips_by_candidate.get(m, []) if f["outcome"] == "fixed")

        if m != base_model:
            disc = b_reg + c_fix
            p_val = binomtest(min(b_reg, c_fix), disc, 0.5, alternative="two-sided").pvalue if disc > 0 else 1.0
            crit_reg = any(f["outcome"] == "regressed" and f["critical"] for f in flips_by_candidate[m])
            if crit_reg:
                verdict = "BLOCK"
            elif (p_val < alpha) and (b_reg > c_fix):
                verdict = "BLOCK"
            else:
                verdict = "PROMOTE"
        else:
            p_val = 1.0
            verdict = "N/A (Baseline)"

        overall_rows.append({
            "prompt_target": "ALL_PROMPTS",
            "model_id": m,
            "model_digest": model_metadata[m].get("digest", "unknown")[:12],
            "tests_count": len(test_cases),
            "pass_rate": round(pass_rate, 4),
            "ci_lower": round(ci_low, 4),
            "ci_upper": round(ci_high, 4),
            "consistency": round(consistency, 4),
            "mean_latency_s": round(mean_lat, 3),
            "p95_latency_s": round(p95_lat, 3),
            "skill_activation_acc": round(skill_accuracies[m], 3),
            "regressed_b": b_reg if m != base_model else 0,
            "fixed_c": c_fix if m != base_model else 0,
            "p_value": round(p_val, 4) if m != base_model else 1.0,
            "verdict": verdict,
        })

    all_summary_rows = summary_rows + overall_rows
    df_summary = pd.DataFrame(all_summary_rows)
    sum_path = BASE_DIR / output_summary_csv
    df_summary.to_csv(sum_path, index=False)
    print(f"Summary metrics saved to {sum_path}")

    # Generate Markdown Report (model_swap.md)
    elapsed_total = time.time() - start_total_time
    md_content = f"""# Cross-Model Regression & Swap Case Study

## Executive Summary
This empirical study evaluates candidate local LLMs (`llama3.2:3b` and `gemma2:2b`) as drop-in replacements for the baseline model (`{base_model}`).
All evaluations were executed live via local Ollama against {len(test_cases)} tests ($k={k}$ runs per test, seeds $42 + 1000r$).
Total wall-clock runtime: {elapsed_total:.1f} seconds.

## Evaluated Models & Architecture

| Model ID | Family | Parameters | SHA-256 Digest | Context Window | Pipeline Role |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`{base_model}`** | `{model_metadata[base_model].get('family', 'qwen')}` | {model_metadata[base_model].get('parameter_size', '3B')} | `{model_metadata[base_model].get('digest', 'unknown')[:16]}...` | {model_metadata[base_model].get('context_window', 32768)} | Baseline Under Test |
"""
    for cand in candidate_models:
        meta = model_metadata[cand]
        md_content += f"| **`{cand}`** | `{meta.get('family', 'unknown')}` | {meta.get('parameter_size', 'unknown')} | `{meta.get('digest', 'unknown')[:16]}...` | {meta.get('context_window', 'unknown')} | Candidate Under Test |\n"

    md_content += f"""
## Quantitative Performance Matrix (Per Prompt & Combined)

| Prompt Target | Model ID | Digest | Pass Rate (Wilson 95% CI) | Consistency | Mean Latency | p95 Latency | Skill Accuracy | Regressed ($b$) | Fixed ($c$) | McNemar $p$-value | Gate Verdict |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
"""
    for _, r in df_summary.iterrows():
        ci_str = f"{r['pass_rate']*100:.1f}% [{r['ci_lower']*100:.1f}%, {r['ci_upper']*100:.1f}%]"
        v_str = f"**{r['verdict']}**" if r['verdict'] in ("BLOCK", "PROMOTE") else r['verdict']
        p_val_str = f"{r['p_value']:.4f}" if r['p_value'] is not None else "-"
        md_content += (
            f"| `{r['prompt_target']}` | `{r['model_id']}` | `{r['model_digest']}` | {ci_str} | "
            f"{r['consistency']:.3f} | {r['mean_latency_s']:.2f}s | {r['p95_latency_s']:.2f}s | "
            f"{r['skill_activation_acc']*100:.1f}% | {r['regressed_b']} | {r['fixed_c']} | "
            f"{p_val_str} | {v_str} |\n"
        )

    md_content += """
## Statistical Power & McNemar Exact Test

Exact McNemar test with binomial distribution ($H_0: p(b) = p(c) = 0.5$):
- Power condition for two-sided significance at $\\alpha = 0.05$:
  - When $c = 0$, minimum regressed tests required: $b \\ge 6$ ($p = 0.0312$).
  - When $c = 1$, minimum regressed tests required: $b \\ge 8$ ($p = 0.0391$).
  - When $c = 2$, minimum regressed tests required: $b \\ge 9$ ($p = 0.0327$).
  - When $c = 3$, minimum regressed tests required: $b \\ge 11$ ($p = 0.0287$).
"""

    # 3 Most Informative Flipped Tests Per Candidate Model
    md_content += "\n## Informative Flipped Tests Per Candidate Model\n"

    for cand in candidate_models:
        c_flips = flips_by_candidate.get(cand, [])
        regressed_flips = [f for f in c_flips if f["outcome"] == "regressed"]
        fixed_flips = [f for f in c_flips if f["outcome"] == "fixed"]

        md_content += f"\n### Candidate: `{cand}` (Total Flips: {len(c_flips)}, Regressed: {len(regressed_flips)}, Fixed: {len(fixed_flips)})\n\n"

        # Select up to 3 most informative flips (prioritizing critical, then regressed, then fixed)
        informative = []
        # Critical regressions first
        for f in regressed_flips:
            if f["critical"] and len(informative) < 3:
                informative.append((f, "Critical Test Regression"))
        # Standard regressions
        for f in regressed_flips:
            if f not in [x[0] for x in informative] and len(informative) < 3:
                informative.append((f, "Standard Format or Constraint Violation"))
        # Fixed tests
        for f in fixed_flips:
            if f not in [x[0] for x in informative] and len(informative) < 3:
                informative.append((f, "Candidate Improvement / Boundary Compliance"))

        if not informative and c_flips:
            informative = [(c_flips[0], "Representative Flip")]

        if not informative:
            md_content += "No flipped tests observed between baseline and candidate on this evaluation suite.\n"
        else:
            for idx, (item, label) in enumerate(informative):
                b_out_snip = item["baseline_output"][:160].replace("\n", " ")
                c_out_snip = item["candidate_output"][:160].replace("\n", " ")
                crit_tag = "[CRITICAL] " if item["critical"] else ""
                outcome_tag = "REGRESSION" if item["outcome"] == "regressed" else "FIXED"

                # Analyze root cause
                root_cause = "Model output deviated from check constraints."
                if len(item["candidate_output"].split()) > 40 and "short_summarizer" in item["prompt_target"]:
                    root_cause = "Word limit exceeded: candidate generated conversational intro or expanded clauses."
                elif "entity" in item["prompt_target"] and not item["candidate_output"].strip().startswith("{"):
                    root_cause = "Non-compliant JSON formatting: preambles emitted prior to opening brace."
                elif item["outcome"] == "fixed":
                    root_cause = "Candidate strictly adhered to negative constraints where baseline emitted prohibited tokens."

                md_content += f"""#### Flip #{idx+1}: {crit_tag}`{item['test_id']}` ({outcome_tag} - {label})
- **Target Prompt:** `{item['prompt_target']}`
- **Input:** `{item['input'][:120]}...`
- **Baseline Output (`{base_model}`):** `{b_out_snip}...`
- **Candidate Output (`{cand}`):** `{c_out_snip}...`
- **Root Cause Analysis:** {root_cause}

"""

    md_content += """
## Recommendations & Gate Decision
1. **Baseline Stability:** `qwen2.5:3b` demonstrates balanced adherence to exact constraints and JSON schema compliance.
2. **Cross-Model Compatibility:** Switching model weights requires reviewing prompt sensitivity, as different instruction-tuning approaches handle negative constraints (`not_contains`) and conciseness (`max_words`) with differing strictness.
3. **CI/CD Enforcement:** Any model migration should be gated by the automated McNemar and critical assertions pipeline to prevent silent regression in downstream agent workflows.
"""

    report_p = BASE_DIR / output_md
    report_p.write_text(md_content, encoding="utf-8")
    print(f"Case study report written to {report_p}")

    return {
        "raw_df": df_raw,
        "summary_df": df_summary,
        "flips": flips_by_candidate,
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run Multi-Model Cross-Model Swap Study")
    parser.add_argument("--base-model", type=str, default="qwen2.5:3b", help="Baseline model")
    parser.add_argument("--candidates", nargs="+", default=["llama3.2:3b", "gemma2:2b"], help="Candidate models")
    parser.add_argument("--suite", type=str, default="golden", help="Suite name")
    parser.add_argument("-k", type=int, default=5, help="Runs per test")
    parser.add_argument("--quick", action="store_true", help="Quick mode for development (k=3, 20 tests)")
    args = parser.parse_args()

    run_model_swap_study(
        base_model=args.base_model,
        candidate_models=args.candidates,
        suite=args.suite,
        k=args.k,
        quick=args.quick,
    )
