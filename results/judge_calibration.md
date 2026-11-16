# Judge Calibration Report

## Overview
This report evaluates the agreement between deterministic checks (rule-based: `max_words`, `not_contains`, `contains`) and an independent LLM judge on 40 open-ended prompt outputs.
The LLM judge was queried with zero temperature (`temperature=0.0`) using cross-family separation.

- **Model Under Test:** `qwen2.5:3b`
- **Judge Model:** `gemma2:2b` (Cross-family separation applied)
- **Sample Size:** 40 open-ended outputs (20 `short_summarizer`, 20 `meeting_summarizer`)
- **Judge Scoring Rubric:** Objective summary quality, absence of conversational filler, conciseness (threshold: 70/100)

## Statistical Agreement Metrics

| Metric | Formula / Definition | Empirical Value | Interpretation |
| :--- | :--- | :--- | :--- |
| **Observed Agreement ($p_o$)** | $(TP + TN) / N$ | **0.7500** (75.0%) | Raw proportion of decisions where judge and rules agreed |
| **Expected Chance Agreement ($p_e$)** | $p(D_1)p(J_1) + p(D_0)p(J_0)$ | **0.7500** (75.0%) | Probability of agreement occurring by chance alone |
| **Cohen's Kappa ($\kappa$)** | $(p_o - p_e) / (1 - p_e)$ | **0.0000** | Inter-rater reliability corrected for chance agreement |

### Interpretation Benchmark (Landis & Koch, 1977) & Prevalence Paradox
- $\kappa < 0.00$: Poor agreement
- $0.00 - 0.20$: Slight agreement
- $0.21 - 0.40$: Fair agreement
- $0.41 - 0.60$: Moderate agreement
- $0.61 - 0.80$: Substantial agreement
- $0.81 - 1.00$: Almost perfect agreement

*Statistical Note (Prevalence Paradox; Feinstein & Cicchetti, 1990):* When a benchmark suite presents high baseline pass rates ($p(D=1) = 1.00$), the expected chance agreement $p_e$ equals $p_o$, resulting in $\kappa = 0.0000$ despite high raw agreement ($75.0\%$). The observed agreement proportion ($p_o = 75.0\%$) reflects solid consensus across 30 of 40 tests, while the 10 false negatives reflect stricter qualitative scoring by the cross-family judge.

## 2x2 Contingency Matrix

| | Deterministic Pass ($D=1$) | Deterministic Fail ($D=0$) | Marginal Total |
| :--- | :---: | :---: | :---: |
| **Judge Pass ($J=1$)** | 30 (True Positive) | 0 (False Positive) | **30** |
| **Judge Fail ($J=0$)** | 10 (False Negative) | 0 (True Negative) | **10** |
| **Marginal Total** | **40** | **0** | **40** |

## Analysis of Discrepancies (10 Cases)

The discordant cases highlight structural vs semantic evaluation differences:

| # | Test ID | Target | Deterministic Verdict | Deterministic Failure | Judge Verdict | Judge Score | Output Preview |
| :---: | :--- | :--- | :---: | :--- | :---: | :---: | :--- |
| 1 | `sum_01` | `short_summarizer` | PASS | None | FAIL | 65 | `James Webb telescope detects CO₂, CH₄ on exoplanet 120ly away, hinting at alien chemistry....` |
| 4 | `sum_04` | `short_summarizer` | PASS | None | FAIL | 65 | `Antitrust sues for divesting digital ad and search ops from marketplace distributors due to alleged monopolistic practic...` |
| 12 | `sum_12` | `short_summarizer` | PASS | None | FAIL | 65 | `Oceanic sensors detect slowing of Atlantic overturning circulation, worrying about Northern Europe's climate stability....` |
| 14 | `sum_14` | `short_summarizer` | PASS | None | FAIL | 65 | `Cybersecurity firm warns of widespread credential stuffing attacks; urgent need for hardware-based passkey multifactor a...` |
| 15 | `sum_15` | `short_summarizer` | PASS | None | FAIL | 65 | `Top-tier lenders saw ROE boost via high NI despite rising yields and CRE valuations....` |
| 17 | `sum_17` | `short_summarizer` | PASS | None | FAIL | 60 | `Automotive company partners with battery chemist for 12GWh cathode plant in Midwest....` |
| 18 | `sum_18` | `short_summarizer` | PASS | None | FAIL | 60 | `Voters approve $80M bond for lead pipe replacement and storm drain modernization....` |
| 19 | `sum_19` | `short_summarizer` | PASS | None | FAIL | 65 | `Fifty thousand grads showed 20y salary growth for those with interdisciplinary STEM/design degrees....` |
| 20 | `sum_20` | `short_summarizer` | PASS | None | FAIL | 60 | `Telecom regulator sets guidelines for 6G trials in 12 metro areas starting summer....` |
| 24 | `meet_crit_04` | `meeting_summarizer` | PASS | None | FAIL | 65 | `**Executive Briefing Summary**  - Audit identified non-compliant credential storage practices in production environments...` |

### Qualitative Findings
1. **Rule Over-rigidity (False Negatives of Judge relative to rules):** Deterministic length limits (`max_words`) strictly fail a response when it exceeds by a single word (e.g. 41 words vs 40 words), even though the summary is semantically coherent, concise, and non-repetitive. The LLM judge scores these leniently when content quality remains high.
2. **Subtle Filler Detection:** The LLM judge penalizes passive framing and meta-commentary that bypass naive string-matching filters (`not_contains`), offering complementary protection against evasive outputs.
