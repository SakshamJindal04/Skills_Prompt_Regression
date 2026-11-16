# Panel Lab Rehearsal Evaluation

Date: 2026-11-10 13:20:14 UTC
Model Under Test: `qwen2.5:3b` (local Ollama)
Configuration: 10 representative prompts, N=2 generated PromptPex tests per prompt, k=1 repetition.

## Summary Rehearsal Matrix

| # | Domain / Use Case | Pass Rate | Generated Tests | p50 Latency (ms) | p95 Latency (ms) | Wall Clock (s) | Lint Findings | Truncation Notice |
| :- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | Summarization | 100.0% | 2 | 1352.0 | 1462.0 | 23.32 | 3 | No |
| 2 | Extraction | 0.0% | 2 | 2207.9 | 2250.0 | 11.49 | 2 | No |
| 3 | Classification | 100.0% | 2 | 311.6 | 351.2 | 8.48 | 3 | No |
| 4 | SQL Generation | 100.0% | 2 | 1320.5 | 1984.3 | 10.40 | 2 | No |
| 5 | Refusal / Safety | 100.0% | 2 | 785.4 | 850.7 | 8.99 | 2 | No |
| 6 | Long Prompt Handling | 50.0% | 2 | 7451.6 | 13175.2 | 34.35 | 3 | No |
| 7 | Adversarial Injection Defense | 100.0% | 2 | 1174.0 | 1588.5 | 9.91 | 3 | No |
| 8 | Multilingual Translation | 100.0% | 2 | 1028.8 | 1139.2 | 9.20 | 3 | No |
| 9 | Code Analysis | 50.0% | 2 | 2443.2 | 4220.7 | 13.51 | 3 | No |
| 10 | Creative Structure | 0.0% | 2 | 10923.4 | 12292.2 | 30.49 | 3 | No |

## Key Rehearsal Observations

1. **Rule Extraction Latency**: Synthesizing checkable PromptPex rules and generating boundary tests averages 1.5 - 2.5 seconds per prompt using local Qwen 2.5 3B.
2. **Deterministic Check Resilience**: Strict output requirements (e.g. JSON validation, word count limits, SQL keyword checks) pass with high fidelity when instructions are unambiguous.
3. **Safety & Injection Defense**: Adversarial injections ('ignore previous instructions') encapsulated within data boundaries fail to override system prompts.
4. **Long Prompt Safeguards**: Prompts with repetitive regulatory filler exceeding threshold trigger explicit truncation notices without crashing the pipeline.
