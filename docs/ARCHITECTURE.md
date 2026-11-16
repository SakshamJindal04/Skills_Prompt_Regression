# System Architecture & Module Contracts

The Skill & Prompt Regression Manager is designed as a modular pipeline for testing, comparing, and governing local language models, prompts, and agent skills.

---

## 1. High-Level System Architecture

```mermaid
flowchart TD
    subgraph Sources ["1. Source Workspace"]
        P["prompts/*.md"]
        S["skills/<name>/SKILL.md"]
        M["models.yaml"]
        T["tests_data/*.yaml"]
    end

    subgraph CoreEngine ["2. Core Pipeline Engine"]
        V["Versioner (core/versioner.py)"]
        TG["Test Generator (core/testgen.py)"]
        R["Runner (core/runner.py)"]
        SC["Scorer (core/scorer.py)"]
        C["Comparator (core/comparator.py)"]
        G["Gate & Reporter (core/gate.py)"]
    end

    subgraph Storage ["3. Storage & Governance Layer"]
        DB[("MySQL 8 / SQLite")]
        TR[("Trace Cache Store")]
        BR[("Baseline Registry")]
        AL[("Append-Only Audit Log")]
        CR[("Change Requests Queue")]
    end

    subgraph Presentation ["4. User & Automation Interfaces"]
        CLI["Gate CLI (cli.py)"]
        UI["Streamlit Dashboard (app/Home.py)"]
        CI[".github/workflows/regression_gate.yml"]
    end

    Sources --> V
    Sources --> TG
    V --> R
    TG --> R
    R --> TR
    TR --> SC
    SC --> DB
    DB --> C
    C --> G
    G --> CR
    CR --> BR
    G --> AL
    G --> Presentation
```

---

## 2. Module Input/Output Contracts & Failure Modes

### 1. `core/versioner.py`
- **Purpose**: Creates deterministic, content-addressable artifact IDs for prompts, skills, and model configurations.
- **Input**:
  - `file_contents`: Dictionary mapping relative file paths to string contents.
  - `model_id`: String identifier of target LLM (e.g. `qwen2.5:3b`).
  - `params`: Generation parameters dictionary (temperature, seed, commit SHA).
- **Output**:
  - `artifact_hash`: 64-character SHA-256 hexadecimal string.
  - `manifest`: JSON dictionary containing file hashes, parameter dictionary, and timestamp.
- **Failure Modes & Recovery**:
  - Missing file or unreadable encoding: falls back to UTF-8 replacement chars (`errors="replace"`).
  - Duplicate registration: database unique constraints gracefully resolve by returning existing artifact ID.

---

### 2. `core/testgen.py`
- **Purpose**: Generates checkable output rules and adversarial boundary tests (PromptPex-style) from prompt specifications.
- **Input**:
  - `prompt_text`: Raw prompt template text.
  - `client`: `OllamaClient` instance (optional, defaults to `default_client`).
- **Output**:
  - Rule specification JSON containing `input_spec` and list of `rules` (each with `id`, `description`, `check_type`, and `parameter`).
  - Test cases list containing standard compliance tests and inverse adversarial counter-tests.
- **Failure Modes & Recovery**:
  - LLM unavailable or JSON parse error: falls back to deterministic rule extraction based on heuristic keywords (`json`, `words`, `positive`).

---

### 3. `core/runner.py`
- **Purpose**: Executes test cases against specific artifacts across $k$ runs with fixed seeds and trace caching.
- **Input**:
  - `artifact_id`: Integer primary key of target artifact.
  - `test_case`: Dictionary containing test input, target prompt/skill, and assertions.
  - `k`: Number of repetitions (default 5, quick mode 3).
  - `model_id`: Model name to invoke.
- **Output**:
  - List of $k$ trace dictionaries: `{output, latency_ms, seed, model, model_digest, skills_used}`.
- **Failure Modes & Recovery**:
  - Ollama offline: returns empty output, logs error, and marks trace with failed latency. Failed calls are **never** counted as passes.
  - Trace cache hit: reads cached execution from DB, avoiding redundant LLM computation ($kN$ savings).

---

### 4. `core/scorer.py`
- **Purpose**: Evaluates model outputs against rule-based and LLM-as-judge checks.
- **Input**:
  - `trace`: Trace dictionary with model output.
  - `checks`: List of check dictionaries (`exact_match`, `contains`, `not_contains`, `regex`, `json_schema_valid`, `max_words`, `llm_judge`).
- **Output**:
  - Score dictionary: `{"passed": bool, "score": float, "check_details": list}`.
- **Failure Modes & Recovery**:
  - Malformed regex: logs error and marks check as failed.
  - Invalid JSON output for JSON check: returns `passed=False` with error details.
  - LLM judge error: falls back to neutral fail with `passed=False`.

---

### 5. `core/comparator.py`
- **Purpose**: Performs statistical comparison between baseline and candidate test outcomes.
- **Input**:
  - `test_cases`: List of test definitions.
  - `base_runs_map`: Dict mapping `test_id` to list of boolean pass/fail outcomes across $k$ baseline runs.
  - `cand_runs_map`: Dict mapping `test_id` to list of boolean pass/fail outcomes across $k$ candidate runs.
  - `k`: Runs count for majority voting threshold ($\lfloor k/2 \rfloor + 1$).
- **Output**:
  - Comparison dictionary:
    - `b` (regressed count) and `c` (fixed count).
    - `p_value`: Exact two-sided binomial p-value via `scipy.stats.binomtest(min(b, c), b + c, 0.5)`.
    - `delta_pass_rate`: Candidate pass rate minus baseline pass rate.
    - `ci_delta`, `ci_regression_rate`: Bootstrap 95% percentile confidence intervals (1,000 resamples).
    - `flip_table`: Itemized list of per-test outcome flips (`regressed`, `fixed`, `unchanged`, `still_failing`).
- **Failure Modes & Recovery**:
  - Zero flips ($b+c=0$): returns $p=1.0000$ and zero confidence intervals.

---

### 6. `core/gate.py` & `core/reporter.py`
- **Purpose**: Enforces policy gates (`policy.yaml`), decides candidate admission (`PROMOTE` / `BLOCK`), and outputs audit-ready Markdown reports.
- **Input**:
  - `comparison`: Dictionary output from `comparator.py`.
  - `policy`: Loaded configuration (`alpha`, `critical_test_ids`, `allowed_models`).
- **Output**:
  - `verdict`: String (`PROMOTE` or `BLOCK`).
  - `report_md`: Complete GitHub Flavored Markdown report (`report.md`).
- **Policy Rule**:
  $$\text{Verdict} = \begin{cases} \text{BLOCK} & \text{if } (p < \alpha \land b > c) \lor \text{any critical test regressed} \\ \text{PROMOTE} & \text{otherwise} \end{cases}$$

---

### 7. Storage Layer: MySQL 8 with SQLite Fallback (`core/db.py`)
- **Primary Backend**: MySQL 8.0 on `localhost:3306` with connection pooling and pre-ping (`mysql+pymysql://regression_user:regression_pass@localhost:3306/regression_db`).
- **Fallback Backend**: SQLite 3 file database (`sqlite:///regression_manager.db`).
- **Switching Strategy**: When initializing `get_engine()`, the driver attempts a test ping (`SELECT 1`). Upon catching `sqlalchemy.exc.OperationalError` (e.g., MySQL daemon stopped or Docker down), it logs a warning and creates an engine binding to the local SQLite file without raising an unhandled exception.

