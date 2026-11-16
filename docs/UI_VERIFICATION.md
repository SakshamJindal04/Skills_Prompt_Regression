# Empirical UI Verification & Data Integrity Audit

This document records the empirical verification and spot-checking of numerical values presented across the Streamlit dashboard against their authoritative sources in `results/`, `config/`, `tests_data/`, and the backing relational database.

**Audit Date**: 2026-11-16  
**Auditor**: Antigravity Automated Verification Suite  
**Verification Method**: Automated cross-examination via pytest, Playwright, and deterministic file reading.  
**Result**: 25/25 verified values match ground truth with zero discrepancy.

---

## 1. Spot-Check Audit Matrix (25 Verified Empirical Values)

| # | Metric Description | UI Dashboard Page | Ground-Truth Value | Raw Data Source File | In-UI Displayed Value | Audit Status |
|---|--------------------|-------------------|-------------------|----------------------|-----------------------|--------------|
| 1 | Our Method Detection F1 | Evaluation Results (p.5) | `0.435` | `results/summary.csv` (Row 0, Col `F1`) | `0.435` | PASS |
| 2 | Our Method Precision | Evaluation Results (p.5) | `1.000` | `results/summary.csv` (Row 0, Col `Precision`) | `1.000` | PASS |
| 3 | Our Method Recall | Evaluation Results (p.5) | `0.278` | `results/summary.csv` (Row 0, Col `Recall`) | `0.278` | PASS |
| 4 | Measured Model Calls per Check | Evaluation Results (p.5) | `20` | `results/summary.csv` (Row 0, Col `Measured_Calls`) | `20` | PASS |
| 5 | Single-Run Baseline (B2) Recall | Evaluation Results (p.5) | `0.333` | `results/summary.csv` (Row 2, Col `Recall`) | `0.333` | PASS |
| 6 | Single-Run Baseline (B2) Precision | Evaluation Results (p.5) | `1.000` | `results/summary.csv` (Row 2, Col `Precision`) | `1.000` | PASS |
| 7 | PromptPex Baseline (B3) Precision | Evaluation Results (p.5) | `0.750` | `results/summary.csv` (Row 3, Col `Precision`) | `0.750` | PASS |
| 8 | Skill vs No-Skill Baseline Precision | Evaluation Results (p.5) | `0.625` | `results/summary.csv` (Row 5, Col `Precision`) | `0.625` | PASS |
| 9 | Skill-Selection Overall Accuracy | Project Scorecard (p.14) | `87.5%` | `results/summary.md` (Table 3), `tests_data/skill_benchmarks.yaml` | `87.5%` | PASS |
| 10 | Skill-Selection Clear Tasks Acc | Project Scorecard (p.14) | `93.3%` | `results/summary.md` (Section 3.1) | `93.3%` | PASS |
| 11 | Vector Cosine Retrieval Latency (Mean) | Project Scorecard (p.14) | `1.2 ms` | `results/summary.md` (Table 3) | `1.2 ms` | PASS |
| 12 | Vector Cosine Retrieval Latency (p95) | Project Scorecard (p.14) | `2.5 ms` | `results/summary.md` (Table 3) | `2.5 ms` | PASS |
| 13 | BM25 Lexical Retrieval Latency (Mean) | Project Scorecard (p.14) | `0.4 ms` | `results/summary.md` (Table 3) | `0.4 ms` | PASS |
| 14 | BM25 Lexical Retrieval Latency (p95) | Project Scorecard (p.14) | `0.9 ms` | `results/summary.md` (Table 3) | `0.9 ms` | PASS |
| 15 | Multi-Run Consistency (k=5) | Project Scorecard (p.14) | `0.959` | `results/summary.md` (Section 4), `results/model_matrix.csv` | `0.959` | PASS |
| 16 | Task Success Delta (Candidate vs Base) | Project Scorecard (p.14) | `-66.7%` | `results/summary.md` (Table 2), `results/edits.csv` | `-66.7%` | PASS |
| 17 | Exact McNemar Paired p-value | Project Scorecard (p.14) | `0.0020` | `results/summary.md` (Table 2) | `0.0020` | PASS |
| 18 | Task Success 95% Bootstrap CI | Project Scorecard (p.14) | `[-82.5%, -47.1%]` | `results/summary.md` (Table 2) | `[-82.5%, -47.1%]` | PASS |
| 19 | Subtle Mutation Detection Recall | Project Scorecard (p.14) | `27.8%` | `results/summary.csv` (Row 0, Col `Recall`) | `27.8%` | PASS |
| 20 | Injected Mutation Suite Size | Evaluation Results (p.5) | `18 regressions, 8 controls` | `results/summary.md`, `tests_data/analytics_tests.yaml` | `18 regressions, 8 controls` | PASS |
| 21 | Multi-Model Pass Rate (qwen2.5:3b) | Model Matrix (p.9) | `100.0%` | `results/model_summary.csv` (`ALL_PROMPTS`, `qwen2.5:3b`) | `100.0%` | PASS |
| 22 | Multi-Model Pass Rate (llama3.2:3b) | Model Matrix (p.9) | `33.3%` | `results/model_summary.csv` (`ALL_PROMPTS`, `llama3.2:3b`) | `33.3%` | PASS |
| 23 | Multi-Model Pass Rate (gemma2:2b) | Model Matrix (p.9) | `33.3%` | `results/model_summary.csv` (`ALL_PROMPTS`, `gemma2:2b`) | `33.3%` | PASS |
| 24 | Quarantine Consistency Threshold | Test Health (p.12) | `0.70` | `config/gate_policy.yaml` (`quarantine_consistency_threshold`) | `0.70` | PASS |
| 25 | Judge Calibration Sample Size | Model Matrix (p.9) | `40` | `results/judge_calibration.json` (`total_evaluated`) | `40` | PASS |

---

## 2. Methodology & Statistical Integrity Confirmation

1. **No Synthetic Number Inflation**: Every figure displayed in the UI stems directly from local execution artifacts or live database queries. Zero mocked or synthetic figures were injected into UI templates.
2. **Consistent Number Formatting**:
   - Decimals formatted to either 1, 2, or 3 significant places (`0.435`, `1.2 ms`, `p=0.0020`).
   - Percentages formatted consistently with explicit sign where representing deltas (`-66.7%`, `+0.0%`, `87.5%`).
   - Bootstrap confidence intervals consistently formatted as `[lower, upper]`.
3. **Dual-Encoded Statuses**:
   - All gate verdicts (`PROMOTE`, `BLOCK`, `INCONCLUSIVE`) and outcome classifications are encoded with both text labels and distinct semantic Material icons.
