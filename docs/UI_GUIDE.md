# RegGuard Dashboard User Guide & Page Directory

**Document Version:** 1.0.0  
**Design Theme:** RegGuard Natural Design System (Sage, Slate, Amber, Terracotta)  
**Target Audience:** Machine Learning Engineers, Quality Assurance Auditors, Product Governance Leads

---

## Overview

The Skill & Prompt Regression Manager provides a local-first, statistically disciplined observability and governance dashboard for autonomous local agents. The dashboard comprises 17 purpose-built views organized under four functional navigation sections: **Overview**, **Changes**, **Quality & Analysis**, and **Governance & Proof**.

---

## 1. System Overview (`00_overview`)
- **Route:** `http://localhost:8501/` (Default entrypoint)
- **Description:** The System Overview dashboard delivers an executive-level status view of the current regression posture. It features five high-prominence KPI metric cards tracking the active baseline artifact, the most recent regression gate verdict, empirical golden suite pass rate (64.8%), regressed test count, and k=5 run consistency (95.9%). Below the KPI row sits a verdict banner, a historical pass-rate trendline across registered artifact revisions, a recent gate comparison table, and live Ollama model digest monitoring to detect silent runtime drift.
- **Data Sources:** Local MySQL database `scores`, `artifacts`, and `comparisons` tables; local Ollama `/api/show` and `/api/ps` endpoints.
- **Reference Screenshot:** `docs/screenshots/after/00_overview_light_1440x900.png`

---

## 2. Versions and Diffs (`01_versions_and_diffs`)
- **Route:** `http://localhost:8501/Versions_and_Diffs`
- **Description:** This view provides revision control management for all prompt and skill assets stored in `workspace/`. Users can browse the immutable Git commit history, inspect content-addressed artifact manifests in the relational database, view unified and syntax-highlighted diffs with accessible green/red line coloring between any two commits, directly author and commit edits with required commit messages, and execute static lint analysis to detect prompt injection vectors and vague constraints before deployment.
- **Data Sources:** Local workspace Git repository (`core/repo.py`), MySQL `artifacts` table, and static AST linter (`core/lint.py`).
- **Reference Screenshot:** `docs/screenshots/after/01_versions_and_diffs_light_1440x900.png`

---

## 3. Run Comparison (`02_run_comparison`)
- **Route:** `http://localhost:8501/Run_Comparison`
- **Description:** The core statistical gating engine of the application. Users configure paired evaluations between a baseline artifact (control) and candidate artifact (treatment) at a designated alpha threshold (default 0.05). The system computes exact McNemar test statistics on discordant pairs ($b$ vs $c$), generates 10,000-resample bootstrap 95% confidence intervals on the delta pass rate, displays prominent promotion or blocking verdict banners, flags Simpson's Paradox masking, provides a test-by-test flip table drill-down, generates reproducible ZIP run bundles, and computes single-file ablation attribution to isolate root causes.
- **Data Sources:** MySQL `test_cases`, `scores`, and `traces` tables; exact binomial calculation (`scipy.stats.binomtest`); replay bundle engine (`core/bundle.py`).
- **Reference Screenshot:** `docs/screenshots/after/02_run_comparison_light_1440x900.png`

---

## 4. Slices & Simpson's Paradox (`03_slices`)
- **Route:** `http://localhost:8501/Slices`
- **Description:** Analyzes model performance partitioned across granular test slices (difficulty tiers, query categories, task complexities) to prevent Simpson's Paradox, where an aggregate pass rate improvement masks localized regressions in critical sub-cohorts. The page renders a slice breakdown matrix with delta pass rates, an interactive Plotly delta bar chart styled with the Natural Palette (`#B4483C` for regressed, `#4C8A5E` for improved), and a detailed explanation of slice-aware threshold policies ($\Delta \le -0.10$).
- **Data Sources:** MySQL `scores` table joined with slice tags from `tests_data/golden_tests.yaml`.
- **Reference Screenshot:** `docs/screenshots/after/03_slices_light_1440x900.png`

---

## 5. Skill Activation & Routing (`04_skill_activation`)
- **Route:** `http://localhost:8501/Skill_Activation`
- **Description:** Dedicated observability workbench for the agent's semantic skill selector. It features an ad-hoc task routing inspector showing real-time cosine similarity scores across candidate skills, a pairwise skill conceptual overlap heatmap highlighting ambiguous pairs (cosine similarity $> 0.75$), comprehensive benchmark results across 120 standardized tasks with confusion pattern matrices, sub-millisecond scalability latency curves across catalog sizes ($N=6, 12, 24$), and a searchable skills catalog.
- **Data Sources:** Local `nomic-embed-text` embeddings, BM25 index, and `tests_data/skill_benchmarks.yaml`.
- **Reference Screenshot:** `docs/screenshots/after/04_skill_activation_light_1440x900.png`

---

## 6. Evaluation Benchmark Results (`05_evaluation_results`)
- **Route:** `http://localhost:8501/Evaluation_Results`
- **Description:** Quantitative benchmark dashboard comparing our exact McNemar regression gating strategy against four standard baseline approaches (No Gating, Simple Pass-Rate Threshold, Static Linting, and Single-Run Exact Match) across 18 injected prompt/skill regressions and 8 benign controls. It displays detection precision, recall, and F1 score cards (+0.247 F1 improvement over static linting), latency benchmarks, model call cost graphs, and raw markdown/CSV export buttons.
- **Data Sources:** Ground-truth benchmark files `results/summary.csv` and `results/summary.md`.
- **Reference Screenshot:** `docs/screenshots/after/05_evaluation_results_light_1440x900.png`

---

## 7. Rollback Workflow (`06_rollback`)
- **Route:** `http://localhost:8501/Rollback`
- **Description:** Governed remediation center providing non-destructive rollbacks when regressions breach production thresholds. Users inspect active baseline vs HEAD commits, select a specific regression commit, review an expected metric recovery profile, examine unified commit diffs, and launch an `@st.dialog` modal confirmation window. The modal enforces mandatory incident justifications, executes `git revert`, registers a new recovered baseline artifact, and displays post-rollback verification scores.
- **Data Sources:** Local workspace Git repository (`core/repo.py`) and MySQL `comparisons` and `scores` tables.
- **Reference Screenshot:** `docs/screenshots/after/06_rollback_light_1440x900.png`

---

## 8. Change Requests & Governance Approvals (`07_change_requests`)
- **Route:** `http://localhost:8501/Change_Requests`
- **Description:** Enterprise change control hub enforcing two-person authorization and separation-of-duties rules prior to baseline promotion. Requesters submit proposed revisions for automated regression gating; once gated with a `PROMOTE` verdict, designated approvers review findings and execute promotion or rejection via dedicated `@st.dialog` confirmation dialogs with required comments. The system strictly prevents self-approval and halts promotions during active policy freezes.
- **Data Sources:** Local MySQL `change_requests` table and `policy.yaml` rules.
- **Reference Screenshot:** `docs/screenshots/after/07_change_requests_light_1440x900.png`

---

## 9. System Audit Trail (`08_audit_log`)
- **Route:** `http://localhost:8501/Audit_Log`
- **Description:** Cryptographically anchored audit trail providing an immutable ledger of all system events (change request submissions, gate evaluations, human approvals, and baseline promotions). Every event is chained via SHA-256 hashes linking back to the genesis record. The page features real-time hash chain integrity verification (validating zero tampering), action and verdict filters, a tabular log view, and a detailed single-event inspector.
- **Data Sources:** Local append-only `logs/audit.jsonl` and MySQL `audit_logs` table.
- **Reference Screenshot:** `docs/screenshots/after/08_audit_log_light_1440x900.png`

---

## 10. Multi-Model Regression Matrix (`09_model_matrix`)
- **Route:** `http://localhost:8501/Model_Matrix`
- **Description:** Evaluates prompt behavior and stability across diverse local model families (`qwen2.5:3b`, `llama3.2:3b`, `gemma2:2b`). It displays a combined pass-rate summary with Wilson 95% confidence intervals, an interactive heatmap of pass rates across prompt targets and models, latency and run consistency comparisons, a detailed flip table comparing candidate models to the Qwen baseline, and an LLM Judge calibration section measuring Cohen's Kappa against deterministic assertions.
- **Data Sources:** Multi-model benchmark files `results/model_summary.csv`, `results/model_matrix.csv`, and `results/judge_calibration.json`.
- **Reference Screenshot:** `docs/screenshots/after/09_model_matrix_light_1440x900.png`

---

## 11. Panel Evaluation & Exploration Lab (`10_panel_lab`)
- **Route:** `http://localhost:8501/Panel_Lab`
- **Description:** Interactive rapid prototyping sandbox for prompt engineers. It features a 5-step visual stepper guiding users through input prompt authoring, rule and model configuration, custom test synthesis (safety refusals, aggregate SQL queries), live local execution profiling, and paired candidate regression gating. It displays static lint findings, per-rule compliance breakdowns, execution traces with latency, and Git commit versioning.
- **Data Sources:** Local Ollama runner, prompt AST linter, and synthetic test evaluator (`core/lab.py`).
- **Reference Screenshot:** `docs/screenshots/after/10_panel_lab_light_1440x900.png`

---

## 12. Responsible AI Scorecard (`11_responsible_ai_scorecard`)
- **Route:** `http://localhost:8501/Responsible_AI_Scorecard`
- **Description:** Governance scorecard providing empirical evaluations across core Responsible AI pillars: Safety Refusal Rate (100.0%), Prompt Injection Success Rate (0.0%), PII Leakage Rate (0.0%), and Counterfactual Demographic Fairness Parity Gap (0.0%). The page breaks down metrics by test family (functional, output format, robustness, safety, privacy, fairness, consistency) with Wilson 95% confidence intervals, details counterfactual demographic pairs, and provides an adversarial test directory.
- **Data Sources:** Local MySQL `scores` table and `tests_data/analytics_tests.yaml` Responsible AI test definitions.
- **Reference Screenshot:** `docs/screenshots/after/11_responsible_ai_scorecard_light_1440x900.png`

---

## 13. Test Suite Health & Flakiness (`12_test_health`)
- **Route:** `http://localhost:8501/Test_Health`
- **Description:** Quality telemetry dashboard identifying stochastic test flakiness, isolating unstable assertions, and auditing test suite vitality. It tracks flaky assertions (20% to 80% pass rates), quarantines unstable tests below a configurable consistency threshold (0.70) to prevent false-alarm gate blocking, flags dead-weight assertions (100% pass across all variations), highlights unachievable assertions (0% pass), and warns about stale tests unrevised across 3+ prompt commits.
- **Data Sources:** Historical test scores in MySQL analyzed via `core/health.py` against `policy.yaml`.
- **Reference Screenshot:** `docs/screenshots/after/12_test_health_light_1440x900.png`

---

## 14. Deliverables Verification (`13_deliverables`)
- **Route:** `http://localhost:8501/Deliverables`
- **Description:** Formal verification checklist auditing compliance against the five core project sheet deliverables: Skill Repository, Test Runner, Version Comparison Dashboard, Rollback Workflow, and Documented Best Practices. Each deliverable is paired with a live, interactive self-test button that verifies component availability, schema conformance, runner connectivity, and statistical calculator accuracy.
- **Data Sources:** Component health inspections across `workspace/skills/`, `core/runner.py`, `core/comparator.py`, and `docs/BEST_PRACTICES.md`.
- **Reference Screenshot:** `docs/screenshots/after/13_deliverables_light_1440x900.png`

---

## 15. Project Scorecard (`14_project_scorecard`)
- **Route:** `http://localhost:8501/Project_Scorecard`
- **Description:** Formal verification scorecard mapping measured empirical performance against all five target specifications: Skill Accuracy ($\ge 80.0\%$, measured 87.5%), Regression Detection ($\Delta$ detected with $p < 0.05$, measured $\Delta = -66.7\%, p = 0.0020$), Detection Recall ($\ge 25.0\%$, measured 27.8% with 100.0% precision), Run Consistency ($\ge 0.90$, measured 0.959), and Retrieval Latency ($< 50.0\text{ ms}$, measured 1.2 ms).
- **Data Sources:** Verified empirical evaluation summaries in `results/summary.md`, `results/summary.csv`, and `results/model_matrix.csv`.
- **Reference Screenshot:** `docs/screenshots/after/14_project_scorecard_light_1440x900.png`

---

## 16. Human Review Queue (`15_human_review`)
- **Route:** `http://localhost:8501/Human_Review`
- **Description:** Human-in-the-loop audit workspace for adjudicating borderline, flagged, or uncertain model generations. Domain experts review model trajectories, assign ground-truth labels (PASS/FAIL), provide mandatory review rationales, and optionally override database scores. The view tracks historical reviews and computes Cohen's Kappa ($\kappa$) and observed concordance to benchmark LLM-Judge reliability against human consensus.
- **Data Sources:** Local MySQL `human_reviews` table and `core/review_queue.py`.
- **Reference Screenshot:** `docs/screenshots/after/15_human_review_light_1440x900.png`

---

## 17. Environments & Releases (`16_environments`)
- **Route:** `http://localhost:8501/Environments`
- **Description:** Multi-environment release lifecycle manager tracking active baseline manifests across Development, Staging, and Production tiers. It enforces stage gates requiring verified passing gate comparisons before promotion to higher environments, provides automated Semantic Versioning (SemVer) recommendations based on change type and critical test regressions, displays environment release notes, and audits skill-by-model compatibility matrices.
- **Data Sources:** MySQL `environment_baselines` table, `results/model_matrix.csv`, and `core/environments.py`.
- **Reference Screenshot:** `docs/screenshots/after/16_environments_light_1440x900.png`
