# ADR-005: Multi-Layered Deterministic Checks with LLM-as-a-Judge Fallback and Human Review Override

- **Status:** Accepted
- **Date:** 2026-11-16
- **Context:** Establishing the evaluation policy for grading complex agent tool outputs, SQL queries, and text summaries.

## Context

Solely relying on an LLM-as-a-Judge introduces judge bias, self-preference, and stochastic evaluation drift. Conversely, solely relying on exact string matching fails on semantically equivalent outputs (e.g., whitespace variations, column alias ordering, valid syntactic paraphrasing).

A reliable evaluation harness requires deterministic guarantees for structural invariants, combined with calibrated subjective evaluation when required, and human-in-the-loop oversight for contentious or safety-critical decisions.

## Decision

We adopt a **Tri-Layered Evaluation Policy**:
1. **Layer 1: Deterministic Invariant Checkers** (`core/checkers.py`):
   - Fast, non-stochastic checks: `exact_match`, `contains`, `regex`, `json_schema`, `sql_ast_valid`, `tool_called`, `no_loops`, `max_steps`.
   - Executed locally in microseconds with 100% determinism.
2. **Layer 2: Calibrated Local LLM Judge Fallback**:
   - Invoked only for open-ended semantic equivalence when configured in policy.
   - Constrained to strict binary output (`{"passed": bool, "reason": str}`).
3. **Layer 3: Human Adjudication Queue & Score Override** (`core/review_queue.py`):
   - Any test where judge confidence is low or discordant pairs flip on critical boundaries is enqueued for human review (`app/pages/15_Human_Review.py`).
   - A qualified reviewer can submit a definitive label with rationale, which overrides the recorded test score and appends an immutable audit entry.

## Consequences & Empirical Evidence

- **Judge Calibration Truth**: In `results/judge_calibration.json` and `results/judge_calibration.md`, comparing the local 3B model judge against human expert ground truth achieved **75.0% observed agreement** on complex SQL queries, with Cohen's kappa $\kappa = 0.0000$ due to severe class imbalance on edge cases. This empirically proved why deterministic Layer 1 and Human Layer 3 are mandatory.
- **Audit Traceability**: Overrides record reviewer ID, timestamp, and justification, preserving end-to-end accountability.
