# Panel Lab Evaluation Report

- **Generated**: 2026-11-10T13:06:46.634067+00:00
- **Model**: `qwen2.5:3b`
- **Test Configuration**: N=2 tests, k=1 repetitions
- **Overall Pass Rate**: 100.00%
- **Latency (p50 / p95)**: 1310.03 ms / 1737.25 ms
- **Total Wall Clock**: 13.66 s
- **Model Calls**: 2 calls (Local Ollama cost: $0.00)

## Advisory Warnings

> **Methodology Notice**: This generated suite checks compliance with the prompt's own rules, not correctness against an external standard.
>
> **Statistical Power Notice**: Sample size is small (N=20, k=3): statistical tests have low power. Treat the verdict as a heuristic and read the flip table.

## Static Linting Findings

| Code | Severity | Message | Line |
| :--- | :--- | :--- | :--- |
| `no_refusal` | **warning** | No negative guidance or refusal instructions for handling out-of-scope or invalid inputs. | 1 |
| `injection_prone` | **warning** | Template variable '{input}' is interpolated without delimiters, quotes, or markdown code blocks, making it susceptible to injection. | 16 |

## Per-Rule Compliance Breakdown

| Rule | Inverse Rule / Failure Mode | Pass Rate | Passed / Total |
| :--- | :--- | :--- | :--- |
| General | Inverse failure | 100.00% | 2 / 2 |
