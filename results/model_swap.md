# Cross-Model Regression & Swap Case Study

## Executive Summary
This empirical study evaluates candidate local LLMs (`llama3.2:3b` and `gemma2:2b`) as drop-in replacements for the baseline model (`qwen2.5:3b`).
All evaluations were executed live via local Ollama against 108 tests ($k=5$ runs per test, seeds $42 + 1000r$).
Total wall-clock runtime: 2518.0 seconds.

## Evaluated Models & Architecture

| Model ID | Family | Parameters | SHA-256 Digest | Context Window | Pipeline Role |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`qwen2.5:3b`** | `qwen2` | 3.1B | `357c53fb659c5076...` | 32768 | Baseline Under Test |
| **`llama3.2:3b`** | `llama` | 3.2B | `a80c4f17acd55265...` | 131072 | Candidate Under Test |
| **`gemma2:2b`** | `gemma2` | 2.6B | `8ccf136fdd5298f3...` | 8192 | Candidate Under Test |

## Quantitative Performance Matrix (Per Prompt & Combined)

| Prompt Target | Model ID | Digest | Pass Rate (Wilson 95% CI) | Consistency | Mean Latency | p95 Latency | Skill Accuracy | Regressed ($b$) | Fixed ($c$) | McNemar $p$-value | Gate Verdict |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `entity_extractor` | `qwen2.5:3b` | `357c53fb659c` | 0.0% [0.0%, 9.6%] | 1.000 | 2.61s | 4.28s | 90.0% | 0 | 0 | 1.0000 | N/A (Baseline) |
| `entity_extractor` | `llama3.2:3b` | `a80c4f17acd5` | 0.0% [0.0%, 9.6%] | 1.000 | 4.84s | 7.80s | 100.0% | 0 | 0 | 1.0000 | **PROMOTE** |
| `entity_extractor` | `gemma2:2b` | `8ccf136fdd52` | 0.0% [0.0%, 9.6%] | 1.000 | 2.58s | 3.60s | 100.0% | 0 | 0 | 1.0000 | **PROMOTE** |
| `sentiment_classifier` | `qwen2.5:3b` | `357c53fb659c` | 94.4% [81.9%, 98.5%] | 1.000 | 0.23s | 0.31s | 90.0% | 0 | 0 | 1.0000 | N/A (Baseline) |
| `sentiment_classifier` | `llama3.2:3b` | `a80c4f17acd5` | 86.1% [71.3%, 93.9%] | 0.978 | 0.27s | 0.33s | 100.0% | 4 | 1 | 0.3750 | **BLOCK** |
| `sentiment_classifier` | `gemma2:2b` | `8ccf136fdd52` | 91.7% [78.2%, 97.1%] | 0.978 | 0.37s | 0.55s | 100.0% | 1 | 0 | 1.0000 | **PROMOTE** |
| `short_summarizer` | `qwen2.5:3b` | `357c53fb659c` | 100.0% [90.4%, 100.0%] | 1.000 | 0.78s | 1.08s | 90.0% | 0 | 0 | 1.0000 | N/A (Baseline) |
| `short_summarizer` | `llama3.2:3b` | `a80c4f17acd5` | 100.0% [90.4%, 100.0%] | 1.000 | 1.30s | 1.79s | 100.0% | 0 | 0 | 1.0000 | **PROMOTE** |
| `short_summarizer` | `gemma2:2b` | `8ccf136fdd52` | 100.0% [90.4%, 100.0%] | 1.000 | 0.89s | 1.17s | 100.0% | 0 | 0 | 1.0000 | **PROMOTE** |
| `ALL_PROMPTS` | `qwen2.5:3b` | `357c53fb659c` | 64.8% [55.4%, 73.2%] | 1.000 | 1.21s | 3.52s | 90.0% | 0 | 0 | 1.0000 | N/A (Baseline) |
| `ALL_PROMPTS` | `llama3.2:3b` | `a80c4f17acd5` | 62.0% [52.6%, 70.6%] | 0.993 | 2.14s | 6.39s | 100.0% | 4 | 1 | 0.3750 | **BLOCK** |
| `ALL_PROMPTS` | `gemma2:2b` | `8ccf136fdd52` | 63.9% [54.5%, 72.3%] | 0.993 | 1.28s | 3.25s | 100.0% | 1 | 0 | 1.0000 | **PROMOTE** |

## Statistical Power & McNemar Exact Test

Exact McNemar test with binomial distribution ($H_0: p(b) = p(c) = 0.5$):
- Power condition for two-sided significance at $\alpha = 0.05$:
  - When $c = 0$, minimum regressed tests required: $b \ge 6$ ($p = 0.0312$).
  - When $c = 1$, minimum regressed tests required: $b \ge 8$ ($p = 0.0391$).
  - When $c = 2$, minimum regressed tests required: $b \ge 9$ ($p = 0.0327$).
  - When $c = 3$, minimum regressed tests required: $b \ge 11$ ($p = 0.0287$).

## Informative Flipped Tests Per Candidate Model

### Candidate: `llama3.2:3b` (Total Flips: 5, Regressed: 4, Fixed: 1)

#### Flip #1: [CRITICAL] `sent_08` (REGRESSION - Critical Test Regression)
- **Target Prompt:** `sentiment_classifier`
- **Input:** `Not a single bug discovered during the entire week of rigorous stress testing....`
- **Baseline Output (`qwen2.5:3b`):** `POSITIVE...`
- **Candidate Output (`llama3.2:3b`):** `NEUTRAL...`
- **Root Cause Analysis:** Model output deviated from check constraints.

#### Flip #2: `sent_04` (REGRESSION - Standard Format or Constraint Violation)
- **Target Prompt:** `sentiment_classifier`
- **Input:** `Company reports record quarterly revenue and EBITDA expansion of 24% year-over-year....`
- **Baseline Output (`qwen2.5:3b`):** `POSITIVE...`
- **Candidate Output (`llama3.2:3b`):** `NEUTRAL...`
- **Root Cause Analysis:** Model output deviated from check constraints.

#### Flip #3: `sent_09` (REGRESSION - Standard Format or Constraint Violation)
- **Target Prompt:** `sentiment_classifier`
- **Input:** `I cannot say that I am disappointed with how responsive the new user interface feels....`
- **Baseline Output (`qwen2.5:3b`):** `POSITIVE...`
- **Candidate Output (`llama3.2:3b`):** `NEGATIVE...`
- **Root Cause Analysis:** Model output deviated from check constraints.


### Candidate: `gemma2:2b` (Total Flips: 1, Regressed: 1, Fixed: 0)

#### Flip #1: `sent_09` (REGRESSION - Standard Format or Constraint Violation)
- **Target Prompt:** `sentiment_classifier`
- **Input:** `I cannot say that I am disappointed with how responsive the new user interface feels....`
- **Baseline Output (`qwen2.5:3b`):** `POSITIVE...`
- **Candidate Output (`gemma2:2b`):** `NEUTRAL...`
- **Root Cause Analysis:** Model output deviated from check constraints.


## Recommendations & Gate Decision
1. **Baseline Stability:** `qwen2.5:3b` demonstrates balanced adherence to exact constraints and JSON schema compliance.
2. **Cross-Model Compatibility:** Switching model weights requires reviewing prompt sensitivity, as different instruction-tuning approaches handle negative constraints (`not_contains`) and conciseness (`max_words`) with differing strictness.
3. **CI/CD Enforcement:** Any model migration should be gated by the automated McNemar and critical assertions pipeline to prevent silent regression in downstream agent workflows.
