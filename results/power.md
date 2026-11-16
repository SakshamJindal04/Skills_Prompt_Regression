# Statistical Power Analysis: Exact Two-Sided McNemar Test

This document analyzes the statistical detection threshold of our exact two-sided McNemar test across test suites of size $N$.

## 1. Exact McNemar Test Formulation

For paired test evaluations comparing baseline against candidate:
- Let $b$ be the number of regressed tests (baseline pass $\rightarrow$ candidate fail).
- Let $c$ be the number of fixed tests (baseline fail $\rightarrow$ candidate pass).
- Under the null hypothesis $H_0: p_{\text{regression}} = p_{\text{fix}}$, the number of discordant pairs follows:
  $$K = \min(b, c) \sim \text{Binomial}\left(b + c, 0.5\right)$$
- The two-sided $p$-value is computed exactly via:
  $$p = \text{scipy.stats.binomtest}\left(\min(b, c), b + c, 0.5\right).\text{pvalue}$$

---

## 2. Minimum Regressed Tests ($b$) for Statistical Significance ($\alpha = 0.05$)

Given varying counts of fixed tests ($c \in \{0, 1, 2, 3\}$), the table below details the exact two-sided $p$-values and identifies the minimum number of regressed tests $b^*$ required to reject $H_0$ at $\alpha = 0.05$:

| Fixed Tests ($c$) | Regressed Tests ($b$) | Total Flips ($b+c$) | Two-Sided $p$-value | Significant ($p < 0.05$)? |
| :---: | :---: | :---: | :---: | :---: |
| **0** | 4 | 4 | 0.1250 | No |
| **0** | 5 | 5 | 0.0625 | No |
| **0** | **6** | **6** | **0.0312** | **Yes ($b^* = 6$)** |
| **1** | 6 | 7 | 0.1250 | No |
| **1** | 7 | 8 | 0.0703 | No |
| **1** | **8** | **9** | **0.0391** | **Yes ($b^* = 8$)** |
| **2** | 8 | 10 | 0.1094 | No |
| **2** | 9 | 11 | 0.0654 | No |
| **2** | **10** | **12** | **0.0386** | **Yes ($b^* = 10$)** |
| **3** | 10 | 13 | 0.0923 | No |
| **3** | 11 | 14 | 0.0574 | No |
| **3** | **12** | **15** | **0.0352** | **Yes ($b^* = 12$)** |

---

## 3. Smallest Detectable Regression Rate for Suite Size $N = 108$

For our golden suite containing $N = 108$ tests:

$$\text{Minimum Detectable Regression Rate } \text{RR}_{\min} = \frac{b^*}{N}$$

- **Scenario A ($c = 0$ fixed tests)**:
  $$\text{RR}_{\min} = \frac{6}{108} \approx 5.56\%$$
- **Scenario B ($c = 1$ fixed test)**:
  $$\text{RR}_{\min} = \frac{8}{108} \approx 7.41\%$$
- **Scenario C ($c = 2$ fixed tests)**:
  $$\text{RR}_{\min} = \frac{10}{108} \approx 9.26\%$$
- **Scenario D ($c = 3$ fixed tests)**:
  $$\text{RR}_{\min} = \frac{12}{108} \approx 11.11\%$$

---

## 4. Architectural Implications for Gate Policy

1. **Why McNemar Alone Misses Small Injected Regressions**:
   If an injected edit degrades performance on only 1 to 5 non-critical tests (e.g., subtle phrasing drifts affecting 2 niche inputs), $p \ge 0.0625$. Under pure significance testing with $N=108$, this cannot achieve $p < 0.05$.
2. **The Role of the Critical Test Policy**:
   Our gate evaluates:
   $$\text{Verdict} = \text{BLOCK if } (p < \alpha \text{ and } b > c) \text{ OR } (\text{any critical test regressed})$$
   Marking high-priority constraints (e.g. strict JSON adherence, single-word compliance) as `critical: true` ensures that even a single regression ($b = 1$) halts deployment immediately, bypassing the statistical sample-size barrier.

