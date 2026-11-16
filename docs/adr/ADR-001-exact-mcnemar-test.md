# ADR-001: Selection of Exact Two-Sided McNemar Test for Paired Regression Gating

- **Status:** Accepted
- **Date:** 2026-11-16
- **Context:** Deciding the primary statistical hypothesis test for evaluating whether a candidate prompt/skill change introduces statistically significant regressions compared to an active baseline.

## Context

When evaluating local LLM prompts and agent skills, test cases are evaluated against both the active baseline artifact and a candidate artifact under identical conditions. Because the same test inputs are applied to both versions, test outcomes are strictly paired binary observations:
- Both pass ($a$)
- Regressed: Baseline pass $\rightarrow$ Candidate fail ($b$)
- Fixed: Baseline fail $\rightarrow$ Candidate pass ($c$)
- Both fail ($d$)

Unpaired tests (such as two-sample Student's t-test or two-proportion z-test) ignore within-item pairing, treating the $2N$ observations as independent. This introduces substantial variance and fails to isolate discordant outcomes ($b$ and $c$).

Furthermore, asymptotic McNemar formulations using the $\chi^2$ approximation ($\chi^2 = (b - c)^2 / (b + c)$) break down when total discordant flips are small ($b + c < 25$), leading to severely inflated Type I error rates.

## Decision

We adopt the **Exact Two-Sided McNemar Test** (`scipy.stats.binomtest(min(b, c), b + c, 0.5)`).

1. Under the null hypothesis $H_0: p_{\text{regressed}} = p_{\text{fixed}}$, the number of discordant pairs follows a Binomial distribution:
   $$\min(b, c) \sim \text{Binomial}(b + c, 0.5)$$
2. The gate blocks candidate promotion if and only if:
   $$p < \alpha \quad \text{and} \quad b > c$$
   where $\alpha = 0.05$ by default.
3. If $b \le c$, the change is non-inferior or superior and passes the statistical check.

## Consequences & Empirical Evidence

- **Small Sample Exactness**: Avoids continuous distribution approximation errors on small suites ($N \le 108$).
- **Minimum Detectable Threshold**: As documented in `results/power.md`, with $c = 0$ fixes, the exact test requires $b \ge 6$ regressed tests to achieve significance at $\alpha = 0.05$ ($0.5^{6-1} = 0.03125$). For our golden suite ($N = 108$), this defines an empirical minimum detectable regression rate of $5.56\%$.
- **Precision Ground Truth**: In our benchmark evaluation across 26 prompt edits (`results/summary.csv`), the Majority-k + Exact McNemar method achieved **1.000 Precision** (95% CI: $[0.566, 1.000]$) and **95.9% Decision Consistency**, outperforming single-run diffs (72.0% consistency).
