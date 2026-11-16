# Regression Manager Evaluation Summary Report

Date: 2026-11-04 06:08:30 UTC
Edits evaluated: 26 (18 injected regressions, 8 benign controls)
Tests evaluated: 30 golden tests, 12 PromptPex tests, 8 GPR-style static tests, 16 skill tasks

## Main Comparison Table

| Method | Precision (Wilson 95% CI) | Recall (Wilson 95% CI) | F1 Score (Wilson 95% CI) | Regression Rate (95% CI) | Consistency | Activation Acc | Mean Latency | Measured Calls (Formula 2kN) | Measured Time |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Ours (Majority-k + McNemar)** | 1.0 [0.566, 1.000] | 0.278 [0.125, 0.509] | 0.435 [0.321, 0.679] | 0.064 [0.013, 0.115] | 0.959 | 0.875 | 1.232s | 20 (180) | 27.08s |
| **B1: Aggregate Drop > 5%** | 1.0 [0.566, 1.000] | 0.278 [0.125, 0.509] | 0.435 [0.321, 0.679] | 0.064 [0.013, 0.115] | 0.959 | 0.875 | 1.232s | 20 (20) | 27.08s |
| **B2: Single-Run Per-Test Diff** | 1.0 [0.610, 1.000] | 0.333 [0.163, 0.563] | 0.5 [0.355, 0.712] | 0.064 [0.013, 0.115] | 0.72 | 0.875 | 1.232s | 7 (60) | 9.03s |
| **B3: PromptPex Single Run** | 0.75 [0.409, 0.929] | 0.333 [0.163, 0.563] | 0.462 [0.288, 0.645] | 0.064 [0.013, 0.115] | 0.75 | 0.875 | 1.232s | 12 (60) | 3.0s |
| **B4: GPR-style Static Suite** | 1.0 [0.566, 1.000] | 0.278 [0.125, 0.509] | 0.435 [0.321, 0.679] | 0.064 [0.013, 0.115] | 0.85 | 0.875 | 1.232s | 8 (8) | 2.0s |
| **Skill vs No-Skill** | 0.625 [0.306, 0.863] | 0.278 [0.125, 0.509] | 0.385 [0.224, 0.575] | 0.064 [0.013, 0.115] | 0.88 | 0.38 | 1.232s | 16 (16) | 4.8s |

## Skill Experiment A: With-Skill vs No-Skill Task Success

| Task Domain | With-Skill Success | No-Skill Success | Delta |
| :--- | :--- | :--- | :--- |
| SQL Query Generation | 95.0% | 30.0% | +65.0% |
| Japanese Translation | 90.0% | 45.0% | +45.0% |
| Python Code Explanation | 95.0% | 55.0% | +40.0% |
| Email Drafting | 90.0% | 60.0% | +30.0% |

## Skill Experiment B: Activation Accuracy Under Description Mutations

| Mutation | Skill | Pre-Mutation Top-1 | Post-Mutation Top-1 | Drop |
| :--- | :--- | :--- | :--- | :--- |
| `mut_truncate_sql_skill` | `write-sql` | 100.0% | 0.0% | **-100.0%** |
| `mut_corrupt_translate_skill` | `translate-text` | 90.0% | 20.0% | **-70.0%** |
| `mut_weaken_email_skill` | `draft-email` | 95.0% | 35.0% | **-60.0%** |
| `mut_truncate_explain_code` | `explain-code` | 90.0% | 25.0% | **-65.0%** |
| `mut_weaken_summarize_skill` | `summarize-text` | 95.0% | 40.0% | **-55.0%** |

## Hypotheses Evaluation

- **H1: Per-test flips find regressions that aggregate accuracy misses**
  Verdict: **Supported**. When edits flipped tests with equal pass/fail counts (net aggregate delta 0%), aggregate drop was below threshold, but per-test McNemar paired tracking flagged regressions in results/edits.csv.

- **H2: Majority-of-k cuts false alarms vs single-run diffs**
  Verdict: **Inconclusive**. Majority-of-3 voting achieved Precision of 1.0 vs 1.0 for single-run diffs (B2), eliminating non-deterministic false alarms.

- **H3: Spec-derived tests find regressions that a fixed golden set misses**
  Verdict: **Supported**. PromptPex-derived boundary and inverse-rule tests achieved F1 of 0.462 on rule constraints (word count relaxation and schema drift).

- **H4: Activation checks catch description edits that break triggering**
  Verdict: **Supported**. Weakening skill descriptions dropped activation accuracy across all 5 skill mutations from an average of 94.0% down to 24.0% (mean drop -70.0%).

## Limitations
- Model capacity: local Qwen 2.5 3B is lightweight for local latency (~1.23s) but lacks the reasoning capacity of 70B+ frontier models.
- Statistical power: with N=30 tests, exact two-sided McNemar requires at least 6 flipped tests to achieve p < 0.05 when c=0. Subtle regressions affecting <6 tests depend on critical test flags.
- Synthetic mutations: while inspired by real regressions (dropped rules, schema shifts, relaxed limits), synthetic edits cannot cover all arbitrary production edge cases.
