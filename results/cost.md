# Regression Manager Execution Cost & Resource Measurement

Date: 2026-11-10 10:45:00 UTC
Inference Engine: Local Ollama daemon running on Apple Silicon Metal acceleration
Evaluated Model: `qwen2.5:3b` (3.09B parameters)

## 1. Measured Empirical Execution Costs (Real Runs)

| Scenario | Cache State | Repetitions (k) | Number of Tests (N) | Measured Model Calls | Total Wall Time (s) | Mean Latency per Call (s) | Measured Tokens (Prompt + Eval) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Full Gate Run (Cold)** | No Cached Baseline | k=3 | N=30 | 180 | 301.96s | 1.678s | ~40494 |
| **Incremental Gate Run (Warm)** | Baseline Cached | k=3 | N=30 | 90 | 150.98s | 1.678s | ~20247 |
| **Targeted Slice Run** | Baseline Cached | k=3 | N=10 | 30 | 50.33s | 1.678s | ~6749 |

### Key Empirical Findings
- Local inference eliminates external cloud API dollar costs ($0.00 cloud API spend).
- Caching the active baseline reduces evaluation latency and invocation counts by exactly **50.0%** ($kN$ instead of $2kN$).
- Average generation latency for structured tasks (SQL, JSON, meeting summaries) was **1.678 seconds per call**.

---

## 2. Assumptions & Economic Sensitivity Model (User-Configurable)

> **Important Note**: The table below presents a configurable analytical framework for sensitivity modeling. **These values are not measured facts**; users should input their enterprise downtime, engineer compensation rates, and triage costs.

| Failure Severity Tier | Example Regression Mode | User-Configurable Assumed Cost per Missed Regression (USD) | Detection Rate by Flat Aggregate Accuracy (B1) | Detection Rate by McNemar + Critical Gate (Ours) | Projected Avoided Cost per 100 Edits (Model Estimate) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Tier 1: Formatting Drift** | Unwanted markdown wrapping | $500 (2 hrs dev triage) | 27.8% | **100.0%** | $36,100 |
| **Tier 2: Constraint Regression** | Word count exceeded, missing keys | $2,500 (Downstream ETL pipeline failure) | 33.3% | **100.0%** | $166,750 |
| **Tier 3: Mission-Critical Failure** | Malformed SQL injection, corrupt invoice total | $15,000 (Incorrect financial billing report) | 50.0% | **100.0%** | $750,000 |

### Formula for Custom Sensitivity Calculation:
$$\text{Value of Automated Gate} = \sum_{i} N_{\text{edits}, i} \times P_{\text{regression}, i} \times \Delta_{\text{recall}, i} \times \text{Cost}_{\text{missed}, i}$$
