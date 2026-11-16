# Presenter Demo Script: Skill & Prompt Regression Manager for Local Agents

This document provides a step-by-step walkthrough script for presenting the prototype to the company evaluation panel. All commands and metrics referenced here are 100% reproducible and run on local hardware with zero external API calls.

---

## 1. Executive Summary & Problem Setup (2 Minutes)

### Presenter Talking Points
> *"In agentic systems, prompt and skill adjustments are routinely treated like harmless text edits. But in practice, prompt changes cause silent regressions: an edit that improves summarization conciseness can destroy entity extraction or break valid JSON formatting. Furthermore, teams often swap local models (e.g., from Qwen 3B to Llama 3B) assuming bigger is better, only to find critical prompt instructions ignored.*
>
> *Today we present the **Skill & Prompt Regression Manager for Local Agents**: a fully local, version-controlled testing harness that uses Git versioning, exact McNemar hypothesis testing, multi-model evaluation, and an append-only change governance pipeline to prevent degraded prompts and skills from reaching production."*

---

## 2. Environment & Database Check (1 Minute)

### Command
```bash
python scripts/verify_mysql.py
```

### What the Audience Sees
1. Connection to local **MySQL 8** (`regression_db`).
2. Schema verification across 11 relational tables (`artifacts`, `test_cases`, `traces`, `scores`, `comparisons`, `change_requests`, `audit_logs`, etc.).
3. Read-after-write transaction proof.
4. Automatic graceful fallback to **SQLite** (`sqlite:///regression_manager.db`) when MySQL is unreachable.

---

## 3. One-Command Live Demonstration (3 Minutes)

### Command
```bash
make demo-quick
# or: python scripts/demo.py --quick
```

### Checkpoints for the Audience
1. **Ollama & Models Verification**:
   - Queries Ollama daemon (`http://localhost:11434`) and prints real SHA-256 digests for `qwen2.5:3b`, `llama3.2:3b`, `gemma2:2b`, and `nomic-embed-text`.
2. **Case 1: Baseline Clean Candidate (PROMOTE)**:
   - Evaluates a compliant candidate against active baseline.
   - Flip table: $b=0$ regressed, $c=0$ fixed ($p=1.0000$).
   - Verdict: **PROMOTE**.
3. **Case 2: Silent Regression Candidate (BLOCK)**:
   - Evaluates candidate with critical failure on assertion `demo_t2`.
   - Flip table: $b=1$ regressed ($p < \alpha$ or critical regression).
   - Verdict: **BLOCK** (automated gate intercepts the regression).
4. **Case 3: Change Attribution via Ablation**:
   - Runs automated ablation to isolate which file caused the regression.
   - Pinpoints culprit file: `prompts/sentiment.md`.
5. **Case 4: Git Rollback & Recovery**:
   - Executes non-destructive `revert_commit`.
   - Confirms pass rate restored to 100.0%.

---

## 4. Multi-Model Testing & Cross-Model Gating (3 Minutes)

### Command
```bash
python cli.py --base-model qwen2.5:3b --cand-model llama3.2:3b --quick
```

### Presenter Talking Points
> *"Here we test model replacement without touching prompts or skills. We hold prompt templates fixed and swap the underlying LLM from Qwen2.5:3b to Llama3.2:3b.*
>
> *Notice the result: CLI exits with code **1** (`BLOCK`). Why? Because Llama3.2 fails test `sent_08` ('Not a single bug discovered...'), classifying it as NEUTRAL instead of POSITIVE. Our policy marks `sent_08` as critical, so the candidate is blocked from deployment automatically."*

### Key Comparison Metrics
- `qwen2.5:3b`: 64.8% pass rate, 1.21s latency, 100% consistency.
- `llama3.2:3b`: 62.0% pass rate, 2.14s latency, 4 regressed tests ($b=4, c=1$), Verdict: **BLOCK**.
- `gemma2:2b`: 63.9% pass rate, 1.28s latency, 1 regressed test ($b=1, c=0$), Verdict: **PROMOTE**.

---

## 5. Streamlit Interactive Dashboard Walkthrough (4 Minutes)

### Command
```bash
streamlit run app/Home.py
```

### Tour of Dashboard Pages
1. **Home (`Home.py`)**:
   - Live Models Panel showing loaded VRAM models via `/api/ps`, active baseline ID, and policy version (`1.0.0`).
2. **Repository (`1_Repository.py`)**:
   - Git commit history, file viewer for `prompts/*.md` and `skills/<name>/SKILL.md`.
3. **Run Tests (`2_Run_Tests.py`)**:
   - Select artifact, choose $k=3$ or $k=5$, execute test suite live with real progress bar.
4. **Compare Versions (`3_Compare_Versions.py`)**:
   - Baseline vs Candidate flip table ($b$ regressed in red, $c$ fixed in green), McNemar $p$-value, bootstrap 95% CIs.
5. **Slice Heatmap (`4_Slice_Heatmap.py`)**:
   - Visualizes pass rates across difficulty slices and edge-case tags.
6. **Skill Selection (`5_Skill_Selection.py`)**:
   - Evaluates BM25 vs Embedding vs Embedding+LLM top-1 and top-3 accuracy and latency percentiles (p50/p95).
7. **Rollback (`6_Rollback.py`)**:
   - Change attribution ablation ranking and one-click Git revert with non-destructive commit creation.
8. **Change Requests (`7_Change_Requests.py`)**:
   - Governance queue: review gate reports, sign off with approver authorization check (`approvers.yaml`) and mandatory comments.
9. **Audit Log (`8_Audit_Log.py`)**:
   - Append-only compliance log with export to Markdown (`results/audit_report.md`).
10. **Model Matrix (`9_Model_Matrix.py`)**:
    - Heatmap of prompt target $\times$ model ID, Wilson 95% CIs, latency percentiles, and cross-family judge calibration card (Cohen's $\kappa$).

---

## 6. Panel Q&A Guide & Defensible Answers

### Q: Why McNemar's Test instead of a standard Student's t-test or Wilcoxon?
> **Answer**: *Tests on identical inputs before and after a change are inherently **paired binary outcomes** (pass/fail). Student's t-test assumes continuous normal distributions, and Wilcoxon assumes ordinal rankings. McNemar's test specifically models the discordance counts ($b$ regressions vs $c$ fixes), which directly answers: 'Is the frequency of newly broken tests significantly higher than newly fixed tests?'*

### Q: Why is Cohen's kappa 0.0000 in your judge calibration?
> **Answer**: *This is an honest manifestation of the **prevalence paradox** (Cicchetti & Feinstein). On our 40 curated test summaries, the deterministic rules passed 100% of samples ($p=1.0$). When marginal prevalence is extreme, expected chance agreement $p_e$ equals observed agreement $p_o$ ($75.0\%$), driving $\kappa$ to 0.0 despite 75% raw concordance. We document this phenomenon rather than masking it.*

### Q: How does the system prevent unauthorized baseline updates?
> **Answer**: *Candidates cannot self-promote. The gate verdict only transitions a Change Request to 'gated'. Promotion requires an explicit human sign-off from an authorized principal listed in `approvers.yaml`. Every action is dual-written to an append-only database table and `logs/audit.jsonl` protected against updates and deletes.*

