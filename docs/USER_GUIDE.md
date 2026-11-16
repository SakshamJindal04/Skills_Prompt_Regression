# User Guide: Streamlit Dashboard Walkthrough

The Skill & Prompt Regression Manager provides a 10-page Streamlit multi-page interface. This guide details the purpose, workflow, and controls for each page.

To launch the dashboard:
```bash
make run-app
# or: streamlit run app/Home.py
```

---

## 1. Home Page (`Home.py`)
- **Purpose**: System health monitor and executive overview.
- **Key Elements**:
  - **Sidebar System Status**: Real-time indicator for Ollama daemon status (`ONLINE` / `OFFLINE`), active database engine (`MYSQL` / `SQLITE`), current baseline ID, and active policy version (`1.0.0`).
  - **Live Models Panel**: Displays all models detected in Ollama via `/api/tags`, their parameter counts, quantization formats, short SHA-256 digests, and currently resident VRAM models via `/api/ps`.
  - **Quick Action Links**: Direct navigation buttons to Run Tests, Compare Versions, and Change Requests.

---

## 2. Repository (`1_Repository.py`)
- **Purpose**: Version control explorer for the managed `workspace/` repository.
- **Workflow**:
  1. Inspect the chronological Git commit history with author names, timestamps, and commit messages.
  2. Browse managed prompt markdown files (`workspace/prompts/*.md`) and skill definitions (`workspace/skills/<name>/SKILL.md`).
  3. Select two commits from dropdown selectors to render side-by-side unified Git diffs.

---

## 3. Run Tests (`2_Run_Tests.py`)
- **Purpose**: Execute regression test suites against specific prompt/skill versions.
- **Workflow**:
  1. Select a target version or artifact from the dropdown menu.
  2. Choose test suite (`golden`, `analytics`, or all).
  3. Select number of repetitions ($k=3$ for quick testing, $k=5$ for production gating).
  4. Click **Run Test Suite**. Watch the real-time progress bar.
  5. Inspect the resulting overall pass rate, consistency percentage, and latency breakdown.

---

## 4. Compare Versions (`3_Compare_Versions.py`)
- **Purpose**: Paired statistical comparison between a candidate artifact and active baseline.
- **Workflow**:
  1. Select Baseline Artifact and Candidate Artifact.
  2. The page renders:
     - **Summary Metrics**: Baseline pass rate, candidate pass rate, $\Delta$ pass rate with bootstrap 95% CI.
     - **Statistical Significance**: Number of regressed tests ($b$), fixed tests ($c$), and exact two-sided McNemar $p$-value.
     - **Flip Table**: Itemized list of changed test outcomes with status badges (`REGRESSED` in red, `FIXED` in green).
     - **Automated Gate Verdict**: `PROMOTE` or `BLOCK` according to `policy.yaml`.
  3. Download the full comparison table as CSV.

---

## 5. Slice Heatmap (`4_Slice_Heatmap.py`)
- **Purpose**: Granular performance analysis across slice tags and difficulty strata.
- **Workflow**:
  1. Select an evaluation run from history.
  2. The page renders Plotly heatmaps grouping test pass rates by:
     - Target prompt/skill.
     - Difficulty (`easy`, `medium`, `hard`).
     - Edge-case flag (`true` vs `false`).
     - Rule category.
  3. Identifies localized regressions masked by aggregate numbers.

---

## 6. Skill Selection (`5_Skill_Selection.py`)
- **Purpose**: Benchmark skill routing accuracy and retrieval latency across three selector strategies.
- **Workflow**:
  1. Select selector algorithms to benchmark:
     - **BM25**: Keyword frequency matching.
     - **Embedding**: Dense cosine similarity via `nomic-embed-text`.
     - **Embedding + LLM**: Two-stage dense retrieval with local LLM re-ranking.
  2. Click **Run Benchmark**.
  3. Compare Top-1 Accuracy, Top-3 Accuracy, and latency distribution percentiles (mean, p50, p95).

---

## 7. Rollback & Attribution (`6_Rollback.py`)
- **Purpose**: Root-cause analysis and automated rollback of breaking changes.
- **Workflow**:
  1. Select a regressed commit.
  2. Click **Run Attribution Ablation**. The system isolates each changed file in Git, runs the test suite, and measures performance recovery delta.
  3. The page identifies the culprit file (e.g., `prompts/sentiment.md` caused a 15.4% drop).
  4. Click **Revert Commit**. The system executes a non-destructive `git revert`, commits the recovery, and restores baseline integrity.

---

## 8. Change Requests (`7_Change_Requests.py`)
- **Purpose**: Formal governance queue for proposed prompt and model changes.
- **Workflow**:
  1. Submit a change request specifying base commit, candidate commit, and requester name.
  2. The automated gate evaluates McNemar significance and critical tests against `policy.yaml`.
  3. If verdict is `PROMOTE`, the request advances to `gated`.
  4. An authorized approver listed in `approvers.yaml` inputs an approval justification comment and clicks **Approve & Promote**.
  5. The candidate is promoted as the new active production baseline.

---

## 9. Audit Log (`8_Audit_Log.py`)
- **Purpose**: Immutable compliance trail for enterprise auditing.
- **Workflow**:
  1. Filter records by action type (`submit_change_request`, `gate_evaluation`, `approve_and_promote`, `revert_commit`) or verdict.
  2. Inspect timestamp (UTC), actor, commit hashes, model digest, and approval justifications.
  3. Click **Export Audit Report** to download an audit compliance report in Markdown (`results/audit_report.md`).

---

## 10. Model Matrix (`9_Model_Matrix.py`)
- **Purpose**: Multi-model regression evaluation and cross-family judge calibration.
- **Workflow**:
  1. View the comprehensive summary table comparing `qwen2.5:3b`, `llama3.2:3b`, and `gemma2:2b`.
  2. Inspect Wilson 95% confidence intervals on pass rates, run consistency, and mean/p95 latency.
  3. Review the Plotly heatmap of pass rates across prompt target $\times$ model ID.
  4. Review the **Judge Calibration Card**: observed agreement ($p_o = 75.0\%$), Cohen's $\kappa = 0.0000$ (prevalence paradox), and $2\times 2$ confusion matrix.
  5. Download `results/model_matrix.csv` and `results/model_swap.md`.

