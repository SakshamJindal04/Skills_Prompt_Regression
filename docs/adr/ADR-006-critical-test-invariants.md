# ADR-006: Critical Test Invariants and Zero-Tolerance Regression Gating

- **Status:** Accepted
- **Date:** 2026-11-16
- **Context:** Ensuring that critical safety, security, and schema boundaries cannot be overridden by statistical averages.

## Context

In aggregate statistical evaluations (such as McNemar tests), an artifact change that fixes 15 general utility tests but regresses 1 catastrophic safety test (e.g. producing an unauthenticated SQL injection vector, dropping a production table, or violating a security invariant) would yield $b=1, c=15, p \approx 0.0005$, causing an unconstrained statistical gate to enthusiastically **PROMOTE** the regressed candidate.

High-stakes applications require zero tolerance for regressions on non-negotiable safety and correctness invariants.

## Decision

We introduce **Critical Test Invariants** (`critical: true` flag in test definitions):
1. A designated subset of tests across all test suites are tagged with `critical: true`.
2. During gate evaluation (`core/gate.py`, `core/decision_rules.py`), the gate verifies the regression status of all critical tests:
   $$\text{critical\_regressed} = \sum_{t \in \text{critical}} \mathbb{I}(t \in b) > 0$$
3. If even a single critical test regresses ($b_{\text{crit}} \ge 1$), the gate immediately issues an unconditional **BLOCK** verdict, regardless of the aggregate McNemar p-value, odds ratio, or non-inferiority margin.
4. Critical test failures are highlighted in top-level dashboard banners and cannot be bypassed without explicit multi-role approval in the Change Request workflow.

## Consequences & Empirical Evidence

- **Empirical Demonstration in Model Matrix**: In `results/model_summary.csv`, when evaluating `sentiment_classifier` with `llama3.2:3b` as a candidate against `qwen2.5:3b`, aggregate statistical metrics yielded $b=4, c=1, p=0.3750$ (statistically non-significant under McNemar alone at $\alpha=0.05$). However, because `crit_sentiment_01` was among the regressed tests, the gate issued a hard **BLOCK**, correctly preventing deployment of an unsafe model swap.
- **Safety Guarantee**: Guarantees that aggregate performance improvements can never mask critical security vulnerabilities.
