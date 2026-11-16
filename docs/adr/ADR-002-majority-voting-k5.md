# ADR-002: Five-Repetition ($k=5$) Majority Voting for Stochastic Noise Mitigation

- **Status:** Accepted
- **Date:** 2026-11-16
- **Context:** Deciding the repetition factor $k$ and aggregation strategy to eliminate stochastic generation flakiness in local LLM test evaluations.

## Context

Local language models (even at low decoding temperatures) exhibit token-sampling non-determinism, leading to "flaky" test results where identical prompt inputs yield oscillating pass/fail outcomes across executions. Single-run evaluations ($k=1$) falsely classify stochastic jitter as real regressions, creating high false-alarm rates and developer distrust.

However, increasing $k$ incurs a linear compute and latency penalty ($k \times \text{latency}$), which is critical on local workstation hardware without cloud scale.

## Decision

We adopt **$k=5$ repetitions per test case** with **majority voting aggregation**:
1. For each test case, the model is queried $k=5$ times with varying random seeds ($s \in \{42, 43, 44, 45, 46\}$).
2. The aggregate outcome is passed if and only if $\ge 3$ of the 5 runs pass:
   $$\text{passed}_{\text{majority}} = \left(\sum_{i=1}^5 \mathbb{I}(\text{run}_i = \text{pass})\right) \ge 3$$
3. $k$ is enforced to be an odd integer ($k \in \{1, 3, 5, 7\}$) in `core/config.py` to mathematically guarantee zero tie states.
4. Quick development mode provides $k=3$ as an optional runtime flag.

## Consequences & Empirical Evidence

- **Variance Reduction**: As measured in `results/power.md` and `results/summary.csv`, majority-5 voting achieves a **55.3% reduction in outcome variance** relative to single-run execution.
- **Decision Consistency**: Single-run evaluation (Method B2 in `results/summary.csv`) achieved only **72.0% consistency** across repeated evaluations. In contrast, our Majority-5 evaluation achieved **95.9% consistency** on identical test suites.
- **Compute Overhead Tradeoff**: Running $N=108$ tests at $k=5$ requires 540 total model calls, completing in approximately 180 seconds on local Apple Silicon / Ollama hardware, which fits within standard local commit review cycles.
