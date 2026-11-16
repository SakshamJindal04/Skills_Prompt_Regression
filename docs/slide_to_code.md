# Presentation Slide to Code Mapping

This document maps the architectural concepts, data structures, and algorithms from the project slide deck to their concrete implementations in this repository.

---

## Slide 1: Motivation & The Silent Regression Problem
- **Slide Concept**: In agent pipelines, small prompt tweaks or model swaps break downstream tasks silently. Flat aggregate accuracy hides paired flips.
- **Code Mapping**:
  - `core/comparator.py`: `compare_test_results()` detects paired flips where overall rate is unchanged but individual tests regressed ($b > 0, c > 0$).
  - `tests/test_comparator.py`: `test_hidden_flips_flat_aggregate()` proves that flat aggregate accuracy masks localized test failure.
  - `results/summary.csv`: Empirical comparison showing baseline B1 (aggregate drop) achieves only 27.8% recall on silent regressions.

---

## Slide 2: High-Level Pipeline Architecture
- **Slide Concept**: The 6-stage core engine: Versioner $\rightarrow$ TestGen $\rightarrow$ Runner $\rightarrow$ Scorer $\rightarrow$ Comparator $\rightarrow$ Gate & Reporter.
- **Code Mapping**:
  - Stage 1: `core/versioner.py`: `hash_content()`, `build_manifest()`.
  - Stage 2: `core/testgen.py`: `extract_prompt_rules()`, `generate_tests_for_rules()`.
  - Stage 3: `core/runner.py`: `run_test()`, `execute_agent_loop()`.
  - Stage 4: `core/scorer.py`: `score_trace()`, `score_artifact_runs()`.
  - Stage 5: `core/comparator.py`: `compare_test_results()`, `mcnemar_test()`.
  - Stage 6: `core/gate.py`: `evaluate_gate()`, `run_gate_pipeline()`.
  - Reporter: `core/reporter.py`: `generate_markdown_report()`.

---

## Slide 3: Versioning & Content-Addressable Artifacts
- **Slide Concept**: Git-backed `workspace/` containing prompts and skills, hashed deterministically into immutable artifact records.
- **Code Mapping**:
  - `core/repo.py`: Git operations (`init_repo`, `commit_changes`, `list_versions`, `get_diff`, `revert_commit`).
  - `core/models.py`: `Artifact`, `Version`, `BaselineRegistry`.
  - Storage: Content addressable hashing in `core/versioner.py` using SHA-256 over files, model ID, and generation parameters.

---

## Slide 4: Multi-Model Evaluation & Cross-Model Gating
- **Slide Concept**: Evaluating candidate models (`llama3.2:3b`, `gemma2:2b`) against baseline (`qwen2.5:3b`) with model digest verification.
- **Code Mapping**:
  - `models.yaml`: Central specification of baseline, candidates, judge model, and embeddings.
  - `core/llm.py`: Live model discovery via Ollama `/api/tags` and `/api/ps`, extracting 64-char SHA-256 digests.
  - `core/gate.py`: `run_cross_model_gate()` holding prompt versions fixed and evaluating model swaps.
  - CLI: `cli.py --base-model qwen2.5:3b --cand-model llama3.2:3b`.
  - UI: `app/pages/9_Model_Matrix.py`.

---

## Slide 5: Statistical Rigor: McNemar Test & Bootstrap CIs
- **Slide Concept**: Paired binary hypothesis testing. McNemar's exact test for discordance; bootstrap resampling for confidence intervals.
- **Code Mapping**:
  - `core/comparator.py`: `mcnemar_test(b, c)` using `scipy.stats.binomtest(min(b, c), b + c, 0.5)`.
  - `core/comparator.py`: `bootstrap_confidence_interval(base_outcomes, cand_outcomes, n_resamples=1000)` computing empirical 95% CIs.
  - `core/comparator.py`: `wilson_score_interval()` for binomial proportions.

---

## Slide 6: Governance, Change Requests & Approvals
- **Slide Concept**: Production baselines cannot be updated without automated gate clearance and human authorization.
- **Code Mapping**:
  - `policy.yaml`: Machine-readable policy (`alpha: 0.05`, `critical_test_ids`, `allowed_models`, `required_approvers`).
  - `approvers.yaml`: Authorized personas (`Alice Reviewer`, `Bob Lead`, `Carol Admin`).
  - `core/workflow.py`: `submit_change_request()`, `run_change_request_gate()`, `approve_change_request()`.
  - UI: `app/pages/7_Change_Requests.py`.

---

## Slide 7: Immutability & Audit Trail
- **Slide Concept**: Every regression test, comparison, approval, and rollback must be recorded in an append-only log.
- **Code Mapping**:
  - `core/models.py`: `AuditLog` table with SQLAlchemy `@event.listens_for(AuditLog, 'before_update')` and `before_delete` raising `PermissionError`.
  - `core/audit.py`: `record_audit_event()`, `get_audit_logs()`, `export_audit_report()`.
  - File Persistence: Dual-written to `logs/audit.jsonl`.
  - UI: `app/pages/8_Audit_Log.py`.

---

## Slide 8: Change Attribution & Non-Destructive Rollback
- **Slide Concept**: Automated ablation isolates the guilty file; Git revert creates a forward commit restoring baseline behavior.
- **Code Mapping**:
  - `core/attribution.py`: `ablate_and_attribute()` isolating changed files and ranking by recovery delta.
  - `core/attribution.py`: `auto_bisect()` traversing historical commit ranges.
  - `core/repo.py`: `revert_commit()` invoking Git revert to produce a non-destructive recovery commit.
  - UI: `app/pages/6_Rollback.py`.


---

## Slide 9: Reproducibility Bundles & Offline Replay
- **Slide Concept**: Cryptographically sealed test execution archives that allow offline verification with zero model calls.
- **Code Mapping**:
  - `core/bundle.py`: `create_run_bundle()`, `replay_run_bundle()`, `BundleTamperedError`.
  - CLI: `regguard bundle <run_id>`, `regguard replay <bundle_zip>`.
  - UI: `app/pages/2_Run_Comparison.py` ("Verify Run (Replay Bundle)").

---

## Slide 10: Beyond Pass/Fail Multi-Dimensional Drift
- **Slide Concept**: Detecting semantic, latency, and verbosity regressions that pass binary functional assertions.
- **Code Mapping**:
  - `core/drift_analysis.py`: `analyze_beyond_pass_fail()`, `compute_percentiles()`, `bootstrap_diff_ci()`.
  - Embeddings: Pairwise cosine similarity using local `nomic-embed-text`.
  - Latency: $p_{50}$ and $p_{95}$ bootstrap difference confidence intervals.

---

## Slide 11: Agent Trajectory Tests & Invariant Checkers
- **Slide Concept**: Evaluating multi-step tool-using agents against deterministic local tools and behavioral invariants.
- **Code Mapping**:
  - `core/agent.py`: `tool_calculator`, `tool_doc_lookup`, `tool_db_query`, `run_agent_trajectory()`.
  - Checkers: `tool_called`, `no_loops`, `max_steps`, `valid_arguments` in `core/checkers.py`.
  - Test Suite: 40 trajectory tests in `tests_data/agent_trajectory_tests.yaml`.

---

## Slide 12: Human Review Queue & Inter-Rater Reliability
- **Slide Concept**: Human-in-the-loop oversight for ambiguous or contentious outputs, with Cohen's kappa calibration.
- **Code Mapping**:
  - `core/review_queue.py`: `enqueue_review_item()`, `submit_human_review()`, `compute_cohens_kappa()`.
  - Audit Trail: Immutable logging of score overrides in `logs/audit.jsonl`.
  - UI: `app/pages/15_Human_Review.py`.

---

## Slide 13: Local REST API & Plugin Architecture
- **Slide Concept**: Headless integration via FastAPI REST service and decoupled extension points for models and checks.
- **Code Mapping**:
  - `core/api.py`: FastAPI endpoints (`/gate`, `/runs`, `/runs/{id}`, `/review`, `/health`, `/metrics`).
  - `core/api_client.py`: Dual-mode client adapter switching between direct calls and REST.
  - `core/plugins.py`: `@register_model_provider` and `@register_check`.

---

## Slide 14: Local Role-Based Access Control & Security Confinement
- **Slide Concept**: Multi-role permission enforcement with zero cloud dependencies and strict directory traversal confinement.
- **Code Mapping**:
  - `core/auth.py`: PBKDF2 HMAC-SHA256 hashed credentials, `ROLE_PERMISSIONS` (`author`, `reviewer`, `admin`), `check_action_permitted()`.
  - `core/security.py`: `safe_resolve_path()`, `safe_load_yaml()`, `PathTraversalError`.
