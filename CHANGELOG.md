# Changelog

All notable changes to the **Skill & Prompt Regression Manager for Local Agents (RegGuard)** and its managed workspace are documented in this file.

This changelog is derived directly from the Git commit histories of the repository and the managed prompt workspace.

---

## Root Repository Releases

### [v2.0.0] - 2026-11-16 (Branch: `industry`)

#### Tier 2: Engineering, Architecture & Scalability
* **25c5a97** (2026-11-16) - feat(tier2): complete engineering, api, security, and packaging hardening (Saksham Jindal)
  - **Packaging**: Created `pyproject.toml` with console command `regguard` and Makefile targets (`test`, `lint`, `typecheck`, `format`, `coverage`, `check-docs`, `run-dev`, `build`).
  - **Configuration**: Added Pydantic v2 `AppSettings` with field validators for statistical constraints and deployment environments.
  - **Migrations**: Added Alembic migrations for MySQL and SQLite with automated upgrade and schema integrity assertion on startup.
  - **REST API**: Implemented local-first FastAPI service with localhost-restricted CORS and endpoints (`/gate`, `/runs`, `/runs/{id}`, `/review`, `/health`, `/metrics`), paired with dual-mode client adapter.
  - **Extensibility**: Implemented plugin decorators `@register_model_provider` and `@register_check` with verified examples.
  - **Observability**: Added structured JSON logging (`StructuredJSONFormatter`) to `logs/regguard.jsonl` with correlation IDs (`run_id`, `test_id`), metrics registry ($p_{50}, p_{95}$ latency percentiles), and real-time health diagnostics.
  - **Security**: Added path traversal confinement (`safe_resolve_path()`), safe YAML loader (`safe_load_yaml()`), Bandit AST scan (0 High issues), and pip-audit scan (0 CVEs).
  - **Local RBAC**: Added PBKDF2 hashed credential storage (`data/credentials.json`) with role enforcement (`author`, `reviewer`, `admin`).
  - **Containerization**: Multi-stage `Dockerfile` with non-root user and `docker-compose.yml` orchestrating MySQL, Dashboard, and API.
  - **Testing**: Added Hypothesis property-based testing and scaling benchmarks across 10, 50, and 100 tests.

#### Tier 1: Decision Quality, Reproducibility & Governance
* **3355dba** (2026-11-16) - feat(tier1): complete decision quality, reproducibility, and evidence hardening (Saksham Jindal)
  - **Replay Verification**: Added `regguard bundle` and `regguard replay` for cryptographically sealed offline re-scoring with zero model calls and SHA-256 tamper detection.
  - **Frozen Decision Rules**: Added four frozen rules (Exact McNemar, Non-Inferiority Margin, Holm-Bonferroni Slices, Discordant Odds Ratio) and statistical power calculator (`regguard power`).
  - **Beyond Pass/Fail Quality**: Implemented semantic embedding cosine similarity drift, bootstrap CI latency percentiles, output length distribution ratios, and cost telemetry.
  - **Agent Trajectories**: Added deterministic agent tools (calculator, document lookup, SQLite queries) with 40 trajectory tests and invariant checkers.
  - **Human Review Queue**: Added adjudication dashboard (`15_Human_Review.py`), Cohen's kappa tracking, and score override capability.
  - **Environments**: Added multi-stage environment promotion registry (`16_Environments.py`) for `dev`, `staging`, and `prod`, SemVer suggestion engine, and automated release notes.
  - **Release Reports**: Added automated HTML and Playwright PDF release report generation with anti-hallucination number validation.

### [v1.0.0] - 2026-11-16 (Branch: `main`)
* **f155e0f** (2026-11-16) - baseline: initial commit before industry hardening pass (Saksham Jindal)
  - Initial baseline codebase comprising multi-model evaluation, Responsible AI scorecard, Panel Lab, SHA-256 audit log chaining, and Streamlit dashboard.

---

## Managed Workspace Prompt & Skill Commit History

* **c836eb2** (2026-11-10) - style: normalize trailing newlines on analytics prompts and skills (Regression Manager)
* **08e43ee** (2026-11-10) - feat(analytics): add prompts and skills for analytics workflow (Regression Manager)
* **d637ee0** (2026-11-04) - chore: bump version to v1.2-rc (Alice Engineer)
* **ce965b7** (2026-11-04) - feat(skills): update documentation across developer skills (Dave Contributor)
* **8efc524** (2026-11-04) - refactor(entity): simplify instructions for faster generation (Charlie Dev)
* **0f4f67e** (2026-11-04) - docs: add production maintenance notes to short_summarizer (Bob Reviewer)
* **3e80cae** (2026-11-04) - feat(sentiment): clarify neutral edge-cases and boundary conditions (Alice Engineer)
* **7c255ba** (2026-11-04) - Initial baseline: production prompts and skills v1.0 (Alice Engineer)
