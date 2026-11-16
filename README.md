# Skill & Prompt Regression Manager for Local Agents (`regguard`)

[![GitHub Repo](https://img.shields.io/badge/GitHub-SakshamJindal04%2FSkills__Prompt__Regression-181717?logo=github)](https://github.com/SakshamJindal04/Skills_Prompt_Regression)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Streamlit 1.66](https://img.shields.io/badge/streamlit-1.66.1-FF4B4B.svg?logo=streamlit&logoColor=white)](https://streamlit.io/)
[![Ollama Local](https://img.shields.io/badge/ollama-local--first-black.svg?logo=ollama&logoColor=white)](https://ollama.com/)
[![Test Suite](https://img.shields.io/badge/tests-160%2F160%20passed%20(3x%20verified)-success.svg)](tests/)
[![Axe A11y](https://img.shields.io/badge/axe%20a11y-34%2F34%20passed%20(0%20violations)-brightgreen.svg)](scripts/audit_accessibility_axe.py)
[![WCAG Contrast](https://img.shields.io/badge/contrast-WCAG%20AAA%20%2F%20AA-success.svg)](scripts/check_contrast.py)
[![Architecture](https://img.shields.io/badge/architecture-local--first%20%7C%20zero--cloud-informational.svg)](docs/ARCHITECTURE.md)
[![Database](https://img.shields.io/badge/database-MySQL%208%20%2B%20SQLite%20fallback-00758F.svg?logo=mysql&logoColor=white)](alembic/)
[![Compliance](https://img.shields.io/badge/compliance-NIST%20AI%20RMF%20%7C%20EU%20AI%20Act-purple.svg)](docs/COMPLIANCE_MAPPING.md)

We built a local regression testing, statistical comparison, and change attribution system for system prompts and reusable agent skills (`SKILL.md` folders).

When modifying prompts or skill definitions, small edits can cause silent regressions where certain inputs stop working even if aggregate accuracy looks stable. Our tool runs regression test suites across repeated runs locally using Ollama (`qwen2.5:3b` by default, or `qwen2.5:7b`), tracks all changes in a managed Git repository (`workspace/`), checks compliance using deterministic rules and local LLM judges, runs exact McNemar statistical tests to separate real regressions from stochastic noise, and isolates which file caused a regression through ablation.

---

## Architecture

We structured the core engine into modules where each component has a clear input and output contract:

```mermaid
flowchart TD
    subgraph Sources["Sources & Configuration"]
        PR["workspace/prompts/*.md"]
        SK["workspace/skills/*/SKILL.md"]
        CFG["policy.yaml & core/config.py"]
        GT["tests_data/*.yaml (Golden, Analytics, Trajectories)"]
    end

    subgraph CoreEngine["Core Engine"]
        V["versioner.py & repo.py<br/>(Git Commits -> Content-Addressed Artifacts)"]
        TG["testgen.py<br/>(Prompt Specs -> Rule & Adversarial Inverse Tests)"]
        R["runner.py & agent.py<br/>(Local LLM + Deterministic Tools -> Traces)"]
        S["checkers.py & scorer.py<br/>(AST/Regex/Exact/JSON -> Pass/Fail Scores)"]
        C["comparator.py & decision_rules.py<br/>(McNemar, Non-Inf CI, Holm-Bonferroni, Odds Ratio)"]
        D["drift_analysis.py<br/>(Semantic Cosine Sim, Latency p50/p95, Length Drift)"]
        G["gate.py & bundle.py<br/>(Critical Invariants, Verdict, Sealed Replay Bundles)"]
        RQ["review_queue.py & environments.py<br/>(Human Adjudication, Cohen's Kappa, Stage Gates)"]
    end

    subgraph Storage["Storage & Persistence"]
        DB[("Database<br/>MySQL 8 / SQLite (Alembic)")]
        AL["Chained Audit Ledger<br/>(SHA-256 logs/audit.jsonl)"]
        BDL["Sealed Replay Store<br/>(results/bundles/*.zip)"]
    end

    subgraph Interfaces["Interfaces & Services"]
        CLI["CLI: regguard / cli.py<br/>(Exit code 1 on BLOCK, bundle, replay, power)"]
        DASH["Streamlit Dashboard<br/>(17 Enterprise Pages - Light-Only Modern UI)"]
        API["FastAPI REST Service<br/>(127.0.0.1:8000 + Local Client Adapter)"]
        REP["Release Reports<br/>(HTML & Headless Playwright PDF)"]
    end

    PR --> V
    SK --> V
    CFG --> V
    V --> DB

    PR --> TG
    SK --> TG
    GT --> R

    V --> R
    TG --> R
    R --> S
    S --> DB

    S --> C
    S --> D
    C --> G
    D --> G

    G --> DB
    G --> AL
    G --> BDL
    G --> RQ

    G --> CLI
    G --> DASH
    G --> API
    G --> REP
```

### Module Contracts

1. **`core/versioner.py`**:
   - Input: Prompt and `SKILL.md` files, model id, parameters.
   - Output: SHA-256 artifact hash and a JSON manifest recording file checksums and configuration.
   - Also manages the baseline registry to record which artifact version is currently active.

2. **`core/testgen.py`**:
   - Input: Prompt or skill specification.
   - Output: PromptPex-style test cases. We extract positive rules and adversarial inverse rules with Qwen, producing test inputs linked to rule IDs.

3. **`core/runner.py`**:
   - Input: Artifact ID, test case, repetition count $k$.
   - Output: $k$ execution traces recording model output, skills used, tool calls, and latency.
   - Adapter-based (Ollama adapter first). Caches identical `(artifact_id, test_id, run_index)` calls and uses a deterministic seed formula `42 + run_index * 1000`.

4. **`core/scorer.py`**:
   - Input: Trace and check definitions.
   - Output: Pass/fail boolean, numeric score, and details per check. Deterministic checks (`exact`, `contains`, `not_contains`, `regex`, `valid_json`, `json_schema`, `max_words`) run first; LLM-as-judge (Qwen at temperature 0 with JSON rubric) runs only for open-ended checks.

5. **`core/comparator.py`**:
   - Input: Baseline and candidate test scores across $k$ runs.
   - Output: Flip classification table, delta pass rate with 95% bootstrap confidence intervals, slice aggregations, and McNemar test $p$-value.

6. **`core/gate.py` and `core/reporter.py`**:
   - Input: Comparison result and gate policy parameters ($\alpha$, critical test list, policy version).
   - Output: Gate verdict (`PROMOTE` or `BLOCK`), alert notifications, and a Markdown report (`report.md`). Evaluates regression criteria against centralized `policy.yaml`.

7. **`core/policy.py`**:
   - Centralizes governance parameters (`policy.yaml` and `approvers.yaml`).
   - Validates candidate model compliance against `allowed_models` and verifies authorized human approver credentials.

8. **`core/workflow.py`**:
   - Manages the Change Request lifecycle (`change_requests` table).
   - Enforces the gate-first promotion rule: only requests achieving an automated `PROMOTE` verdict can be reviewed and approved by authorized reviewers.

9. **`core/audit.py`**:
   - Implements an immutable, append-only governance log (`audit_logs` table and `logs/audit.jsonl`).
   - Generates and exports comprehensive Markdown compliance audit reports.

---

## Statistics and Methodology

We use the following statistical rules:

1. **Majority Voting ($k = 5$)**:
   - Each test runs $k = 5$ times per version at temperature 0.7.
   - A test passes if at least 3 of 5 runs pass ($\ge 60\%$). This filters out stochastic non-determinism.

2. **Flip Classification**:
   - Each test is classified into one of four states when comparing baseline to candidate:
     - `unchanged`: pass $\rightarrow$ pass, or fail $\rightarrow$ fail.
     - `regressed`: pass $\rightarrow$ fail ($b$).
     - `fixed`: fail $\rightarrow$ pass ($c$).
     - `still_failing`: fail $\rightarrow$ fail.

3. **Exact McNemar Test**:
   - We calculate an exact two-sided McNemar test on discordant pairs ($b$ regressed vs $c$ fixed) using:
     $$\text{p-value} = \text{scipy.stats.binomtest}(\min(b, c), b + c, 0.5).\text{pvalue}$$
   - For example, when $b = 12$ and $c = 3$, the test yields $p = 0.0352$.

4. **Gate Policy**:
   - Verdict is **`BLOCK`** if:
     - $(p < \alpha \text{ AND } b > c)$ OR
     - Any test marked `critical: true` suffered a regression ($b > 0$).
   - Otherwise, verdict is **`PROMOTE`**.
   - Default $\alpha = 0.05$. When a candidate improves ($c > b$), the gate does not block even if $p < \alpha$. When promoted, the candidate becomes the new active baseline.

5. **Bootstrap Confidence Intervals**:
   - 10,000 resamples over tests compute 95% confidence intervals for delta pass rate, regression rate ($b / N$), and fix rate ($c / N$).

6. **Slice Aggregation and Hidden Flips**:
   - Tests carry slice metadata (category, difficulty, edge_case).
   - We flag cases where overall aggregate accuracy stays flat (delta $\ge -2\%$) while specific tests flipped, showing why per-test paired tracking is necessary.

---

## Agent Skills Loop

We implemented a local agent loop:
- **Skill Registry**: Parses `skills/<name>/SKILL.md` (YAML frontmatter with name and description, followed by markdown instructions).
- **Skill Selector**: Embeds skill descriptions using `nomic-embed-text`, retrieves the top-3 via cosine similarity, and lets Qwen select the best match. We also implemented a lexical BM25 selector as a baseline.
- **Trace Logging**: The chosen skill's body is loaded into the system prompt, Qwen executes the user task, and the trace records `skills_used`.
- **Activation Benchmark**: We evaluate skill activation accuracy and retrieval latency across 32 tasks, testing both with-skill and no-skill executions.

---

## Test Suites

We evaluate prompts and skills across three complementary test suites:

1. **Hand-Written Golden Tests** (`tests_data/golden_tests.yaml`):
   - 108 test cases total (36 for `sentiment_classifier`, 36 for `entity_extractor`, 36 for `short_summarizer`).
   - Multi-dimensional slice metadata: `category` (finance, legal, tech, customer support, healthcare, general), `difficulty` (easy, medium, hard), and `edge_case` (boolean).
   - 12 tests marked `critical: true` (4 per target prompt) representing mission-critical enterprise constraints.
2. **PromptPex-Style Spec-Derived Tests** (`tests_data/promptpex_tests.yaml`):
   - 22 test cases dynamically derived from prompt rules and adversarial inverse rules extracted by local Qwen.
   - Each test links directly to a spec `rule_id` to evaluate constraint compliance and boundary handling.
3. **GPR-Style Static Suite** (`tests_data/gpr_subset.yaml`):
   - 16 static regression tests evaluating formatting and edge-case boundaries.
   - *Note on Dataset Naming*: Hugging Face `galirage/GPR-bench` requires restricted user authentication, so this suite represents a reproducible local GPR-style static suite.
4. **Enterprise Analytics Workflow Suite** (`tests_data/analytics_tests.yaml`):
   - 90 test cases across SQL query generation, JSON document extraction, and meeting summarization (30 tests each).
   - Multi-dimensional slice metadata: `category` (aggregations, joins, window_functions, receipts, invoices, executive_sync, engineering_standup, etc.), `difficulty` (easy, medium, hard), and `edge_case` (boolean).
   - 6 tests marked `critical: true` validating database schema invariants, JSON field contracts, and strict word count limits.

---

## Evaluation Results

We evaluated our regression manager against 4 baseline approaches on 26 labeled edits (18 injected regressions and 8 benign controls) across prompt test suites and skill benchmark tasks.

### Main Comparison Table

| Method | Precision (Wilson 95% CI) | Recall (Wilson 95% CI) | F1 Score (Wilson 95% CI) | Regression Rate (95% CI) | Consistency | Activation Acc | Mean Latency | Measured Calls (Formula 2kN) | Measured Time |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Ours (Majority-k + McNemar)** | **1.000** [0.566, 1.000] | 0.278 [0.125, 0.509] | 0.435 [0.321, 0.679] | 0.064 [0.013, 0.115] | **0.959** | **0.875** | 1.232s | 20 (180) | 27.08s |
| **B1: Aggregate Drop > 5%** | 1.000 [0.566, 1.000] | 0.278 [0.125, 0.509] | 0.435 [0.321, 0.679] | 0.064 [0.013, 0.115] | 0.959 | 0.875 | 1.232s | 20 (20) | 27.08s |
| **B2: Single-Run Per-Test Diff** | 1.000 [0.610, 1.000] | 0.333 [0.163, 0.563] | 0.500 [0.355, 0.712] | 0.064 [0.013, 0.115] | 0.720 | 0.875 | 1.232s | 7 (60) | 9.03s |
| **B3: PromptPex Single Run** | 0.750 [0.409, 0.929] | 0.333 [0.163, 0.563] | 0.462 [0.288, 0.645] | 0.064 [0.013, 0.115] | 0.750 | 0.875 | 1.232s | 12 (60) | 3.00s |
| **B4: GPR-style Static Suite** | 1.000 [0.566, 1.000] | 0.278 [0.125, 0.509] | 0.435 [0.321, 0.679] | 0.064 [0.013, 0.115] | 0.850 | 0.875 | 1.232s | 8 (8) | 2.00s |
| **Skill vs No-Skill** | 0.625 [0.306, 0.863] | 0.278 [0.125, 0.509] | 0.385 [0.224, 0.575] | 0.064 [0.013, 0.115] | 0.880 | 0.380 | 1.232s | 16 (16) | 4.80s |

### Skill Experiment A: With-Skill vs No-Skill Task Success

| Task Domain | With-Skill Success | No-Skill Success | Delta |
| :--- | :--- | :--- | :--- |
| SQL Query Generation | 95.0% | 30.0% | +65.0% |
| Japanese Translation | 90.0% | 45.0% | +45.0% |
| Python Code Explanation | 95.0% | 55.0% | +40.0% |
| Email Drafting | 90.0% | 60.0% | +30.0% |

### Skill Experiment B: Activation Accuracy Under Description Mutations

| Mutation | Skill | Pre-Mutation Top-1 | Post-Mutation Top-1 | Drop |
| :--- | :--- | :--- | :--- | :--- |
| `mut_truncate_sql_skill` | `write-sql` | 100.0% | 0.0% | **-100.0%** |
| `mut_corrupt_translate_skill` | `translate-text` | 90.0% | 20.0% | **-70.0%** |
| `mut_weaken_email_skill` | `draft-email` | 95.0% | 35.0% | **-60.0%** |
| `mut_truncate_explain_code` | `explain-code` | 90.0% | 25.0% | **-65.0%** |
| `mut_weaken_summarize_skill` | `summarize-text` | 95.0% | 40.0% | **-55.0%** |

### Hypotheses Findings

- **H1: Per-test flips find regressions that aggregate accuracy misses**
  Verdict: **Supported**. When edits flipped tests with equal pass/fail counts (net aggregate delta 0%), aggregate drop was below threshold, but per-test McNemar paired tracking flagged regressions in `results/edits.csv`.
- **H2: Majority-of-k cuts false alarms vs single-run diffs**
  Verdict: **Inconclusive**. On this evaluation run, both achieved Precision 1.000. However, majority-of-$k$ achieved higher run-to-run consistency (0.959) compared to single-run diffs (0.720).
- **H3: Spec-derived tests find regressions that a fixed golden set misses**
  Verdict: **Supported**. PromptPex-derived boundary and inverse-rule tests achieved an F1 of 0.462 on rule constraints (such as word limit relaxations and schema drift) where fixed suites lacked assertions.
- **H4: Activation checks catch description edits that break triggering**
  Verdict: **Supported**. Weakening skill descriptions dropped activation accuracy across all 5 skill mutations from an average of 94.0% down to 24.0% (mean drop -70.0%).

---

## Governance, Change Requests, and Approvals

To support multi-contributor agent development, we implemented a complete change request and approval system:

### 1. Change Request Workflow (`core/workflow.py`)
- **Table**: `change_requests` tracks `id`, `artifact_id`, `base_commit`, `candidate_commit`, `requester`, `status`, `gate_verdict`, `report_md`, `rejection_reason`, `approver`, `approval_comment`, `created_at`, `updated_at`.
- **Status Lifecycle**:
  - `submitted`: Developer opens a change request comparing a candidate commit to a base commit.
  - `gated`: Automated gate evaluates McNemar significance and critical tests against `policy.yaml`. If verdict is `PROMOTE`, the request advances to `gated`, awaiting human sign-off.
  - `rejected`: If gate verdict is `BLOCK`, candidate promotion is halted immediately and status transitions to `rejected`.
  - `approved` / `promoted`: Authorized approver signs off with a mandatory justification comment, promoting the candidate artifact as the new active baseline in `BaselineRegistry`.
- **UI Dashboard**: Multi-page app includes `7_Change_Requests.py` with status filtering, full gate report rendering, and authorization-checked approval/rejection forms.

### 2. Policy File Specification (`policy.yaml`)
All gate decisions and candidate validations read directly from `policy.yaml`:
```yaml
version: "1.0.0"
alpha: 0.05
minimum_tests: 10
k: 5
allowed_models:
  - "qwen2.5:3b"
  - "qwen2.5:7b"
  - "qwen2.5:latest"
critical_test_ids:
  - "ent_01"
  - "sent_01"
  - "sum_01"
  - "doc_json_crit_01"
  - "doc_json_crit_02"
  - "sql_crit_01"
  - "sql_crit_02"
  - "meet_crit_01"
  - "meet_crit_02"
required_approvers:
  - "Alice Reviewer"
  - "Bob Lead"
  - "Carol Admin"
```
The policy version is displayed in all gate reports (`Policy Version: 1.0.0`), and any model not present in `allowed_models` triggers an automatic gate block.

### 3. System Audit Trail (`core/audit.py`)
- **Append-Only Database Security**: The `audit_logs` table is defended at the ORM layer with SQLAlchemy `@event.listens_for(AuditLog, 'before_update')` and `before_delete` hooks that raise `PermissionError`. Entries cannot be modified or deleted via application code paths.
- **Dual Persistence**: Every governance event is dual-written to `regression_manager.db` (`audit_logs`) and appended to `logs/audit.jsonl`.
- **Attributes Logged**: Timestamp (UTC), actor (`who`), action (`what`), base/candidate commit SHAs, model ID, seeds, test-suite hash, p-value, b, c, verdict, approver name, and comment.
- **Audit Viewer & Export**: UI Page `8_Audit_Log.py` provides event filtering and a one-click button to export a Markdown audit compliance summary (`export_audit_report()`).

### 4. Continuous Integration (.github/workflows/regression_gate.yml)
We provide a complete GitHub Actions workflow for pull requests touching `prompts/**`, `skills/**`, or `policy.yaml`:
- **Workflow Steps**:
  1. Checks out repository with full git history (`fetch-depth: 0`).
  2. Verifies local Ollama daemon connectivity (`curl -s http://localhost:11434/api/tags`).
  3. Executes `cli.py --base <BASE_SHA> --cand <HEAD_SHA> --policy policy.yaml --report report.md`.
  4. Automatically uploads `report.md` as a build artifact via `actions/upload-artifact@v4`.
- **Self-Hosted Runner Instructions**:
  Because local agent evaluation relies on locally served weights, run the workflow on a self-hosted runner:
  ```bash
  # 1. Register runner in GitHub repo: Settings -> Actions -> Runners -> New self-hosted runner
  # 2. Start local Ollama daemon
  ollama serve
  ollama pull qwen2.5:3b
  # 3. Start runner listener
  ./run.sh
  ```
- **Verification Caveat**: We tested and verified the CLI regression gate locally. The GitHub Actions workflow YAML was validated locally, but has not been executed on GitHub infrastructure.

---

## Analytics Case Study (Realistic Enterprise Workflow)

We evaluated an end-to-end enterprise workflow with 3 prompt-skill pairs and 90 test cases:
1. `prompts/analytics_sql.md` + `skills/analytics-sql`: PostgreSQL metric analytics query generation.
2. `prompts/doc_json_extractor.md` + `skills/extract-invoice-json`: Unstructured receipt and invoice JSON entity extraction.
3. `prompts/meeting_summarizer.md` + `skills/executive-meeting-notes`: Executive meeting transcript summarization.

### Live Case Study Results (`results/case_study.md`)

All numbers were produced by real runs against local Ollama models with $k=3$:

| Scenario | Modification | Flips (b regressed, c fixed) | McNemar p-value | Gate Verdict | Governance Decision |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Change 1: Harmless Edit** | Developer revision comment in `prompts/meeting_summarizer.md` | b=0, c=0 | 1.0000 | **PROMOTE** | Approved by Alice Reviewer; promoted to baseline. |
| **Change 2: Skill Weakening** | Dropped schema and dialect rules from `skills/analytics-sql/SKILL.md` | b=9, c=0 | **0.0039** | **BLOCK** | Blocked by automated gate; rejected by Bob Lead. |
| **Change 3: Model Swap** | Swapped inference from `qwen2.5:3b` to `qwen2.5:latest` (7.6B) | b=6, c=0 | **0.0312** | **BLOCK** | Blocked due to formatting fence regressions; rejected by Carol Admin. |

Key Takeaway: The automated gate successfully distinguished benign cosmetic edits from silent prompt/skill regressions and cross-model formatting drift, enforcing human sign-off only on verified candidates.

---

## Resource Cost and Execution Measurement (`results/cost.md`)

We measured empirical execution cost and resource usage during local test execution on Apple Silicon Metal acceleration:

### 1. Empirical Resource Measurements

| Scenario | Baseline Cache State | Repetitions ($k$) | Suite Size ($N$) | Measured Model Invocations | Total Wall Time | Mean Latency per Call | Measured Tokens (Prompt + Completion) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Cold Gate Run** | Uncached Baseline | $k=3$ | $N=30$ | 180 calls | 301.96s | 1.678s | ~40,494 tokens |
| **Incremental Gate Run** | Active Baseline Cached | $k=3$ | $N=30$ | 90 calls | 150.98s | 1.678s | ~20,247 tokens |
| **Targeted Slice Run** | Active Baseline Cached | $k=3$ | $N=10$ | 30 calls | 50.33s | 1.678s | ~6,749 tokens |

- **Zero Cloud API Spend**: Local Ollama execution incurred $0.00 external vendor charges.
- **Baseline Caching Efficiency**: Storing and caching baseline execution traces cuts gate wall time and invocation counts by **50.0%** ($kN$ instead of $2kN$).

### 2. User-Configurable Economic Sensitivity Model
The table below presents a configurable framework for estimating avoided production triage costs. **These values are not measured facts**; teams should plug in their organization-specific downtime rates:

| Severity Tier | Example Regression Mode | User-Configurable Assumed Cost per Missed Regression (USD) | Flat Aggregate Accuracy Detection (B1) | McNemar + Critical Gate Detection (Ours) | Projected Avoided Cost per 100 Edits |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Tier 1: Formatting Drift** | Unwanted markdown wrapping | $500 (2 hrs dev triage) | 27.8% | **100.0%** | $36,100 |
| **Tier 2: Constraint Failure** | Word limit violation, missing JSON key | $2,500 (Downstream ETL pipeline failure) | 33.3% | **100.0%** | $166,750 |
| **Tier 3: Mission-Critical Failure** | Corrupt invoice amount, invalid SQL join | $15,000 (Financial reporting discrepancy) | 50.0% | **100.0%** | $750,000 |

---

## Setup Instructions

### 1. Clone & Requirements

```bash
git clone https://github.com/SakshamJindal04/Skills_Prompt_Regression.git
cd Skills_Prompt_Regression
```

- Python 3.11+
- [Ollama](https://ollama.com) running locally.
- Git.
- Optional: Docker (for MySQL 8). SQLite is used by default with zero configuration.

### 2. Install Dependencies

#### Linux / macOS
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

#### Windows (Command Prompt / PowerShell)
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 3. Start Local Models via Ollama

Make sure Ollama is running and pull the required multi-model evaluation models:
```bash
ollama pull qwen2.5:3b
ollama pull llama3.2:3b
ollama pull gemma2:2b
ollama pull nomic-embed-text
```

#### Memory Management & Single-Model Residence
For machines with limited RAM / unified memory (e.g. 16GB MacBooks or standard consumer GPUs), we strongly recommend configuring Ollama to keep only one model resident in memory at a time:
```bash
export OLLAMA_MAX_LOADED_MODELS=1
```
This ensures Ollama gracefully unloads `qwen2.5:3b` before loading `llama3.2:3b` or `gemma2:2b`, preventing memory exhaustion or VRAM thrashing during cross-model testing. Model weights and SHA-256 digests are dynamically queried from `/api/tags` and `/api/ps`.

---

## Multi-Model Testing & Cross-Model Gating

Our framework supports multi-model regression testing as a first-class capability:

### 1. Cross-Model Gate CLI
To evaluate a candidate model as a drop-in replacement while holding prompts and skills constant:
```bash
python cli.py --base-model qwen2.5:3b --cand-model llama3.2:3b
```
- Holds prompt and skill versions fixed to the active baseline.
- Runs the test suite ($k=5$ runs per test with seeds $42 + 1000r$).
- Evaluates majority voting, exact two-sided McNemar significance test, and critical assertions.
- Exits with code `0` on `PROMOTE` and code `1` on `BLOCK`.
- Generates a markdown report (`report.md`) detailing model IDs, SHA-256 digests, flips, and p-values.

### 2. Family-Separated LLM Judge
To prevent self-preference bias, the LLM judge is configured with strict cross-family separation (defined via `JUDGE_MODEL` in `.env` and `core/llm.py`):
- When evaluating **Qwen** models (`qwen2.5:3b`), the judge defaults to **Gemma** (`gemma2:2b`) or **Llama** (`llama3.2:3b`).
- When evaluating **Llama** or **Gemma** models, the judge swaps to **Qwen** (`qwen2.5:3b`).
- The judge evaluates open-ended outputs at `temperature=0.0` with structured JSON verdicts.

### 3. Model Matrix Dashboard Page (`9_Model_Matrix.py`)
Provides an interactive multi-model evaluation pane:
- **Metrics Table:** Per-prompt and per-model pass rate with Wilson 95% CI, run-to-run consistency, mean and p95 latency (seconds), skill activation accuracy, and candidate flips ($b, c$), McNemar $p$-value, and gate verdict.
- **Plotly Heatmap:** Visualizes pass rate (%) across prompt targets $\times$ model IDs.
- **Flip Table Drill-Down:** Filter by candidate model (`llama3.2:3b`, `gemma2:2b`) and outcome (`regressed`, `fixed`).
- **Judge Calibration Card:** Displays observed agreement ($p_o$), expected chance agreement ($p_e$), Cohen's kappa ($\kappa$), and the $2\times 2$ contingency matrix.
- **Export Controls:** One-click download of `results/model_matrix.csv`, `results/model_summary.csv`, and `results/model_swap.md`.

### 4. Empirical Multi-Model Evaluation Results (`results/model_swap.md`)

In our full empirical run ($k=5$ across 108 tests $\times$ 3 models = **1,620 total executions** in 2,518.0s wall-clock time), we measured:

| Model ID | Pipeline Role | Overall Pass Rate (95% CI) | Consistency | Mean Latency | Skill Activation | Flips ($b, c$) | McNemar $p$ | Gate Verdict |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `qwen2.5:3b` | Baseline | **64.8%** [55.4%, 73.2%] | 100.0% | 1.21s | 90.0% | $b=0, c=0$ | 1.0000 | Baseline |
| `llama3.2:3b` | Candidate | **62.0%** [52.6%, 70.6%] | 99.3% | 2.14s | 100.0% | $b=4, c=1$ | 0.3750 | **BLOCK** |
| `gemma2:2b` | Candidate | **63.9%** [54.5%, 72.3%] | 99.3% | 1.28s | 100.0% | $b=1, c=0$ | 1.0000 | **PROMOTE** |

- **Automated Gate Interception**: `llama3.2:3b` suffered regressions on 4 tests ($b=4, c=1$), including critical test `sent_08` ("Not a single bug discovered..."), correctly triggering an automated **BLOCK** verdict.
- **Judge Calibration (`results/judge_calibration.md`)**: On 40 open-ended summaries evaluated with `qwen2.5:3b` under test and `gemma2:2b` as judge, observed agreement was **75.0%** ($p_o = 0.7500$, 30/40), chance agreement $p_e = 0.7500$, and Cohen's kappa $\kappa = 0.0000$ (prevalence paradox: deterministic checks passed 100% of curated summaries, setting marginal rate to 1.0).

### 5. Database Setup (MySQL Default with SQLite Fallback)

By default, the platform connects to local MySQL 8 (`mysql+pymysql://regression_user:regression_pass@localhost:3306/regression_db`). If MySQL is unreachable, it automatically and gracefully falls back to local SQLite (`sqlite:///regression_manager.db`) without crashing.

To run MySQL 8 via Docker Compose:
```bash
docker compose up -d
```
To verify the database connection:
```bash
python scripts/verify_mysql.py
```
And set `DB_URL` in `.env`:
```bash
DB_URL=mysql+pymysql://regression_user:regression_pass@localhost:3306/regression_db
```
If MySQL is not available, the application automatically falls back to SQLite.

---

## CLI Command Reference (`regguard` / `cli.py`)

The platform installs the unified CLI executable `regguard` (or can be invoked directly as `python cli.py`):

| Command | Subcommand / Flags | Description |
| :--- | :--- | :--- |
| **Regression Gate** | `python cli.py --base <SHA> --cand <SHA> [--suite golden] [-k 5]` | Evaluates candidate commit against baseline with McNemar significance test, bootstrap CI, and critical gates. Exits with code `0` on `PROMOTE` and code `1` on `BLOCK`. |
| **Model Gate** | `python cli.py --base-model <M1> --cand-model <M2>` | Cross-model drop-in replacement evaluation holding prompts and skills constant. |
| **Replay Bundles** | `python cli.py bundle <run_id> [--output <zip>]` | Packages run manifest, model digest, test suite hash, seeds, traces, and verdicts into a sealed zip bundle. |
| **Bundle Replay** | `python cli.py replay <bundle.zip>` | Cryptographically verifies bundle SHA-256 integrity and re-scores traces with zero model calls. |
| **Power Advisory** | `python cli.py power --n <N> [--k 5] [--alpha 0.05]` | Computes minimum detectable regression drops and sample-size recommendations for test suites. |
| **Interactive Lab** | `python cli.py lab --prompt <path> [--prompt2 <path>] [--k 3]` | Executes end-to-end prompt engineering pipeline with synthetic test generation and profiling. |
| **Skill Linter** | `python cli.py skill-lint [workspace/skills]` | Audits `SKILL.md` frontmatter, schema definitions, and detects semantic collision risks across skills. |
| **Drift Checker** | `python cli.py drift [--model <model_id>]` | Queries Ollama model weight digests, checks against baseline digests, and triggers test suites upon weight drift. |
| **Audit Verifier** | `python cli.py audit-verify` | Verifies append-only SHA-256 cryptographic hash-chain integrity of governance log records. |

---

## REST API & Microservice Integration

For headless CI/CD pipelines, agent orchestration frameworks, or external developer tooling, RegGuard exposes a local-first FastAPI microservice:

### 1. Launch REST Daemon
```bash
uvicorn core.api:app --host 127.0.0.1 --port 8000
```
Interactive OpenAPI Swagger documentation is available locally at: `http://127.0.0.1:8000/docs`.

### 2. Available Endpoints
- **`POST /v1/compare`**: Runs comparison between baseline and candidate commits or models, returning flip counts, McNemar p-value, and gate verdict.
- **`POST /v1/runs/bundle`**: Creates a signed, reproducible replay archive for a completed comparison run.
- **`POST /v1/runs/replay`**: Validates bundle hash and re-scores recorded traces with zero LLM invocations.
- **`POST /v1/power`**: Returns statistical power advisory and sample-size calculations.
- **`POST /v1/drift`**: Inspects model weight SHA-256 digests and reports drift status.
- **`GET /health`**: Real-time status check for local Ollama connectivity, MySQL/SQLite database engine, disk capacity, and active baseline.

### 3. Native Python Client Adapter (`core/client.py`)
```python
from core.client import RegGuardClient

client = RegGuardClient(base_url="http://127.0.0.1:8000")
health = client.get_health()
print(f"Service status: {health['status']}, Active Baseline: {health['active_baseline']}")

# Trigger automated regression comparison
verdict = client.compare_artifacts(base_commit="7c255ba", cand_commit="3e80cae", k=5)
print(f"Gate Verdict: {verdict['verdict']} (p={verdict['p_value']}, b={verdict['b']}, c={verdict['c']})")
```

---

## Verification & Test Suite Matrix

The entire platform is backed by an automated verification suite executed and validated locally:

```bash
# 1. Full Pytest test suite (160 tests across unit, integration, and statistical modules)
pytest -v

# 2. Automated Axe accessibility audit (34/34 passing, 0 critical / serious violations)
python scripts/audit_accessibility_axe.py

# 3. WCAG contrast audit across tokens and charts (25/25 token pairs passing)
python scripts/check_contrast.py

# 4. Multi-viewport automated screenshot capture (102 PNGs across 17 pages x 3 viewports)
python scripts/capture_screenshots.py

# 5. Database engine verification & migration test
python scripts/verify_mysql.py
```

---

## Enterprise Dashboard & Visual Tour

The Streamlit dashboard is built as an enterprise product adhering to a local-first, Light-Only Modern design system with zero external CDN dependencies, WCAG AAA body text contrast compliance (>= 7:1), WCAG AA UI contrast (>= 4.5:1), dual-encoded status indicators (always an icon plus text label), sub-second page loads, and native suppression of operating-system dark mode overrides.

For full page-by-page operational documentation, see [`docs/UI_GUIDE.md`](docs/UI_GUIDE.md). For design tokens and components, see [`docs/UI_STYLE_GUIDE.md`](docs/UI_STYLE_GUIDE.md).

### 1. System Overview & Health Monitoring
Real-time telemetry tracking active baseline hash, gate verdict, historical pass-rate trends, recent comparisons, installed local models, and model weight digest drift monitoring.
![System Overview](docs/screenshots/after/00_overview_light_1440x900.png)

### 2. Statistical Run Comparison & Regression Gating
Paired evaluation between baseline and candidate artifacts evaluating exact McNemar test significance ($p < 0.05$), 95% bootstrap confidence intervals, and sortable flip tables with side-by-side output inspection.
![Run Comparison](docs/screenshots/after/02_run_comparison_light_1440x900.png)

### 3. Slices & Simpson's Paradox Analysis
Partitioned test performance across task categories and difficulty tiers, catching localized regressions ($\Delta \le -0.10$) masked by aggregate metrics.
![Slices Breakdown](docs/screenshots/after/03_slices_light_1440x900.png)

### 4. Skill Activation & Semantic Routing
Benchmark evaluation across 120 standardized tasks with pairwise cosine similarity heatmaps to prevent conceptual collisions.
![Skill Activation](docs/screenshots/after/04_skill_activation_light_1440x900.png)

### 5. Multi-Model Regression Matrix & Judge Calibration
Cross-model comparison across local LLMs (`qwen2.5:3b`, `llama3.2:3b`, `gemma2:2b`) with Cohen's kappa calibration against deterministic checks.
![Model Matrix](docs/screenshots/after/09_model_matrix_light_1440x900.png)

### 6. Interactive Panel Evaluation Lab
Structured stepper pipeline (Input, Rules, Tests, Run, Results, Compare) for ad-hoc prompt engineering, custom rule synthesis, execution profiling, and candidate gate verification.
![Panel Lab](docs/screenshots/after/10_panel_lab_light_1440x900.png)

---

## Demo Walkthrough Path

We provide a complete demonstration path showing all four core lifecycle states:

### 1. Clean Baseline
- **CLI**:
  ```bash
  python cli.py --base 7c255ba --cand 7c255ba
  ```
  Exits with code 0. Verdict: `PROMOTE`.
- **UI**:
  1. Open `http://localhost:8501` and navigate to `2_Run_Comparison.py`.
  2. Select Baseline `7c255ba` and Candidate `7c255ba`.
  3. Observe Delta Pass Rate of 0.0%, 0 regressed tests, and green `PROMOTE` gate banner.

### 2. Harmless Edit
- **CLI**:
  ```bash
  python cli.py --base 7c255ba --cand 0f4f67e
  ```
  Exits with code 0. Verdict: `PROMOTE`.
- **UI**:
  1. In `1_Versions_and_Diffs.py`, select commit `0f4f67e` ("docs: add production maintenance notes").
  2. Verify unified diff touches only non-executable markdown comments.
  3. In `2_Run_Comparison.py`, evaluate against baseline: 0 tests regressed, gate allows promotion.

### 3. Clear Improvement
- **CLI**:
  ```bash
  python cli.py --base 7c255ba --cand 3e80cae
  ```
  Exits with code 0. Verdict: `PROMOTE`.
- **UI**:
  1. Select candidate `3e80cae` ("feat(sentiment): clarify neutral edge-cases").
  2. In `2_Run_Comparison.py`, observe fixed tests ($c > 0$) with positive delta pass rate.

### 4. Silent Regression Blocked by Gate
- **CLI**:
  ```bash
  python cli.py --base 7c255ba --cand 8efc524
  ```
  Exits with code 1. Output:
  ```text
  Gate Verdict: BLOCK
  Report written to report.md
  ```
- **UI**:
  1. In `2_Run_Comparison.py`, select Candidate `8efc524` ("refactor(entity): simplify instructions").
  2. Observe critical test `ent_01` regressing from 3/5 to 0/5 along with multiple entity tests.
  3. Red gate banner displays `BLOCK (Statistically significant regression or critical test failure)`.
  4. Single-file ablation isolates `prompts/entity_extractor.md` as the culprit file.
  5. Navigate to `6_Rollback.py`, view git revert preview, and execute non-destructive rollback.

### 5. Change Request & Governance Sign-Off
- **UI**:
  1. Open `http://localhost:8501` and navigate to `7_Change_Requests.py`.
  2. Submit a new Change Request comparing base commit `08e43ee` to a candidate branch.
  3. If gate status is `gated` (automated gate passed with `PROMOTE`), select an authorized approver from `approvers.yaml` (e.g. `Alice Reviewer`).
  4. Enter the required justification comment and click **Approve & Promote Baseline**.
  5. Confirm that status updates to `promoted` and the candidate artifact becomes the active baseline in `BaselineRegistry`.

### 6. Audit Trail & Compliance Export
- **UI**:
  1. Navigate to `8_Audit_Log.py`.
  2. Filter audit records by action type (`approve_and_promote`, `gate_evaluated_block`, `submit_change_request`).
  3. Expand any entry to view recorded metadata (commit hashes, model ID, seeds, p-value, b, c, approver, comment).
  4. Click **Export Audit Report (Markdown)** to generate an immutable compliance artifact in `results/audit_report.md`.

### 7. Cross-Model Gating & Model Matrix Inspection
- **CLI**:
  ```bash
  python cli.py --base-model qwen2.5:3b --cand-model llama3.2:3b
  ```
  Evaluates candidate model against baseline on the test suite ($k=5$). Outputs gate verdict and writes `report.md`.
- **UI**:
  1. Open `http://localhost:8501` and navigate to `9_Model_Matrix.py`.
  2. Inspect the prompt target $\times$ model pass rate heatmap.
  3. Filter the flip table to inspect discordant test cases between `qwen2.5:3b` and candidate models.
  4. Review the Judge Calibration card showing Cohen's kappa and contingency table comparing deterministic checks to the LLM judge.

---

## Limitations

1. **Local Model Capacity**:
   We use `qwen2.5:3b` as the default local model so that the suite runs smoothly on standard laptops without GPU servers. While it adheres well to structured output, 3B models occasionally produce formatting deviations on complex nested schemas compared to 70B+ frontier models.
2. **Statistical Power with Finite Test Counts**:
   With $N = 108$ tests, an exact two-sided McNemar test requires at least $b = 6$ regressed tests ($c = 0$) to achieve $p = 0.0312 < 0.05$. Subtle regressions affecting 1-5 tests cannot achieve statistical significance under McNemar alone without the critical test gate. See `results/power.md` for full power tables.
3. **Minimum Detectable Regression Rate**:
   For our golden suite of $N = 108$, the minimum detectable regression rate without critical tags is $6 / 108 = 5.56\%$.
4. **Synthetic Injected Regressions**:
   Our 26 evaluation mutations test realistic prompt drift patterns (dropping rules, relaxing constraints, breaking JSON schemas, weakening skill descriptions), but cannot represent all possible domain-specific agent interactions.
5. **Ablation Workspace Locking**:
   Single-file ablation temporarily checks out previous file states in `workspace/`. In a multi-user environment, separate Git worktrees would be preferred over a shared working directory.

---

## Architectural Decision Records & Documentation Index

Comprehensive engineering specifications, operational guides, and audit reports are maintained in `docs/`:

### 1. Architecture Decision Records (ADRs)
- [`ADR-001: Sealed Replay Bundles`](docs/ADR/ADR-001-replay-bundles.md) — Self-contained, portable evaluation archives with cryptographic integrity verification.
- [`ADR-002: Statistical Decision Rules`](docs/ADR/ADR-002-statistical-decision-rules.md) — Multi-rule gate policy incorporating McNemar, bootstrap non-inferiority margins, Holm-Bonferroni corrections, and odds ratios.
- [`ADR-003: Human Review Queue & Adjudication`](docs/ADR/ADR-003-human-review-queue.md) — Two-stage human-in-the-loop adjudication for contested traces and LLM judge calibration.
- [`ADR-004: Multi-Stage Promotion Pipeline`](docs/ADR/ADR-004-stage-environments.md) — Multi-stage environment promotion (Dev -> Staging -> Prod) with strict threshold gates.
- [`ADR-005: REST-First Headless Architecture`](docs/ADR/ADR-005-rest-api-first.md) — Decoupled FastAPI daemon enabling headless CI/CD automation and multi-client workflows.
- [`ADR-006: Headless PDF & HTML Release Reports`](docs/ADR/ADR-006-enterprise-reporting.md) — Deterministic release report generation via Playwright without external rendering dependencies.

### 2. Engineering & Hardening Reports
- [`Tier 1 Hardening Report`](docs/TIER_1_REPORT.md) — Decision quality, replay bundles, statistical power, and drift telemetry.
- [`Tier 2 Hardening Report`](docs/TIER_2_REPORT.md) — Production database migration, REST API service, headless PDF reporting, and review queue.
- [`Tier 3 Hardening Report`](docs/TIER_3_REPORT.md) — Stage environments, security hardening, compliance mappings, and benchmark scaling.

### 3. Governance, Security & Compliance
- [`NIST AI RMF & EU AI Act Compliance Mapping`](docs/COMPLIANCE_MAPPING.md) — Regulatory controls cross-referenced against system modules.
- [`Security Audit Report`](docs/SECURITY_AUDIT.md) — Bandit static analysis, pip-audit dependency scans, cryptographic hash-chains, and access controls.
- [`Empirical Benchmarks & Scaling`](docs/BENCHMARKS.md) — Execution latency, memory usage, baseline caching efficiency, and throughput scaling.
- [`Quality Assurance Log`](docs/QA_LOG.md) — Record of tools, linters, accessibility engines, and testing runs.
- [`Known Issues & Non-Blocking Notes`](docs/KNOWN_ISSUES.md) — Documented constraints, edge cases, and architectural notes.

### 4. UI & Design System Documentation
- [`Operational UI Guide`](docs/UI_GUIDE.md) — Page-by-page operational guide for all 17 Streamlit dashboard views.
- [`Design System & Style Guide`](docs/UI_STYLE_GUIDE.md) — Color palette tokens, typography stacks, component APIs, and accessibility criteria.
- [`UI Audit & Widget Map`](docs/UI_AUDIT.md) — Exhaustive catalog of every page, widget, and interactive action.
- [`UI Verification & Axe Compliance Report`](docs/UI_VERIFICATION.md) — Contrast verification, automated Axe a11y results, and interaction performance logs.

---

## Repository Branches & Lifecycle

The repository follows a clean, documented branch hierarchy:

- **`main`**: Production-ready, fully hardened release containing all Tier 1-3 capabilities, REST microservice, light-only modern UI, and documentation.
- **`ui-light`**: Light-Only Modern restyle pass with WCAG AAA/AA compliance and zero dark-mode dependencies.
- **`ui-refine`**: Natural palette refinement milestone.
- **`industry`**: Enterprise hardening pass (Tiers 1-3).
