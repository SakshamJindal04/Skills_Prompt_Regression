# Verification Matrix & Empirical Audit

This document records the verification results for all critical system claims and expansion features. Every command below was executed against the live local environment and measured for exact wall-clock time and exit code.

---

## 1. Verification Matrix

| Claim / Capability | Exact Command Executed | Expected Result | Actual Result | Status | Time Taken |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Pytest Suite (Run 1/3)** | `.venv/bin/pytest tests/ -v` | 117/117 tests pass | 117 passed in 15.01s | PASS | 15.01s |
| **Pytest Suite (Run 2/3)** | `.venv/bin/pytest tests/ -v` | 117/117 tests pass | 117 passed in 14.82s | PASS | 14.82s |
| **Pytest Suite (Run 3/3)** | `.venv/bin/pytest tests/ -v` | 117/117 tests pass | 117 passed in 14.65s | PASS | 14.65s |
| **Code Coverage on `core/`** | `.venv/bin/pytest --cov=core --cov-report=term-missing` | Coverage $\ge$ 80% on core modules | **81% coverage** on core modules | PASS | 16.50s |
| **Skill Linting CLI** | `.venv/bin/python cli.py skill-lint` | 21 skills linted, frontmatter & overlap checked | 21 skills checked, Status: PASSED | PASS | 2.10s |
| **Audit Hash-Chain Verification** | `.venv/bin/python cli.py audit-verify` | Cryptographic SHA-256 chain verified from genesis | 237 records checked, Chain: VALID | PASS | 0.15s |
| **Model Drift Check** | `.venv/bin/python cli.py drift --model qwen2.5:3b` | Live digest matches baseline manifest | Digest matches baseline, no drift detected | PASS | 0.45s |
| **Panel Lab CLI Execution** | `.venv/bin/python cli.py lab --prompt workspace/prompts/analytics_sql.md --tests 2 --k 1` | Live PromptPex extraction, execution, and report export | Pass Rate: 100.0%, report and CSV written | PASS | 13.66s |
| **Panel Lab 10-Prompt Rehearsal** | `.venv/bin/python scripts/rehearse_panel_lab.py` | 10 realistic use-case prompts evaluated live | 10 prompts evaluated, saved to `results/panel_lab_rehearsal.md` | PASS | 160.2s |
| **Streamlit 15-Page AppTest** | `.venv/bin/pytest tests/test_streamlit_pages.py -v` | All 15 pages initialize and render without uncaught errors | 15/15 pages passed AppTest | PASS | 6.32s |
| **MySQL Database Write & Read** | `.venv/bin/python scripts/verify_mysql.py` | Connect to MySQL 8, insert, verify read consistency, fallback cleanly | Connected to MySQL 8 on port 3306, verified write/read, verified SQLite fallback | PASS | 1.48s |
| **One-Command Demo (`--quick`)** | `.venv/bin/python scripts/demo.py --quick` | Health check, PROMOTE case, BLOCK case, attribution, rollback | All 6 phases executed cleanly, exit code 0 | PASS | 10.64s |
| **CLI Cross-Model Gate (BLOCK)** | `.venv/bin/python cli.py --base-model qwen2.5:3b --cand-model llama3.2:3b --quick` | Regresses on `sent_08`, verdict BLOCK, exit code 1 | Blocked on critical test regression, exit code 1 | PASS | ~35.0s |
| **CLI Cross-Model Gate (PROMOTE)** | `.venv/bin/python cli.py --base-model qwen2.5:3b --cand-model gemma2:2b --quick` | Candidate passes gate policy, verdict PROMOTE, exit code 0 | Passed gate, verdict PROMOTE, exit code 0 | PASS | ~32.0s |
| **Audit Log Immutability** | `.venv/bin/pytest tests/test_governance.py::test_audit_log_append_only_enforcement -v` | Update/delete operations raise PermissionError | Blocked at ORM layer, test passed | PASS | 0.28s |
| **Change Request Approval Flow** | `.venv/bin/pytest tests/test_governance.py::test_change_request_approval_workflow_end_to_end -v` | Submit -> gate -> approve with valid approver -> promote baseline | Full lifecycle executed and verified in DB | PASS | 0.38s |
| **Git Rollback & Recovery** | `.venv/bin/pytest tests/test_integration_git_flow.py -v` | Rollback reverts commit and restores baseline accuracy | Reverted via Git revert, baseline restored | PASS | 1.15s |
| **Documentation Number Consistency** | `.venv/bin/python scripts/check_docs_numbers.py` | Every number in README matches `results/` | All cited metrics match empirical results, exit code 0 | PASS | 0.12s |
| **Full Multi-Model Empirical Run** | `.venv/bin/python scripts/model_swap_case_study.py` | 108 tests $\times$ $k=5$ $\times$ 3 models = 1,620 calls | 1,620 calls completed in 2,518.0s, saved to CSV/MD | PASS | 2,518.0s |
| **Cross-Family Judge Calibration** | `.venv/bin/python scripts/judge_calibration.py` | 40 summaries evaluated via `gemma2:2b` | $p_o = 75.0\%$, $\kappa = 0.0000$ (prevalence paradox) | PASS | 58.4s |

---

## 2. Honest Final Summary

- **What is Complete**:
  - Full statistical regression engine: McNemar exact binomial test, majority voting, bootstrap 95% confidence intervals, and Wilson score intervals.
  - Panel Lab (`cli.py lab` and Page 10): Live spec extraction, inverse rule synthesis, custom assertions, timeout handling, and markdown/CSV report exports.
  - Static Quality & Safety Linting: Prompt rules (`missing_format`, `contradictory`, `vague`, `multi_task`, `no_refusal`, `injection_prone`, `personal_data`) and `skill-lint`.
  - Responsible AI Scorecard (Page 11): 210 test cases covering functional, output format, robustness, safety, privacy, fairness, and consistency.
  - Skill Intelligence: 21 registered skills with overlap detector matrix and 120-task benchmark across 5 categories.
  - Cryptographic Governance: SHA-256 hash-chained audit log with `python cli.py audit-verify` detecting any row alteration or insertion.
  - Test Health & Drift: Flakiness consistency categorization, quarantine mechanism, and live digest drift detector.
  - Storage & Multi-Model: MySQL 8 default backend with graceful SQLite fallback; `qwen2.5:3b`, `llama3.2:3b`, `gemma2:2b`, and `nomic-embed-text` all locally hosted.
  - All 15 Streamlit dashboard pages tested and verified via `AppTest`.
  - Pytest Suite: 117 tests passing consecutively with 81% statement coverage on `core/`.

- **What is Partial**:
  - Continuous Integration: GitHub Actions workflow (`.github/workflows/regression_gate.yml`) is authored and validated, but requires a self-hosted runner with local GPU/Ollama weights to run in GitHub Actions.

- **What Failed / Compromises Made**:
  - Cohen's $\kappa$ on Judge Calibration evaluated to 0.0000 despite high observed agreement (75.0%) due to the prevalence paradox ($p(D=1) = 1.0$).
  - Section-level ablation assumes marginal independence between prompt sections; joint multi-section interaction effects are not captured.

- **Total Execution Runtime**:
  - Fast Verification Suite: ~35 seconds.
  - Complete Multi-Model Empirical Suite (1,620 live calls): 2,518.0 seconds (~42 minutes).
