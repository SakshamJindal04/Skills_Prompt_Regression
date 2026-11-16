# ADR-008: Dual-Backend Persistence Strategy with Automated Alembic Schema Migrations

- **Status:** Accepted
- **Date:** 2026-11-16
- **Context:** Supporting both zero-configuration local workstation development and concurrent team production deployment without code branching.

## Context

Local workstation developers need zero-configuration setup without installing or running containerized database daemons. Conversely, enterprise teams running continuous evaluation pipelines and multi-user review workflows require concurrent write transactions, row-level locking, and high throughput that SQLite cannot reliably provide under concurrent write pressure (often encountering `database is locked` errors).

Maintaining separate database access layers or diverging ORM schemas creates severe maintenance overhead and deployment bugs.

## Decision

We adopt a **Unified SQLAlchemy + Alembic Architecture** supporting both **MySQL 8.0** and **SQLite**:
1. All relational entities (`Artifact`, `EvalRun`, `Comparison`, `Trace`, `Score`, `ChangeRequest`, `ReviewItem`, `EnvironmentBaseline`) are defined with standard SQLAlchemy ORM models.
2. Dialect abstractions handle type differences transparently (e.g. JSON columns mapped to `JSON` on MySQL and JSON-serialized `Text` on SQLite; timestamps normalized to UTC).
3. `core/db.py` implements intelligent auto-fallback: attempts connection to production MySQL (`mysql+pymysql://regression_user:regression_pass@localhost:3306/regression_db`), and if unreachable, automatically falls back to local SQLite (`sqlite:///regression_manager.db`) with clear logging.
4. Schema migrations are managed declaratively with **Alembic** (`alembic/`), auto-running on application startup in `core/db.py:init_db()`.
5. Post-migration schema assertions verify table existence before serving traffic.

## Consequences & Empirical Evidence

- **Scaling Benchmark Verification**: As measured in `results/scaling.md`:
  - At $N=100$ tests, SQLite insertion completed in **64.2ms** and query retrieval in **1.8ms**.
  - At $N=100$ tests, MySQL insertion completed in **142.6ms** (reflecting network socket and transactional durability overhead) and query retrieval in **3.2ms**.
- **Zero Friction Onboarding**: A new developer can clone the repository, run `pip install -e .`, and immediately execute test suites against SQLite without starting any services, while CI/CD and Docker environments automatically run with MySQL.
