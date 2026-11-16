# RegGuard Streamlit Dashboard Operational Guide

This operational manual documents all 17 views of the **Skill & Prompt Regression Manager for Local Agents** under the Light-Only Modern Design System.

---

## 1. System Overview (`0_Overview.py`)
- **One-line purpose:** Central enterprise command center displaying high-level regression KPIs, empirical pass rate trends, active model digests, and the latest gate verdict.
- **Data Sources:** Local MySQL database `comparisons`, `artifacts`, and `scores` tables; Ollama local daemon (`/api/tags`, `/api/ps`).
- **Visual Evidence:** [00_overview_light_1440x900.png](file:///Users/sakshamjindal/Desktop/Responsible_Ai/docs/screenshots/after/00_overview_light_1440x900.png)

## 2. Versions & Diffs (`1_Versions_and_Diffs.py`)
- **One-line purpose:** Side-by-side prompt and skill diff viewer comparing candidate changes directly against the active baseline commit with syntax-highlighted additions and deletions.
- **Data Sources:** Local Git repository history (`git show`, `git diff`); `workspace/prompts/` and `workspace/skills/`.
- **Visual Evidence:** [01_versions_and_diffs_light_1440x900.png](file:///Users/sakshamjindal/Desktop/Responsible_Ai/docs/screenshots/after/01_versions_and_diffs_light_1440x900.png)

## 3. Run Comparison (`2_Run_Comparison.py`)
- **One-line purpose:** Exact paired statistical regression testing using McNemar's test, 95% bootstrap confidence intervals, and discordant flip breakdown tables (b vs c).
- **Data Sources:** Relational database `scores` and `traces` tables; paired test execution logs.
- **Visual Evidence:** [02_run_comparison_light_1440x900.png](file:///Users/sakshamjindal/Desktop/Responsible_Ai/docs/screenshots/after/02_run_comparison_light_1440x900.png)

## 4. Slices & Simpson's Paradox (`3_Slices.py`)
- **One-line purpose:** Granular slice-level regression analysis detecting hidden regressions across prompt complexity tiers and testing for Simpson's Paradox.
- **Data Sources:** Database `scores` joined with `test_cases` metadata tags (`complexity`, `slice_category`).
- **Visual Evidence:** [03_slices_light_1440x900.png](file:///Users/sakshamjindal/Desktop/Responsible_Ai/docs/screenshots/after/03_slices_light_1440x900.png)

## 5. Skill Activation (`4_Skill_Activation.py`)
- **One-line purpose:** Evaluates agent skill routing precision, recall, and intentional fallback behaviors across multi-turn intent datasets.
- **Data Sources:** `tests_data/skill_benchmarks.yaml` and skill router execution traces.
- **Visual Evidence:** [04_skill_activation_light_1440x900.png](file:///Users/sakshamjindal/Desktop/Responsible_Ai/docs/screenshots/after/04_skill_activation_light_1440x900.png)

## 6. Evaluation Results (`5_Evaluation_Results.py`)
- **One-line purpose:** Multi-run empirical pass rate and consistency metrics across repeated test iterations ($k=5$) with deterministic seeds.
- **Data Sources:** `results/golden_runs/` raw scores and database test execution history.
- **Visual Evidence:** [05_evaluation_results_light_1440x900.png](file:///Users/sakshamjindal/Desktop/Responsible_Ai/docs/screenshots/after/05_evaluation_results_light_1440x900.png)

## 7. Rollback Workflow (`6_Rollback.py`)
- **One-line purpose:** Safe one-click rollback system restoring previous verified baselines with automated pre-flight checks and `@st.dialog` confirmation.
- **Data Sources:** Git reflog and database `baseline_registry` table.
- **Visual Evidence:** [06_rollback_light_1440x900.png](file:///Users/sakshamjindal/Desktop/Responsible_Ai/docs/screenshots/after/06_rollback_light_1440x900.png)

## 8. Change Requests (`7_Change_Requests.py`)
- **One-line purpose:** Enterprise governance workflow managing proposed candidate promotions with peer review approvals and cryptographic audit signatures.
- **Data Sources:** Relational database `change_requests` table and audit HMAC chains.
- **Visual Evidence:** [07_change_requests_light_1440x900.png](file:///Users/sakshamjindal/Desktop/Responsible_Ai/docs/screenshots/after/07_change_requests_light_1440x900.png)

## 9. System Audit Trail (`8_Audit_Log.py`)
- **One-line purpose:** Tamper-evident, hash-chained operational audit log recording all system events, gate decisions, rollbacks, and configuration edits.
- **Data Sources:** Append-only cryptographic ledger `logs/audit.jsonl` and database `audit_events`.
- **Visual Evidence:** [08_audit_log_light_1440x900.png](file:///Users/sakshamjindal/Desktop/Responsible_Ai/docs/screenshots/after/08_audit_log_light_1440x900.png)

## 10. Model Matrix (`9_Model_Matrix.py`)
- **One-line purpose:** Cross-model evaluation matrix benchmarking regression behavior across local LLMs (`qwen2.5:3b`, `llama3.2:3b`, `gemma2:2b`).
- **Data Sources:** `results/cross_model_evaluation.csv` and local Ollama inference metrics.
- **Visual Evidence:** [09_model_matrix_light_1440x900.png](file:///Users/sakshamjindal/Desktop/Responsible_Ai/docs/screenshots/after/09_model_matrix_light_1440x900.png)

## 11. Panel Lab (`10_Panel_Lab.py`)
- **One-line purpose:** Interactive playground allowing engineers to draft candidate prompt revisions, test live against adversarial inputs, and run instant gate comparisons.
- **Data Sources:** Live Ollama model calls and in-memory test runner with synthetic test generators.
- **Visual Evidence:** [10_panel_lab_light_1440x900.png](file:///Users/sakshamjindal/Desktop/Responsible_Ai/docs/screenshots/after/10_panel_lab_light_1440x900.png)

## 12. Responsible AI Scorecard (`11_Responsible_AI_Scorecard.py`)
- **One-line purpose:** Holistic governance scorecard evaluating fairness across demographic slices, prompt injection safety, and hallucination bounds.
- **Data Sources:** Automated safety test suite `tests/test_responsible_ai.py` and empirical slice metrics.
- **Visual Evidence:** [11_responsible_ai_scorecard_light_1440x900.png](file:///Users/sakshamjindal/Desktop/Responsible_Ai/docs/screenshots/after/11_responsible_ai_scorecard_light_1440x900.png)

## 13. Test Health & Flakiness (`12_Test_Health.py`)
- **One-line purpose:** Monitors test flakiness, variance across seeds, and identifies unstable test cases requiring isolation or quarantine.
- **Data Sources:** Repeated seed runs from database `scores` table.
- **Visual Evidence:** [12_test_health_light_1440x900.png](file:///Users/sakshamjindal/Desktop/Responsible_Ai/docs/screenshots/after/12_test_health_light_1440x900.png)

## 14. Deliverables Verification (`13_Deliverables.py`)
- **One-line purpose:** Interactive compliance checklist verifying that all project deliverables, ADRs, runbooks, and test suites exist and pass checks.
- **Data Sources:** Workspace filesystem inspection and git tree status.
- **Visual Evidence:** [13_deliverables_light_1440x900.png](file:///Users/sakshamjindal/Desktop/Responsible_Ai/docs/screenshots/after/13_deliverables_light_1440x900.png)

## 15. Project Scorecard (`14_Project_Scorecard.py`)
- **One-line purpose:** High-level project scorecard summarizing test suite pass rates, performance benchmarks, and overall system maturity.
- **Data Sources:** Aggregated database metrics and pytest execution reports.
- **Visual Evidence:** [14_project_scorecard_light_1440x900.png](file:///Users/sakshamjindal/Desktop/Responsible_Ai/docs/screenshots/after/14_project_scorecard_light_1440x900.png)

## 16. Human Review Queue (`15_Human_Review.py`)
- **One-line purpose:** Operational queue for domain experts to audit borderline model generations, discordant flips, and calibrate automated LLM judges.
- **Data Sources:** Relational database `human_reviews` table and discordant evaluation traces.
- **Visual Evidence:** [15_human_review_light_1440x900.png](file:///Users/sakshamjindal/Desktop/Responsible_Ai/docs/screenshots/after/15_human_review_light_1440x900.png)

## 17. Environments & Releases (`16_Environments.py`)
- **One-line purpose:** Manages multi-environment baseline deployments (Development, Staging, Production) with release promoting workflows.
- **Data Sources:** Database `environments` and `releases` tables.
- **Visual Evidence:** [16_environments_light_1440x900.png](file:///Users/sakshamjindal/Desktop/Responsible_Ai/docs/screenshots/after/16_environments_light_1440x900.png)
