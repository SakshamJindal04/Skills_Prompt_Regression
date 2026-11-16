# ADR-003: Git Commits as Immutable Version Lineage and Non-Destructive Rollback Mechanism

- **Status:** Accepted
- **Date:** 2026-11-16
- **Context:** Establishing how prompts and skills are versioned, referenced, compared, and rolled back in developer workflows.

## Context

Many prompt evaluation systems store prompt versions in relational databases or mutable cloud registries. This decouples prompt logic from the surrounding codebase, obscures authorship, complicates CI/CD integration, and enables silent out-of-band mutations that evade audit logs.

Additionally, rollbacks in database-centric systems often overwrite the active prompt row, destroying historical state and making root-cause analysis difficult.

## Decision

We adopt the local **Git repository as the single authoritative source of truth**:
1. Every baseline and candidate version is identified by its full 40-character Git SHA-1 commit hash.
2. Changes to prompts (`workspace/prompts/`) and skills (`skills/`) must be committed to Git before gate evaluation.
3. Git working-tree status is verified (`repo.is_dirty()`) before running gate comparisons to prevent evaluating uncommitted state.
4. Rollback operations (`core/repo.py:rollback_to_commit`) execute non-destructive `git revert` commits, appending a new commit hash to history rather than executing destructive hard resets (`git reset --hard`).

## Consequences & Empirical Evidence

- **Traceable Cryptographic Lineage**: Every evaluation record in `eval_runs` and `comparisons` references parent and candidate Git hashes, guaranteeing exact reproducibility.
- **Audit Compliance**: As verified in `tests/test_audit_chain.py` and `tests/test_integration_git_flow.py`, all rollback events are logged in the SHA-256 chained audit log (`logs/audit.jsonl`), recording the requester, approver, target commit, and newly generated revert commit.
- **Merge Conflict Safety**: If a clean `git revert` is obstructed by conflicts, the system automatically checks out the exact file state from the baseline commit and commits it cleanly, maintaining 100% rollback reliability.
