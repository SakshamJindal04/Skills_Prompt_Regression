# Contributing Guidelines

Thank you for contributing to the **Skill & Prompt Regression Manager for Local Agents (RegGuard)**.

This project is governed by strict local-first, privacy-preserving, and empirical quality standards. Please review these guidelines before submitting changes.

---

## 1. Core Engineering Principles

1. **Strictly Local-First**: Zero external network or cloud API calls are permitted at runtime. All model inference must execute via the local Ollama daemon (`http://localhost:11434`). Persistence is local MySQL or SQLite.
2. **Empirical Evidence Only**: Never invent, estimate, or hardcode benchmark numbers, pass rates, latencies, or evaluation history. All numbers in documentation must match computation in `results/`.
3. **Safe Defaults & Feature Flags**: Every new feature must be guarded behind a flag in `policy.yaml` with a safe default.
4. **No Emojis Anywhere**: Use clean, plain student-team style. When icons are needed in UI components, use Streamlit Material icons exclusively (`:material/icon_name:`).
5. **Relative Paths**: Always use relative repository paths rather than hardcoded absolute system paths.

---

## 2. Environment Setup

```bash
# 1. Clone repository and navigate to root
cd Responsible_Ai

# 2. Activate Python 3.12 environment
source .venv/bin/activate

# 3. Install package in editable mode with development dependencies
uv pip install -e ".[dev]"

# 4. Verify local Ollama is active
ollama list
```

---

## 3. Development & Verification Workflow

We provide Makefile targets for all quality gates:

```bash
# Run full unit and integration test suite
make test

# Verify linting and formatting
make lint

# Run static type checking
make typecheck

# Format code
make format

# Verify documentation numbers against empirical results in results/
make check-docs

# Verify MySQL and SQLite persistence
make verify
```

---

## 4. Prompt & Skill Contribution Guidelines

When adding or modifying prompts in `workspace/prompts/` or skills in `skills/`:

1. **Commit Lineage**: Always commit prompt changes to Git so that a valid 40-character Git commit hash exists.
2. **Regression Gate Execution**: Run the regression gate against the active baseline:
   ```bash
   regguard --base <baseline_hash> --cand <candidate_hash> -k 5
   ```
3. **Critical Invariants**: If your change causes any test with `critical: true` to regress, the change will be automatically blocked. You must resolve the regression before requesting review.
4. **Change Request Process**: In the dashboard, submit a formal Change Request (`7_Change_Requests.py`). Note that `requester != approver` is enforced to ensure separation of duties.

---

## 5. Pull Request Checklist

Before submitting a pull request, ensure:
- [ ] `pytest tests/` passes 100% with zero failing or flaky tests.
- [ ] `ruff check core/ app/ cli.py tests/` reports zero errors.
- [ ] `mypy core/` reports zero errors across source files.
- [ ] `python scripts/check_docs_numbers.py` confirms 100% consistency with `results/`.
- [ ] Any new configuration option has a corresponding validator in `core/config.py` and default in `policy.yaml`.
- [ ] No external dependencies or runtime network endpoints were introduced.
