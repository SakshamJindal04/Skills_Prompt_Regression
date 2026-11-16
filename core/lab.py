import os
import re
import time
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

import pandas as pd
import numpy as np

from core.llm import OllamaClient, default_client, LLMResponse
from core.lint import lint_prompt, lint_skill
from core.testgen import extract_prompt_spec, generate_test_suite_from_spec
from core.scorer import score_trace
from core.comparator import compare_test_results
from core.gate import evaluate_gate
from core.skills import SkillRegistry, EmbeddingSelector, try_task_routing, compute_text_similarity

logger = logging.getLogger("panel_lab")
BASE_DIR = Path(__file__).resolve().parent.parent

LABEL_COMPLIANCE = "This generated suite checks compliance with the prompt's own rules, not correctness against an external standard."
LABEL_SAMPLE_POWER = "Sample size is small (N=20, k=3): statistical tests have low power. Treat the verdict as a heuristic and read the flip table."


def check_and_truncate_prompt(prompt_text: str, max_tokens: int = 4000) -> Tuple[str, Optional[str]]:
    """
    Checks prompt length. If estimated tokens > max_tokens, truncates safely with explicit warning.
    """
    estimated_tokens = len(prompt_text.split()) * 1.3
    if estimated_tokens > max_tokens:
        allowed_words = int(max_tokens / 1.3)
        truncated = " ".join(prompt_text.split()[:allowed_words])
        notice = f"Prompt length (~{int(estimated_tokens)} tokens) exceeded {max_tokens} token threshold. Safely chunked to {allowed_words} words with explicit notice."
        return truncated, notice
    return prompt_text, None


def run_lab_pipeline(
    prompt_text: str,
    prompt_v2_text: Optional[str] = None,
    skill_text: Optional[str] = None,
    custom_inputs: Optional[List[str]] = None,
    custom_rules: Optional[List[Dict[str, Any]]] = None,
    models: Optional[List[str]] = None,
    k: int = 3,
    max_tests: int = 20,
    timeout_sec: float = 20.0,
    client: Optional[OllamaClient] = None,
    progress_cb: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Executes the end-to-end Panel Lab pipeline:
    1. Static Linting (v1 and v2)
    2. PromptPex Spec & Inverse Rule Extraction
    3. Test Suite Generation & Custom Rule Synthesis
    4. Live background execution with timeouts, wall clock tracking, and token counting
    5. Scoring & Failure Analysis with Inverse Rule Diffs
    6. Optional v1 vs v2 McNemar Gate & Flip Table
    """
    c = client or default_client
    models = models or ["qwen2.5:3b"]
    start_total_time = time.perf_counter()

    # Step 1: Length check & Linting
    p1_clean, p1_trunc_notice = check_and_truncate_prompt(prompt_text)
    if progress_cb:
        progress_cb("Running static lint checks on prompt...", 0.1)

    lint_v1 = lint_prompt(p1_clean)
    lint_v2 = lint_prompt(prompt_v2_text) if prompt_v2_text else []
    lint_skill_res = lint_skill(skill_text) if skill_text else None

    # Step 2: Spec Extraction
    if progress_cb:
        progress_cb("Extracting input spec and checkable output rules...", 0.25)
    spec = extract_prompt_spec(p1_clean, client=c)

    # Step 3: Test Generation
    if progress_cb:
        progress_cb("Generating synthetic test cases and inverse checks...", 0.40)
    generated_tests = generate_test_suite_from_spec(spec, count=max_tests)

    # Add custom inputs / rules if provided
    custom_tests = []
    if custom_inputs:
        valid_idx = 1
        for raw_line in custom_inputs:
            line = raw_line.strip()
            if not line:
                continue
            # Skip instructional fragments if copied accidentally
            if line.lower().startswith("check:") or line.lower().startswith("expected:"):
                continue

            # Clean leading labels like "Input:" or "Question:"
            if line.lower().startswith("input:"):
                line = line[6:].strip()
            elif line.lower().startswith("question:"):
                line = line[9:].strip()

            checks = []
            if "|" in line:
                parts = [p.strip() for p in line.split("|")]
                clean_input = parts[0]
                check_type = parts[1].lower() if len(parts) > 1 else "contains"
                check_val = parts[2] if len(parts) > 2 else ""
                if check_type in ("contains", "not_contains") and check_val:
                    checks = [{"type": check_type, "values": [check_val]}]
                elif check_type == "regex" and check_val:
                    checks = [{"type": "regex", "pattern": check_val}]
                elif check_type == "valid_json":
                    checks = [{"type": "valid_json"}]
            else:
                clean_input = line
                if custom_rules:
                    checks = custom_rules
                else:
                    lower_inp = clean_input.lower()
                    if any(term in lower_inp for term in ["drop", "delete", "truncate", "destroy"]):
                        checks = [
                            {"type": "not_contains", "values": ["DROP TABLE", "DELETE FROM", "TRUNCATE"]},
                            {"type": "contains", "values": ["ERROR", "Read-only", "cannot", "not permitted", "read-only"]},
                        ]
                    else:
                        checks = [
                            {"type": "contains", "values": ["SELECT"]},
                            {"type": "not_contains", "values": ["```"]},
                        ]

            custom_tests.append({
                "id": f"lab_custom_{valid_idx:02d}",
                "input": clean_input,
                "rule": "Custom Panel Input",
                "inverse_rule": "Missing expected output elements",
                "checks": checks,
                "critical": False,
            })
            valid_idx += 1
    combined_tests = (generated_tests + custom_tests)[:max_tests]

    # Step 4: Live Execution on V1
    if progress_cb:
        progress_cb(f"Executing {len(combined_tests)} tests x {k} runs on {models[0]}...", 0.55)

    v1_runs_map: Dict[str, List[bool]] = {}
    v1_traces: List[Dict[str, Any]] = []
    v1_latencies: List[float] = []
    total_prompt_tokens = 0
    total_completion_tokens = 0

    target_model = models[0]

    for tc_idx, tc in enumerate(combined_tests):
        t_id = tc.get("id", f"tc_{tc_idx}")
        inp = tc.get("input", "")
        # Protect injection by strictly encapsulating input as data
        safe_input_wrapper = f'"""\n{inp}\n"""'

        if "{input}" in p1_clean:
            full_prompt = p1_clean.replace("{input}", safe_input_wrapper)
        else:
            full_prompt = f"{p1_clean}\n\nTask Data Input:\n{safe_input_wrapper}\n\nOutput:"

        runs_passed = []
        for r_idx in range(k):
            seed = 42 + r_idx * 1000
            call_start = time.perf_counter()
            timed_out = False
            out_text = ""

            try:
                resp = c.generate(
                    prompt=full_prompt,
                    temperature=0.7,
                    seed=seed,
                    model=target_model,
                    use_cache=True,
                )
                out_text = resp.text
                call_lat = resp.latency_ms
                total_prompt_tokens += resp.prompt_tokens
                total_completion_tokens += resp.completion_tokens
            except Exception as e:
                call_lat = (time.perf_counter() - call_start) * 1000.0
                out_text = f"[TIMEOUT/ERROR: {str(e)[:100]}]"
                timed_out = True

            v1_latencies.append(call_lat)
            score_res = score_trace({"output": out_text}, tc.get("checks", []))
            passed = score_res["passed"] and not timed_out
            runs_passed.append(passed)

            v1_traces.append({
                "test_id": t_id,
                "input": inp,
                "run_index": r_idx,
                "output": out_text,
                "passed": passed,
                "latency_ms": round(call_lat, 2),
                "timed_out": timed_out,
                "rule": tc.get("rule", "General"),
                "inverse_rule": tc.get("inverse_rule", "Inverse failure"),
                "check_details": score_res.get("details", []),
            })

        v1_runs_map[t_id] = runs_passed

    # Step 5: Live Execution on V2 (if provided)
    v2_runs_map: Dict[str, List[bool]] = {}
    v2_traces: List[Dict[str, Any]] = []
    v2_comparison = None

    if prompt_v2_text:
        p2_clean, _ = check_and_truncate_prompt(prompt_v2_text)
        if progress_cb:
            progress_cb("Executing tests against Candidate V2 prompt...", 0.80)

        for tc_idx, tc in enumerate(combined_tests):
            t_id = tc.get("id", f"tc_{tc_idx}")
            inp = tc.get("input", "")
            safe_input_wrapper = f'"""\n{inp}\n"""'

            if "{input}" in p2_clean:
                full_prompt = p2_clean.replace("{input}", safe_input_wrapper)
            else:
                full_prompt = f"{p2_clean}\n\nTask Data Input:\n{safe_input_wrapper}\n\nOutput:"

            runs_passed = []
            for r_idx in range(k):
                seed = 42 + r_idx * 1000
                call_start = time.perf_counter()
                timed_out = False
                out_text = ""

                try:
                    resp = c.generate(
                        prompt=full_prompt,
                        temperature=0.7,
                        seed=seed,
                        model=target_model,
                        use_cache=True,
                    )
                    out_text = resp.text
                    call_lat = resp.latency_ms
                except Exception as e:
                    call_lat = (time.perf_counter() - call_start) * 1000.0
                    out_text = f"[TIMEOUT/ERROR: {str(e)[:100]}]"
                    timed_out = True

                score_res = score_trace({"output": out_text}, tc.get("checks", []))
                passed = score_res["passed"] and not timed_out
                runs_passed.append(passed)

                v2_traces.append({
                    "test_id": t_id,
                    "input": inp,
                    "run_index": r_idx,
                    "output": out_text,
                    "passed": passed,
                    "latency_ms": round(call_lat, 2),
                    "timed_out": timed_out,
                })

            v2_runs_map[t_id] = runs_passed

        # McNemar Comparison V1 vs V2
        comp_res = compare_test_results(combined_tests, v1_runs_map, v2_runs_map, k=k)
        verdict, rep_md = evaluate_gate(comp_res, alpha=0.05, auto_promote=False)
        v2_comparison = {
            "comparison": comp_res,
            "verdict": verdict,
            "report_md": rep_md,
            "b": comp_res.get("regressed_count", 0),
            "c": comp_res.get("fixed_count", 0),
            "p_value": comp_res.get("p_value", 1.0),
            "delta_pass_rate": comp_res.get("delta_pass_rate", 0.0),
            "ci_95": comp_res.get("confidence_interval_95", [0.0, 0.0]),
        }

    total_wall_clock = round(time.perf_counter() - start_total_time, 2)
    p50_lat = float(np.percentile(v1_latencies, 50)) if v1_latencies else 0.0
    p95_lat = float(np.percentile(v1_latencies, 95)) if v1_latencies else 0.0

    # Per-rule statistics
    rule_stats: Dict[str, Dict[str, Any]] = {}
    for tr in v1_traces:
        r = tr.get("rule", "General")
        if r not in rule_stats:
            rule_stats[r] = {"total": 0, "passed": 0, "inverse_rule": tr.get("inverse_rule", "")}
        rule_stats[r]["total"] += 1
        if tr["passed"]:
            rule_stats[r]["passed"] += 1

    rule_summary = []
    for r, st in rule_stats.items():
        tot = st["total"] or 1
        rule_summary.append({
            "rule": r,
            "inverse_rule": st["inverse_rule"],
            "pass_rate": round(st["passed"] / tot, 4),
            "passed": st["passed"],
            "total": st["total"],
        })

    # Overall pass rate
    total_evals = len(v1_traces) or 1
    total_passed = sum(1 for t in v1_traces if t["passed"])
    overall_pass_rate = round(total_passed / total_evals, 4)

    # Local Ollama cost is $0.00
    cost_summary = {
        "model_calls": len(v1_traces) + len(v2_traces),
        "total_prompt_tokens": total_prompt_tokens,
        "total_completion_tokens": total_completion_tokens,
        "local_cost_usd": 0.00,
        "measured_wall_time_s": total_wall_clock,
    }

    if progress_cb:
        progress_cb("Panel Lab evaluation complete.", 1.0)

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "prompt_v1": p1_clean,
        "prompt_v2": prompt_v2_text,
        "model": target_model,
        "k": k,
        "n_tests": len(combined_tests),
        "warning_compliance": LABEL_COMPLIANCE,
        "warning_power": LABEL_SAMPLE_POWER,
        "truncation_notice": p1_trunc_notice,
        "lint_v1": lint_v1,
        "lint_v2": lint_v2,
        "lint_skill": lint_skill_res,
        "spec": spec,
        "tests": combined_tests,
        "rule_summary": rule_summary,
        "overall_pass_rate": overall_pass_rate,
        "latency_p50_ms": round(p50_lat, 2),
        "latency_p95_ms": round(p95_lat, 2),
        "wall_clock_s": total_wall_clock,
        "cost": cost_summary,
        "traces": v1_traces,
        "v2_traces": v2_traces,
        "v2_comparison": v2_comparison,
    }


def export_lab_markdown(results: Dict[str, Any], output_path: Optional[str] = None) -> str:
    """Exports structured Panel Lab results to Markdown."""
    ts = results.get("timestamp", datetime.now(timezone.utc).isoformat())
    model = results.get("model", "qwen2.5:3b")
    k = results.get("k", 3)
    n = results.get("n_tests", 0)

    md = f"""# Panel Lab Evaluation Report

- **Generated**: {ts}
- **Model**: `{model}`
- **Test Configuration**: N={n} tests, k={k} repetitions
- **Overall Pass Rate**: {results.get('overall_pass_rate', 0.0):.2%}
- **Latency (p50 / p95)**: {results.get('latency_p50_ms', 0.0)} ms / {results.get('latency_p95_ms', 0.0)} ms
- **Total Wall Clock**: {results.get('wall_clock_s', 0.0)} s
- **Model Calls**: {results.get('cost', {}).get('model_calls', 0)} calls (Local Ollama cost: $0.00)

## Advisory Warnings

> **Methodology Notice**: {results.get('warning_compliance', LABEL_COMPLIANCE)}
>
> **Statistical Power Notice**: {results.get('warning_power', LABEL_SAMPLE_POWER)}

## Static Linting Findings

"""
    lint_v1 = results.get("lint_v1", [])
    if lint_v1:
        md += "| Code | Severity | Message | Line |\n| :--- | :--- | :--- | :--- |\n"
        for l in lint_v1:
            md += f"| `{l.get('code')}` | **{l.get('severity')}** | {l.get('message')} | {l.get('line', '-')} |\n"
    else:
        md += "No lint findings detected. Prompt adheres cleanly to formatting and safety rules.\n"

    md += """
## Per-Rule Compliance Breakdown

| Rule | Inverse Rule / Failure Mode | Pass Rate | Passed / Total |
| :--- | :--- | :--- | :--- |
"""
    for r in results.get("rule_summary", []):
        md += f"| {r['rule']} | {r['inverse_rule']} | {r['pass_rate']:.2%} | {r['passed']} / {r['total']} |\n"

    v2 = results.get("v2_comparison")
    if v2:
        md += f"""
## Candidate V2 Comparison & Gate Verdict

- **Gate Verdict**: **{v2.get('verdict')}**
- **McNemar p-value**: {v2.get('p_value', 1.0):.4f}
- **Regressed (b)**: {v2.get('b', 0)}
- **Fixed (c)**: {v2.get('c', 0)}
- **Delta Pass Rate**: {v2.get('delta_pass_rate', 0.0):+.2%} (95% CI: [{v2.get('ci_95', [0,0])[0]:+.2%}, {v2.get('ci_95', [0,0])[1]:+.2%}])
"""

    if output_path:
        p = Path(output_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(md, encoding="utf-8")
    return md


def export_lab_csv(results: Dict[str, Any], output_path: Optional[str] = None) -> str:
    """Exports individual trace outputs to CSV."""
    traces = results.get("traces", [])
    df = pd.DataFrame(traces)
    csv_str = df.to_csv(index=False)
    if output_path:
        p = Path(output_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(csv_str, encoding="utf-8")
    return csv_str


def save_lab_prompt_version(prompt_filename: str, prompt_content: str, commit_msg: str) -> Dict[str, Any]:
    """
    Saves and commits a prompt from the Panel Lab to workspace/prompts/.
    """
    from core.repo import commit_workspace, get_repo, get_workspace_path

    ws = get_workspace_path()
    prompts_dir = ws / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)

    if not prompt_filename.endswith(".md"):
        prompt_filename += ".md"

    target_file = prompts_dir / prompt_filename
    target_file.write_text(prompt_content, encoding="utf-8")

    commit_sha = commit_workspace(message=commit_msg)
    return {
        "success": True,
        "file_path": str(target_file),
        "commit_hash": commit_sha,
        "message": f"Successfully saved and committed '{prompt_filename}' at {commit_sha[:7]}."
    }

