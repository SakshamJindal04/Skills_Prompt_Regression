# System Limitations & Boundary Conditions

This document provides an objective, honest account of the theoretical and operational limitations of the Skill & Prompt Regression Manager.

---

## 1. Small Sample Size ($N$) and Statistical Power Boundaries
- **Description**: In local developer workflows, evaluating thousands of test cases is often impractical due to hardware constraints. Our benchmark suites operate on $N \approx 30 \text{ to } 108$ test cases.
- **Consequence**: The exact McNemar test requires a sufficient number of discordant pairs ($b+c$) to reject the null hypothesis at $\alpha = 0.05$. For example, when $b=4$ and $c=1$, the exact two-sided binomial p-value is $p = 0.3750$, which is not statistically significant despite a clear negative trend.
- **Mitigation**: To prevent regressions from slipping through under low statistical power, our gate combines McNemar testing with a deterministic **critical assertion list** (`critical_test_ids` in `policy.yaml`). Any candidate that breaks a test marked critical is blocked immediately regardless of sample size or p-value.

---

## 2. Reliance on Compact Quantized Models (2B to 3B Parameters)
- **Description**: The system is optimized to run locally on resource-constrained consumer hardware (e.g., 16GB RAM laptops) using compact quantized weights (`qwen2.5:3b`, `gemma2:2b`, `llama3.2:3b` in 4-bit quantization).
- **Consequence**: Smaller models exhibit lower instruction-following fidelity on complex multi-constraint tasks. For instance, on the zero-shot JSON entity extraction suite (`entity_extractor`), all 3B models scored near 0.0% pass rate when scored against strict JSON schema validators that penalize preamble conversational conversational text.
- **Mitigation**: Teams should use structured system prompts, specify few-shot examples in `prompts/*.md`, or leverage Ollama's `format="json"` constraint.

---

## 3. Synthetic vs. Organic Prompt Mutations
- **Description**: In our experimental evaluation (`results/edits.csv`), several prompt and skill mutations were synthetically injected (e.g., dropping formatting rules, truncating descriptions, or introducing edge-case ambiguities) to benchmark detection sensitivity.
- **Consequence**: Synthetic mutations may present sharper performance drops than natural developer edits, which often contain subtle phrasing shifts.
- **Mitigation**: We complemented synthetic mutations with an authentic enterprise case study (`results/case_study.md`) based on multi-step SQL, entity extraction, and executive meeting notes workflows.

---

## 4. Evaluator Bias in LLM-as-a-Judge & The Prevalence Paradox
- **Description**: Using an LLM to evaluate open-ended tasks introduces evaluator subjectivity, token length preference, and calibration challenges.
- **Consequence**: In `results/judge_calibration.json`, evaluating 40 summaries with `gemma2:2b` as judge against deterministic checks yielded a Cohen's kappa of $\kappa = 0.0000$ despite high observed agreement ($p_o = 75.0\%$). This is an unavoidable mathematical consequence of the **prevalence paradox**: when the sample consists of pre-screened passing candidates ($p(D=1) = 1.0$), expected chance agreement $p_e$ equals observed agreement $p_o$, forcing $\kappa$ to 0.0.
- **Mitigation**: Rule-based deterministic checks (exact match, JSON schema, regex, word count limits) are always prioritized first. LLM judges are strictly reserved for open-ended rubric evaluations where deterministic assertions cannot be formulated.

---

## 5. Local Hardware Execution Throughput
- **Description**: Wall-clock evaluation time is bounded by local GPU/NPU inference throughput.
- **Consequence**: Running full evaluations ($k=5$ across 108 tests = 540 calls per model) requires approximately 10 to 20 minutes per model on standard Apple Silicon or consumer NVIDIA GPUs.
- **Mitigation**: We provide `--quick` flags ($k=3$, 20 tests) for rapid local iterative feedback, and baseline trace caching to cut total inference calls by 50% on subsequent runs.

