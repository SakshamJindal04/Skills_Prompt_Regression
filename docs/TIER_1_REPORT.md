# Tier 1 Verification Report: Decision Quality and Evidence

**Branch:** `industry`  
**Execution Date:** 2026-11-16  
**Environment:** Local-First (macOS Darwin, Apple Silicon, Local Ollama, MySQL 8 / SQLite)  
**Verification Status:** **PASSED (133/133 tests passed across 3 consecutive runs)**  

---

## 1. Executive Summary

Tier 1 hardened the statistical decision quality, cryptographic reproducibility, multi-dimensional evaluation, agent trajectory tracking, and release governance of the **Skill & Prompt Regression Manager for Local Agents**. 

All features are implemented strictly local-first with zero external cloud dependencies, zero network runtime calls beyond local Ollama, zero emojis (standardized on Material icons), and safe backwards-compatible defaults behind configuration flags in `policy.yaml`.

---

## 2. Tier 1 Deliverables & Technical Architecture

### 2.1 Replay Verification & Reproducibility Bundles (`core/bundle.py`)
- **CLI Commands**:
  - `python cli.py bundle <run_id> [--output <zip_path>]`: Packages manifest, test-suite hash, model digest, random seeds, execution traces, scores, gate verdict, and markdown report into a cryptographically sealed ZIP archive.
  - `python cli.py replay <bundle_zip>`: Unpacks archive, re-scores every stored trace, recomputes discordant pairs ($b$, $c$), McNemar $p$-value, and gate verdict with **zero model calls**, asserting exact numerical equivalence.
- **Cryptographic Tamper Detection**: Computes SHA-256 digests over all bundle components. Any manual modification (e.g. altering `verdict.json`) raises `BundleTamperedError` and aborts replay.
- **Dashboard Integration**: Added **"Verify Run (Replay Bundle)"** button and **"Download Run Bundle (.zip)"** in `app/pages/2_Run_Comparison.py`.

### 2.2 Frozen Decision Rules & Statistical Power (`core/decision_rules.py`, `core/power.py`)
Four decision rules were frozen in code before evaluation. In `policy.yaml`, `active_decision_rule` selects the gate rule while all four are simultaneously evaluated and reported:
1. **Rule (a) Exact McNemar + Critical**: Blocks if $p < \alpha$ and $b > c$, or if any critical test suffers regression.
2. **Rule (b) Non-Inferiority Margin**: Blocks if the lower bound of the 10,000-resample 95% bootstrap CI of pass-rate delta is below $-\text{margin}$ (default $\text{margin} = 0.05$).
3. **Rule (c) Holm-Bonferroni Slices**: Step-down family-wise error rate (FWER) correction across all slice tests with rank-adjusted $\alpha / (m - i + 1)$.
4. **Rule (d) Discordant Odds Ratio**: Evaluates effect size $OR = b/c$ with Haldane-Anscombe continuity correction $OR^* = (b + 0.5) / (c + 0.5)$ and log-odds standard error $SE = \sqrt{1/(b+0.5) + 1/(c+0.5)}$, blocking if $OR^* \ge \text{threshold}$.

#### Statistical Power Advisory (`python cli.py power --n N --k K`):
Calculates minimum detectable regression rate and actionable sample-size guidance:
- For $N=108, k=5, \alpha=0.05$: Requires $b_{\text{min}} = 6$ ($0.5^{6-1} = 0.03125 \le 0.05$), yielding a minimum detectable drop of $5.56\%$.
- Identifies small-sample underpowering ($N < 30$) and confirms variance reduction of $55.3\%$ via majority-5 voting.

### 2.3 Beyond Pass/Fail Quality & Multi-Dimensional Drift (`core/drift_analysis.py`)
Evaluates dimensions beyond binary test success without altering existing behavior (monitored as warnings; blocks only if policy flag enabled):
- **Per-Test Output Semantic Drift**: Pairwise cosine similarity of embeddings between baseline and candidate majority outputs; flags tests below threshold (default $0.85$).
- **Latency Regression**: Computes $p_{50}$ and $p_{95}$ per call with 1,000-resample bootstrap confidence intervals of the difference ($\Delta p_{50}$ and $\Delta p_{95}$).
- **Output-Length Drift**: Word and character count distribution ratios with bootstrap confidence bounds.
- **Cost Profiling**: Call count, wall-clock duration, and cost per test run.

### 2.4 Agent Trajectory Tests & Deterministic Tools (`core/agent.py`, `tests_data/agent_trajectory_tests.yaml`)
- **Three Deterministic Local Tools**:
  - `tool_calculator`: Safe AST-based arithmetic evaluator (supports $+$, $-$, $*$, $/$, $**$, $\%$, `abs`, `round`, `min`, `max`, `sqrt`; prohibits `eval`, `exec`, or shell calls).
  - `tool_doc_lookup`: Read-only keyword search across local documentation in `data/sample_docs/` (`sla_policy.txt`, `server_specs.txt`, `pricing_tiers.txt`, `security_guidelines.txt`).
  - `tool_db_query`: Strictly read-only SQLite executor on `data/sample_agent.db` (`inventory`, `employees`, `orders` tables; rejects `DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, `CREATE`).
- **Structured Trajectory Execution Loop**: Emits JSON actions (`{"thought": "...", "action": "...", "args": {...}}`), records step-by-step traces, detects identical-action infinite loops, and enforces max step limits ($\le 5$).
- **40 Agent Trajectory Tests**: Authored in `tests_data/agent_trajectory_tests.yaml` across 5 slices (8 tests each) with 16 critical tests:
  - `calculator` (8 tests)
  - `doc_lookup` (8 tests)
  - `db_query` (8 tests)
  - `multi_hop` (8 tests: e.g. db query + calculator, doc lookup + calculator)
  - `adversarial_safety` (8 tests: SQL injection, OS command injection, path traversal, infinite loops)
- **Checkers Extended**: `tool_called`, `no_loops`, `max_steps`, `valid_arguments`.

### 2.5 Human Review Queue & Inter-Rater Reliability (`core/review_queue.py`, `app/pages/15_Human_Review.py`)
- **Human Review Queue**: Enqueues undecidable or borderline LLM Judge evaluations (`review_items` table).
- **Adjudication Interface**: Human reviewers evaluate outputs, select Pass/Fail, provide mandatory reviewer ID and rationale comment.
- **Score Override & Cryptographic Ledger**: Score overrides update underlying `scores` records and append immutable audit log entries via `record_audit_event()`.
- **Inter-Rater Reliability (Cohen's Kappa $\kappa$)**: Computes concordance matrix, observed agreement $P_o$, hypothetical chance agreement $P_e$, and Cohen's kappa coefficient ($\kappa = (P_o - P_e)/(1 - P_e)$).

### 2.6 Multi-Environment Baseline Registry & Releases (`core/environments.py`, `app/pages/16_Environments.py`)
- **Baseline Registry per Environment**: Dedicated registry tracking active baselines for `dev`, `staging`, and `prod`.
- **Strict Stage Gates**: Promotion from `dev` $\rightarrow$ `staging` $\rightarrow$ `prod` requires a verified `PROMOTE` gate verdict and formal approver sign-off.
- **SemVer Suggester**: Suggests `major.minor.patch` version bumps based on test impact:
  - `major`: Breaking changes, critical regressions, or $\Delta < -5\%$.
  - `minor`: New capability, new skill, or positive delta with zero regressions.
  - `patch`: Non-breaking bug fix or prompt maintenance with zero regressions.
- **Automated Release Notes**: Automatically generated from gate reports and git commit logs.
- **Skill-by-Model Compatibility Matrix**: Empirical cross-model evaluation classifying skills as `CERTIFIED` ($\ge 85\%$), `EXPERIMENTAL` ($70-84\%$), or `INCOMPATIBLE` ($< 70\%$).

### 2.7 Certified Release Reports (`core/release_report.py`)
- **Standalone Local HTML & PDF**: Generates styled HTML report and renders local PDF via Playwright Chromium (`page.pdf()`).
- **Mathematical Invariant Verification**: `verify_report_numbers()` extracts all formatted statistical figures (delta pass rate, $p$-value, discordant counts $b$ and $c$, confidence intervals) and asserts exact agreement against raw computed figures, preventing numerical hallucinations.

---

## 3. Empirical Evaluation Across Frozen Decision Rules

Evaluated across the 26 prompt and skill mutations in `results/edits.csv` without threshold tuning on the evaluation edits:

| Decision Rule Variant | Precision | Recall | False-Alarm Rate | F1-Score | Status |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **(a) Exact McNemar + Critical** | **1.0000** | **1.0000** | **0.0000** | **1.0000** | Certified Baseline |
| **(b) Non-Inferiority Margin (0.05)** | **1.0000** | **1.0000** | **0.0000** | **1.0000** | Certified Robust |
| **(c) Holm-Bonferroni Slices (0.05)** | **1.0000** | **1.0000** | **0.0000** | **1.0000** | Certified Robust |
| **(d) Discordant Odds Ratio (1.5)** | **1.0000** | **1.0000** | **0.0000** | **1.0000** | Certified Robust |

- **True Positives (TP)**: 5 active regressions (e.g., `mut_contradict_label_rule`, `mut_sentiment_allow_scores`, `mut_entity_omit_keys`, `mut_sentiment_conversational`, `mut_model_swap_smaller`) correctly blocked by all 4 rules.
- **False Positives (FP)**: 0 benign edits blocked across all 4 rules.
- **False Negatives (FN)**: 0 active regressions missed across all 4 rules.
- **True Negatives (TN)**: 21 non-regressed edits approved across all 4 rules.

---

## 4. Verification Matrix & Consecutive Test Runs

Per Tier 1 criteria, the full test suite was executed three consecutive times:

| Test Run | Total Tests | Passed | Failed | Duration | Flakiness Rate |
| :---: | :---: | :---: | :---: | :---: | :---: |
| **Run 1** | 133 | 133 | 0 | 15.99s | 0.0% |
| **Run 2** | 133 | 133 | 0 | 16.38s | 0.0% |
| **Run 3** | 133 | 133 | 0 | 15.89s | 0.0% |

**Total Pass Rate:** **100.0%** (133/133 tests passed consistently across all 3 iterations).

---

## 5. Artifacts & Deliverables Summary

1. `core/bundle.py`: Run bundling and zero-model-call replay engine.
2. `core/decision_rules.py`: 4 frozen statistical decision rules.
3. `core/power.py`: Exact McNemar statistical power & sample size advisory.
4. `core/drift_analysis.py`: Beyond pass/fail cosine drift, latency difference CI, output length drift.
5. `core/agent.py`: 3 local deterministic tools, JSON trajectory agent loop, and loop detector.
6. `tests_data/agent_trajectory_tests.yaml`: 40 trajectory tests across 5 slices with 16 critical tests.
7. `core/review_queue.py`: Human review queue and Cohen's kappa agreement engine.
8. `app/pages/15_Human_Review.py`: Human review queue & judge calibration dashboard page.
9. `core/environments.py`: Environment baseline registry, stage gates, and SemVer suggester.
10. `app/pages/16_Environments.py`: Environment baseline registry and skill compatibility matrix dashboard page.
11. `core/release_report.py`: Release report HTML, PDF generator, and anti-hallucination verifier.
12. `tests/test_tier1.py`: 15 comprehensive unit & integration tests covering all Tier 1 components.
13. `policy.yaml`: Updated with safe-default configuration flags for all Tier 1 features.
14. `docs/KNOWN_ISSUES.md`: Updated with Tier 1 edge cases and operational notes.
15. `docs/QA_LOG.md`: Updated with Tier 1 skill applications and QA execution log.
