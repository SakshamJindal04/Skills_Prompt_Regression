# Repository Audit: Simulated vs Real Execution

This document details the audit of simulation, mocked components, synthetic traces, and shared values in the codebase, along with the concrete remediation performed to ensure all results are real and reproducible.

## 1. Inventory of Simulated or Mocked Artifacts Found

### 1.1 `scripts/run_evaluation.py`
- **Issue**: Synthetic regression and flip rates:
  - `b_reg = 12 if "drop_rule" in cat ... else 6`
  - `c_fix = 1`
  - `b_reg = 1 if (hash(eid) % 3 == 0) else 0`
- **Issue**: Hardcoded latencies and consistency:
  - Latencies generated via `128.0 + (hash(eid) % 30)` rather than measured wall-clock execution.
  - Consistencies copied across baselines (`0.92`, `0.74`, `0.85`).
- **Issue**: Cost approximated by formula (`2 * k * n`) rather than counting actual model invocations and elapsed time.
- **Issue**: Skill activation penalty hardcoded (`0.42`) for no-skill baseline rather than evaluating task outcome with no-skill prompt.

### 1.2 `scripts/seed_demo.py`
- **Issue**: Pseudo-random pass/fail determination:
  - `h = (hash(f"{sha}_{tid}_{r_idx}") % 100) / 100.0; passed = h < base_p`
- **Issue**: Hardcoded canned strings for outputs (`"POSITIVE"`, `"I found these entities: Sample."`, etc.) rather than genuine completions from `qwen2.5:3b`.
- **Issue**: Synthetic pseudo-random latencies (`85.0 + hash(...) % 70`).

### 1.3 `tests/test_scorer.py`
- **Issue**: Mocked LLM client (`MagicMock`) for judge test without a corresponding live integration test against the local Ollama instance.

### 1.4 Baseline B4 and Dataset Honesty
- **Issue**: `tests_data/gpr_subset.yaml` was named after Hugging Face `galirage/GPR-bench`. Verification confirmed that `galirage/GPR-bench` returns HTTP 401 (gated authentication required). Per prompt instructions, this must be honestly classified and named `GPR-style static suite` across all code, tests, and documentation.

### 1.5 Statistical Discrepancies
- **Issue**: Lingering references to Wilcoxon signed-rank and Mann-Whitney U tests from legacy design in `core/compare.py`, `tests/test_compare.py`, and `docs/REPORT_TABLES.md`.

---

## 2. Remediation Plan and Concrete Actions

1. **Delete Contradictory Modules**:
   - Deleted `core/compare.py` and `tests/test_compare.py`.
   - Removed `docs/REPORT_TABLES.md` and old `docs/evaluation_*.csv`.
   - Verified via repository grep that only exact two-sided McNemar and bootstrap CIs are used.

2. **Live Ollama Execution in Runner and Evaluation**:
   - Rewrote `scripts/run_evaluation.py` to invoke Ollama (`qwen2.5:3b`) live for prompts and `nomic-embed-text` for embeddings.
   - Recorded real wall-clock latency per call in seconds using `time.perf_counter()`.
   - Tracked actual model calls and wall-clock times per check alongside the theoretical formula.
   - Evaluated B1, B2, B3, B4, and Skill vs No-Skill with independent measurements (no copied values).

3. **Live Verification Script (`scripts/verify_live.py`)**:
   - Added script executing 5 live tests across 5 repetitions each against Ollama `qwen2.5:3b`.
   - Prints raw model outputs, exact latencies in seconds, and per-run pass/fail results.

4. **Expanded Golden Test Suite**:
   - Expanded golden test suite in `tests_data/golden_tests.yaml` to $\ge 100$ test cases across the 3 prompts (`sentiment_classifier`, `entity_extractor`, `short_summarizer`).
   - Flagged at least 4 critical tests per prompt (12+ critical tests total).

5. **Diagnostic Logging and Statistical Power**:
   - Generated `results/edits.csv` logging per-edit flipped test counts ($b$ regressed, $c$ fixed), sample sizes, and McNemar $p$-values.
   - Created `results/power.md` analyzing minimum detectable regression rates under exact two-sided McNemar for $N \ge 100$ tests.
   - Replaced naive bootstrap intervals on binary outcomes with Wilson 95% score intervals for precision, recall, and F1.

6. **Dataset Honesty**:
   - Renamed baseline B4 to "GPR-style static suite" everywhere.

