# System Card: Skill & Prompt Regression Manager for Local Agents

## 1. System Overview & Intended Use

The Skill & Prompt Regression Manager for Local Agents is a local-first software engineering tool designed to track, benchmark, and govern versioned prompts and reusable agent skills. In production AI agent systems, modifying a system prompt or adjusting a skill description frequently induces unexpected behavioral regressions across existing tasks. 

Our system treats prompt engineering and agent skill authoring with the same rigor as traditional software development:
- Every prompt and skill (`SKILL.md`) is versioned in a local Git repository.
- Changes undergo automated pre-merge regression testing against deterministic test suites and boundary-case tests.
- Re-runs ($k \ge 3$) are executed locally to capture sampling non-determinism.
- Candidate artifacts are compared against production baselines using exact non-parametric McNemar hypothesis tests and 10,000-sample bootstrap confidence intervals.
- Promotions require separation-of-duties sign-off from authorized approvers, recording all decisions into a cryptographically hash-chained audit log.

### Intended Use Cases
- Local development and evaluation of system prompts for extraction, SQL generation, classification, and summarization.
- Continuous integration gates preventing deployment of regressed prompts or broken skill triggering descriptions.
- Cross-model capability comparisons (e.g., evaluating migration from Qwen 2.5 3B to Llama 3.2 3B or Gemma 2 2B).
- Auditing local LLM behavior against Responsible AI standards (fairness parity, injection defense, refusal compliance, PII redaction).

### Out-of-Scope Uses
- Hosted, cloud-dependent agent orchestration requiring external third-party API keys (our system enforces Local-First: Yes).
- Subjective stylistic evaluation without grounded ground-truth rules or deterministic criteria.
- Autonomous, unmoderated promotion of unvalidated models directly to live customer-facing environments.

---

## 2. Hardware & Software Requirements

- **Operating System**: macOS (Apple Silicon / Intel), Linux (x86_64, aarch64), or Windows 10/11 (WSL2 / native Python).
- **CPU & Memory**: Minimum 8 GB RAM (16 GB recommended for multi-model loading).
- **GPU Acceleration**: Metal (macOS MPS), CUDA (NVIDIA), or CPU AVX2 instructions.
- **Runtime Dependencies**:
  - Python 3.11+
  - Local Ollama daemon running on `http://localhost:11434`
  - MySQL 8 database (via Docker or local install) with automatic zero-configuration fallback to SQLite (`sqlite:///regression_manager.db`)
  - Git 2.30+

### Pinned Model Registry
All models run locally via Ollama with zero external telemetry:
- **Default Agent Model**: `qwen2.5:3b` (Q4_K_M quantization, context window 32,768)
- **Candidate Models**: `llama3.2:3b` (Q4_K_M, context window 131,072), `gemma2:2b` (Q4_0, context window 8,192)
- **Embedding Model**: `nomic-embed-text` (F16, context window 2,048, 768 dimensions)
- **Cross-Family Judge Model**: `gemma2:2b` for Qwen outputs; `qwen2.5:3b` for Gemma/Llama outputs

---

## 3. Architecture & Data Flow

```
                      +-----------------------------+
                      |   Managed Git Workspace     |
                      | workspace/prompts/*.md      |
                      | workspace/skills/*/SKILL.md |
                      +--------------+--------------+
                                     |
                                     v
                        +-------------------------+
                        |  Static Quality Linter  |
                        |     (core/lint.py)      |
                        +------------+------------+
                                     |
                                     v
                        +-------------------------+
                        | Test Generation Engine  |
                        |    (core/testgen.py)    |
                        +------------+------------+
                                     |
                                     v
                        +-------------------------+
                        | Local Execution Runner  | <---> Local Ollama
                        |    (core/runner.py)     |       (localhost:11434)
                        +------------+------------+
                                     |
                                     v
                        +-------------------------+
                        | Deterministic Scorer    |
                        |    (core/scorer.py)     |
                        +------------+------------+
                                     |
                                     v
                        +-------------------------+
                        | Exact McNemar Gate      |
                        |  (core/comparator.py)   |
                        +------------+------------+
                                     |
                                     v
                        +-------------------------+
                        | Governance & Approvals  | ---> MySQL 8 / SQLite
                        |   (core/workflow.py)    |      Hash-Chained Audit Log
                        +-------------------------+
```

### Component Breakdown
1. **`core/versioner.py` & `core/repo.py`**: Manages Git commits, hash identification, and unified diff inspection.
2. **`core/lint.py`**: Deterministic static checks verifying explicit output formats, lack of contradictions, prompt injection vulnerability, refusal instructions, and valid YAML frontmatter.
3. **`core/runner.py`**: Executes $k$ independent runs per test with fixed per-run seeds (`42 + run_index * 1000`) and wall-clock latency measurement.
4. **`core/scorer.py`**: Deterministic assertion evaluation (`contains`, `not_contains`, `exact_match`, `regex`, `valid_json`, `max_words`) with cross-family LLM judge calibration.
5. **`core/comparator.py`**: McNemar exact test calculating binomial $p$-values over paired test outcomes ($b$ regressed vs $c$ fixed), accompanied by 10,000-resample bootstrap confidence intervals.
6. **`core/audit.py`**: SHA-256 hash-chained immutable audit log defending against record alteration or insertion.

---

## 4. Security Boundaries & Threat Considerations

1. **Local-First Boundary**: Runtime inference connects exclusively to `http://localhost:11434`. No outbound HTTP requests are transmitted to commercial cloud endpoints.
2. **Data Encapsulation**: Dynamic user inputs and adversarial test prompts are wrapped within explicit string delimiters (`"""\n...\n"""`), preventing prompt injection attacks from overriding system instructions.
3. **Audit Trail Cryptographic Defense**: The `AuditLog` table couples SQLAlchemy before-update / before-delete abort listeners with SHA-256 hash chaining ($H_i = \text{SHA256}(H_{i-1} || \text{data}_i)$). Tampering with any historical record invalidates the entire verification chain.
4. **Separation of Duties**: Change requests cannot be approved by their original authors; promotions require review by an independent designated role in `approvers.yaml`.

