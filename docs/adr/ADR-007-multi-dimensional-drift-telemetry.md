# ADR-007: Multi-Dimensional Drift Monitoring Beyond Pass/Fail Binary Metrics

- **Status:** Accepted
- **Date:** 2026-11-16
- **Context:** Detecting subtle behavioral, semantic, latency, and verbosity regressions that pass binary functional assertions.

## Context

A prompt modification or model swap may maintain a 100% functional pass rate while introducing severe operational regressions:
- Output latency may double or triple, violating user SLA thresholds.
- Responses may become excessively verbose, increasing downstream token costs or causing UI clipping.
- Phrasing and semantic style may drift away from expected domain terminology while still satisfying loose regex checks.

Treating quality as purely binary ($0$ or $1$) leaves production systems blind to operational degradation.

## Decision

We adopt **Multi-Dimensional Drift Monitoring** (`core/drift_analysis.py`):
1. **Semantic Drift**: Computes pairwise cosine similarity between embeddings of baseline and candidate majority outputs using local embedding models (`nomic-embed-text`), flagging tests falling below a similarity threshold ($0.85$).
2. **Latency Regression**: Computes sample $p_{50}$ and $p_{95}$ per-call latency with a 1,000-resample bootstrap confidence interval of the difference ($\Delta p_{50}$, $\Delta p_{95}$).
3. **Length Distribution Drift**: Evaluates token, character, and word count distributions, reporting ratio changes and flagging excessive expansion.
4. **Cost & Duration Telemetry**: Records total calls and wall-clock duration per run.
5. In accordance with safe backward compatibility, these metrics surface as informative warnings by default, and only block promotion if explicit drift thresholds are enabled in `policy.yaml`.

## Consequences & Empirical Evidence

- **Empirical Findings in Model Matrix**: In `results/model_summary.csv`, swapping from `qwen2.5:3b` to `llama3.2:3b` increased overall $p_{95}$ latency from **3.519s** to **6.386s** (+81.5% slowdown), despite maintaining similar raw pass rates. Multi-dimensional drift monitoring surfaced this latency degradation immediately in release reports.
- **Root Cause Isolation**: Per-test cosine similarity pinpointed exact cases where output style changed without failing syntactic checks.
