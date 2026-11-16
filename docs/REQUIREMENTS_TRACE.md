# Requirements Traceability Matrix

This matrix maps every functional requirement, core metric, project deliverable, expansion capability, and governance rule to its concrete implementation file, function, and verification command.

---

## 1. Project Sheet Core Requirements

| Requirement | Implementation File & Function | Verification Command | Status |
| :--- | :--- | :--- | :--- |
| **Versioned repository for prompts and skills** | `core/repo.py`: `init_repo()`, `commit_changes()`, `list_versions()`, `get_diff()` | `pytest tests/test_repo.py tests/test_repo_extended.py -v` | Complete |
| **Automatic regression tests after every change** | `core/runner.py`: `run_test()`, `core/scorer.py`: `score_artifact_runs()` | `pytest tests/test_runner_unit.py tests/test_scorer.py -v` | Complete |
| **Identification of which change improved or degraded performance** | `core/attribution.py`: `ablate_and_attribute()`, `ablate_prompt_sections()`, `auto_bisect()` | `pytest tests/test_attribution.py tests/test_ablation.py -v` | Complete |
| **Change governance & approvals** | `core/workflow.py`: `submit_change_request()`, `approve_change_request()`, `policy.yaml` | `pytest tests/test_governance.py tests/test_workflow_extended.py -v` | Complete |
| **Skill selection & routing** | `core/skills.py`: `SkillRegistry`, `EmbeddingSelector`, `try_task_routing` | `pytest tests/test_skills.py tests/test_skills_extended.py -v` | Complete |
| **Reproducibility** | Fixed random seeds ($s=42+1000r$), pinned digests, `policy.yaml`, `results/environment.md` | `python scripts/check_docs_numbers.py` | Complete |
| **Rollback workflow** | `core/repo.py`: `revert_commit()`, `core/workflow.py`: `request_governed_rollback()` | `pytest tests/test_integration_git_flow.py -v` | Complete |
| **Evidence-based maintenance** | `core/audit.py`: `record_audit_event()`, `export_audit_report()`, `logs/audit.jsonl` | `pytest tests/test_audit_chain.py -v` | Complete |

---

## 2. Advanced Expansion Modules

| Expansion Module | Core Implementation | Interface / CLI | Verification Command | Status |
| :--- | :--- | :--- | :--- | :--- |
| **A. Panel Lab** | `core/lab.py`: `run_lab_pipeline()` | `cli.py lab`, `app/pages/10_Panel_Lab.py` | `pytest tests/test_panel_lab.py -v` | Complete |
| **B. Static Quality & Safety Lint** | `core/lint.py`: `lint_prompt()`, `lint_skill()` | `cli.py skill-lint`, `app/pages/1_Versions_and_Diffs.py` | `pytest tests/test_lint.py -v` | Complete |
| **C. Test Families & Responsible AI** | `core/responsible_ai.py`, `tests_data/analytics_tests.yaml` (210 tests) | `app/pages/11_Responsible_AI_Scorecard.py` | `pytest tests/test_responsible_ai.py -v` | Complete |
| **D. Skill Intelligence (12 Skills & Benchmark)** | `core/skills.py`: `compute_skill_overlap_matrix()`, `benchmark_scalability()` | `app/pages/4_Skill_Activation.py` | `pytest tests/test_skills.py -v` | Complete |
| **E. Test Health & Flakiness** | `core/health.py`: `analyze_test_health()` | `app/pages/12_Test_Health.py` | `pytest tests/test_flakiness.py -v` | Complete |
| **F. Model Drift Monitor** | `core/drift.py`: `check_model_drift()` | `cli.py drift`, `scripts/scheduled_drift_check.sh` | `pytest tests/test_drift.py -v` | Complete |
| **G. Governance & Hash Chaining** | `core/audit.py`: `verify_audit_hash_chain()`, `core/workflow.py` | `cli.py audit-verify`, `app/pages/7_Change_Requests.py` | `pytest tests/test_audit_chain.py -v` | Complete |
| **H. Section-Level Ablation** | `core/attribution.py`: `ablate_prompt_sections()` | `core/attribution.py`, `app/pages/2_Run_Comparison.py` | `pytest tests/test_ablation.py -v` | Complete |
| **I. Model Roles & Resource Limits** | `models.yaml`, `core/llm.py`: `unload_model()` | `core/llm.py`, `scripts/verify_env.py` | `python scripts/verify_env.py` | Complete |
| **J. Project Scorecard & Deliverables** | `app/pages/13_Deliverables.py`, `app/pages/14_Project_Scorecard.py` | Streamlit Dashboard Pages 13 & 14 | `pytest tests/test_streamlit_pages.py -v` | Complete |

---

## 3. The Five Evaluation Metrics

| Metric | Definition | Implementation Function | Verification Command / Output | Status |
| :--- | :--- | :--- | :--- | :--- |
| **1. Skill-selection accuracy** | Top-1 and Top-3 accuracy on routing user queries to matching skills | `core/skills.py`: `run_skill_benchmark()` | `python -c "import yaml; from core.skills import run_skill_benchmark; print(run_skill_benchmark(yaml.safe_load(open('tests_data/skill_benchmarks.yaml'))['benchmarks'][:10]))"` | Complete (87.5% Overall) |
| **2. Task success before/after change** | Absolute pass rate change ($\Delta$) with bootstrap 95% confidence intervals | `core/comparator.py`: `compare_test_results()`, `bootstrap_ci()` | `pytest tests/test_comparator.py -v` | Complete |
| **3. Regression detection recall** | Fraction of true regressions detected under noise / flat aggregate rates | `core/comparator.py`: `mcnemar_test()`, `scripts/evaluate_baselines.py` | `python -c "import pandas as pd; print(pd.read_csv('results/summary.csv')[['Method', 'Recall']])"` | Complete (Ours: 0.278 [0.125, 0.509]) |
| **4. Consistency over repeated runs** | Fraction of test cases yielding identical verdicts across all $k=5$ runs | `core/health.py`: `analyze_test_health()` | `pytest tests/test_flakiness.py -v` | Complete (Ours: 95.9%) |
| **5. Retrieval latency** | Wall-clock latency per evaluation in seconds (mean, p50, p95) | `core/llm.py`: `generate()`, `core/skills.py`: `select()` | `python scripts/verify_live.py` | Complete (Vector: 1.2 ms, Keyword: 0.4 ms) |

---

## 4. The Five Deliverables

| Deliverable | Description | Implementation Artifact | Verification Command | Status |
| :--- | :--- | :--- | :--- | :--- |
| **1. Skill Repository** | Directory structure for prompts and `SKILL.md` folders with YAML frontmatter | `workspace/prompts/*.md`, `workspace/skills/*/SKILL.md` (12+ skills) | `python cli.py skill-lint` | Complete |
| **2. Test Runner** | Multi-model local test execution engine with majority voting and caching | `core/runner.py`, `core/llm.py` | `pytest tests/test_runner_unit.py -v` | Complete |
| **3. Version Comparison Dashboard** | Streamlit multi-page interface with flip tables, heatmaps, and model matrix | `app/Home.py`, `app/pages/*.py` (14 pages) | `pytest tests/test_streamlit_pages.py -v` | Complete |
| **4. Rollback Workflow** | Governed Git revert pipeline with separation-of-duties enforcement | `core/workflow.py`: `request_governed_rollback()`, `app/pages/6_Rollback.py` | `pytest tests/test_integration_git_flow.py -v` | Complete |
| **5. Documented Best Practices** | Empirical guidelines for prompt engineering, model selection, and governance | `docs/BEST_PRACTICES.md`, `results/` | `python scripts/check_docs_numbers.py` | Complete |

---

## 5. Technology Stack Compliance

| Stack Component | Specified Requirement | Concrete Implementation | Verification Command | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Python** | Python 3.11+ | Python 3.12.14 (`.venv`) | `python --version` | Complete |
| **Local LLMs** | Ollama with `qwen2.5:3b`, `llama3.2:3b`, `gemma2:2b` | Local Ollama daemon (`http://localhost:11434`), `core/llm.py` | `curl -s http://localhost:11434/api/tags` | Complete |
| **Embeddings** | `nomic-embed-text` via Ollama | `core/llm.py`: `embed()`, `core/skills.py` | `pytest tests/test_live_ollama.py::test_live_ollama_embeddings` | Complete |
| **Versioning** | GitPython managing `workspace/` | `core/repo.py`, `workspace/.git` | `git -C workspace status` | Complete |
| **Database** | MySQL 8 with graceful SQLite fallback | `core/db.py`, `docker-compose.yml`, `regression_db` on port 3306 | `python scripts/verify_mysql.py` | Complete |
| **Web UI** | Streamlit multi-page application | `app/Home.py` + 14 sub-pages in `app/pages/` | `pytest tests/test_streamlit_pages.py -v` | Complete |
| **Statistics** | `scipy.stats.binomtest`, `numpy` | `core/comparator.py`: McNemar exact, bootstrap CIs, Wilson score intervals | `pytest tests/test_comparator.py -v` | Complete |
| **Visualizations** | Plotly charts and heatmaps | `plotly.graph_objects`, `plotly.express` across pages 3, 4, 9, 10 | `pytest tests/test_streamlit_pages.py` | Complete |
| **Tests** | pytest test suite with coverage | `pytest` test harness with 117 tests and `pytest-cov` | `pytest --cov=core --cov-report=term-missing` | Complete (81% coverage) |
