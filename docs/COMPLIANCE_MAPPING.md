# Regulatory & Governance Compliance Mapping

This document provides a structured mapping of the technical features, evaluation controls, cryptographic safeguards, and governance workflows implemented in the **Skill & Prompt Regression Manager for Local Agents** to international AI safety standards and regulatory frameworks.

> **Important Terminology Note:** In accordance with standard AI assurance guidance, this document indicates how the system **supports** or **aligns with** specific regulatory and standards controls. It does not claim that the software on its own "complies with" legislation, as compliance is an organizational, socio-technical obligation.

---

## 1. NIST Artificial Intelligence Risk Management Framework (AI RMF 1.0)

The NIST AI RMF organizes AI risk management into four core functions: **Govern**, **Map**, **Measure**, and **Manage**.

| NIST AI RMF Function | Sub-Category / ID | System Implementation Feature | How the System Supports / Aligns with the Framework |
| :--- | :--- | :--- | :--- |
| **GOVERN** | **GOVERN 1.1** (Legal & regulatory requirements) | Immutable Audit Trail (`core/audit.py`) | Maintains a cryptographic SHA-256 hash-chained ledger of all evaluations, gate decisions, overrides, and rollbacks, supporting organizational auditability and accountability. |
| **GOVERN** | **GOVERN 1.2** (Roles and responsibilities) | Local Role-Based Access Control (`core/auth.py`) | Aligns with role separation by enforcing distinct permissions for `author`, `reviewer`, and `admin` roles, preventing unauthorized production promotions or policy modifications. |
| **GOVERN** | **GOVERN 2.1** (Risk management policies) | Configurable Gate Policies (`policy.yaml`, `core/policy.py`) | Encodes organizational risk thresholds (significance level $\alpha$, non-inferiority margins, odds-ratio ceilings) into declarative policy files with versioning and freeze flags. |
| **GOVERN** | **GOVERN 3.2** (Separation of duties) | Multi-Role Change Approval (`app/pages/7_Change_Requests.py`) | Requires that prompt changes undergo formal review where `requester != approver`, ensuring dual-custody verification before promotion. |
| **MAP** | **MAP 1.1** (Context of use & intended purpose) | System Card & Data Card (`docs/SYSTEM_CARD.md`, `docs/DATA_CARD.md`) | Supports clear documentation of model limitations, task scope, target domains, and dataset characteristics. |
| **MAP** | **MAP 2.3** (Negative impact identification) | Slice-Based Quality Analysis (`core/runner.py`, `app/pages/3_Slices.py`) | Categorizes evaluations into specialized slices (e.g. edge cases, dialect variations, complex syntax) to map performance disparities across distinct user inputs. |
| **MAP** | **MAP 3.1** (Security & safety vulnerabilities) | Agent Adversarial Slices (`tests_data/agent_trajectory_tests.yaml`) | Maps vulnerability surfaces including SQL injection, path traversal, infinite loops, and shell injection attempts. |
| **MEASURE** | **MEASURE 1.1** (Rigorous quantitative metrics) | Exact McNemar Test & Bootstrap CIs (`core/decision_rules.py`) | Measures regression significance using paired exact binomial tests and 10,000-resample bootstrap confidence intervals rather than noisy heuristics. |
| **MEASURE** | **MEASURE 2.2** (Stochastic variance control) | Majority Voting ($k=5$) (`core/runner.py`) | Aligns with rigorous measurement standards by reducing stochastic token-generation variance by 55.3% through majority-k aggregation. |
| **MEASURE** | **MEASURE 2.5** (Evaluator calibration) | Judge Calibration & Cohen's Kappa (`core/review_queue.py`) | Continuously measures inter-rater agreement between local LLM judges and human raters, computing Cohen's kappa to identify judge bias. |
| **MEASURE** | **MEASURE 2.8** (Multi-dimensional drift) | Multi-Dimensional Drift Telemetry (`core/drift_analysis.py`) | Measures operational degradation across output latency percentiles ($p_{50}, p_{95}$), semantic cosine similarity, length distribution, and compute cost. |
| **MANAGE** | **MANAGE 1.1** (Risk prioritization & treatment) | Critical Test Invariants (`core/gate.py`) | Enforces zero-tolerance gates: regressions on tagged critical tests immediately issue a hard BLOCK verdict regardless of aggregate pass rates. |
| **MANAGE** | **MANAGE 2.2** (Incident response & recovery) | Non-Destructive Git Revert (`core/repo.py`, `app/pages/6_Rollback.py`) | Provides one-click, non-destructive rollback capabilities that commit clean revert states to Git history with verifiable impact previews. |
| **MANAGE** | **MANAGE 3.1** (Continuous monitoring) | Reproducibility Bundles (`core/bundle.py`) | Supports post-deployment assurance by enabling cryptographically sealed ZIP replay of past gate runs with zero model calls. |

---

## 2. European Union Artificial Intelligence Act (EU AI Act)

For high-risk and general-purpose AI systems under the EU AI Act, the architecture aligns with critical technical documentation, logging, and human oversight articles:

### Article 9: Risk Management System
- **Article 9(2)(a) (Identification & analysis of foreseeable risks)**:  
  *Implementation:* Automated static prompt linting (`core/lint.py`) scans candidate prompts for injection vectors, lack of refusal boundaries, missing role scoping, and format vulnerabilities prior to model execution.
- **Article 9(2)(b) (Estimation & evaluation of risks under intended use)**:  
  *Implementation:* Statistical regression gates (`core/decision_rules.py`) evaluate pass-rate deltas, non-inferiority margins, and slice-level regressions across candidate versions.
- **Article 9(5) (Testing procedures & metrics)**:  
  *Implementation:* Standardized golden benchmark suites with fixed seeds ($s \in \{42, \dots, 46\}$), deterministic invariant checkers, and documented minimum detectable regression thresholds ($b^* = 6$ for $N=108$).

### Article 12: Record-Keeping & Automatic Logging
- **Article 12(1) (Automatic logging of events over system lifecycle)**:  
  *Implementation:* Every evaluation run captures step-by-step traces, prompt templates, seed values, completion timestamps, and exact raw text responses into relational tables (`eval_runs`, `traces`, `scores`).
- **Article 12(2) (Traceability of post-market monitoring)**:  
  *Implementation:* Chained SHA-256 audit logging (`core/audit.py`, `logs/audit.jsonl`) writes tamper-evident records for every gate verdict, change request, and promotion across `dev`, `staging`, and `prod` environments.
- **Article 12(3) (Tamper-evident verification)**:  
  *Implementation:* Replay bundles (`core/bundle.py`) package all execution artifacts into cryptographically hashed zip archives; any post-hoc tampering triggers an immediate digest mismatch exception (`BundleTamperedError`).

### Article 14: Human Oversight
- **Article 14(1) (Effective human oversight during operation)**:  
  *Implementation:* The system implements a Human Review Queue (`app/pages/15_Human_Review.py`), enabling qualified human adjudicators to inspect borderline cases, evaluate ambiguous outputs, and submit authoritative labels.
- **Article 14(4)(a) (Awareness of system limitations & automation bias)**:  
  *Implementation:* Power analysis heuristics (`python cli.py power`) explicitly display warnings when sample sizes are statistically underpowered, instructing reviewers to treat the verdict as a heuristic and manually examine the flip table.
- **Article 14(4)(e) (Ability to override or reverse automated decisions)**:  
  *Implementation:* Human score overrides (`core/review_queue.py:submit_human_review`) allow authorized reviewers to override automated model judge scores, recording reviewer identity and explicit rationale in the immutable audit trail.

---

## 3. ISO/IEC 42001:2023 (Artificial Intelligence Management System)

ISO/IEC 42001 specifies requirements for establishing, implementing, maintaining, and continually improving an Artificial Intelligence Management System (AIMS).

| ISO/IEC 42001 Domain | Control Area | System Implementation Alignment | Alignment Description |
| :--- | :--- | :--- | :--- |
| **Clause 6.1** | Actions to address risks and opportunities | Gate Decision Rules & Statistical Verification | Supports systematic risk evaluation through 4 frozen decision rule variants (`core/decision_rules.py`). |
| **Clause 8.2** | AI risk assessment | Static Linting & Adversarial Testing | Supports vulnerability identification across prompt injection, jailbreaking, and unconstrained tool usage. |
| **Clause 8.4** | Control of externally provided AI components | Model Matrix & Swapping Verification | Supports vendor and model evaluation by testing candidate models (`qwen2.5:3b`, `llama3.2:3b`, `gemma2:2b`) against identical test suites before deployment. |
| **Clause 9.1** | Monitoring, measurement, analysis & evaluation | Observability & Telemetry Engine | Supports continuous performance monitoring via structured JSON logging, call metrics, and latency percentiles (`core/observability.py`). |
| **Clause 9.2** | Internal audit | Cryptographic Audit Trail & Replay Engine | Supports independent verification by enabling auditors to recompute historical evaluation verdicts offline with zero model calls. |
| **Clause 10.2** | Nonconformity and corrective action | Non-Destructive Git Rollback Workflow | Supports immediate corrective remediation by providing automated, auditable rollbacks to previous verified baselines (`core/repo.py`). |
| **Annex B.5** | AI system impact assessment | Responsible AI Scorecard (`app/pages/11_Responsible_AI_Scorecard.py`) | Supports qualitative and quantitative impact assessments across robustness, fairness, safety, and efficiency dimensions. |
| **Annex B.7** | Data lifecycle management | Synthetic Test Generation & Curation (`core/testgen.py`) | Supports controlled test suite curation with boundary-case generation, schema validation, and slice tagging. |

---

## 4. Governance Architecture Summary

```
+-------------------------------------------------------------------------------+
|                       ORGANIZATIONAL GOVERNANCE & POLICY                       |
|   (NIST AI RMF Govern / ISO 42001 Clause 6 / EU AI Act Art. 9 Risk Policies)   |
+---------------------------------------+---------------------------------------+
                                        |
                                        v
+-------------------------------------------------------------------------------+
|                      PRE-DEPLOYMENT QUALITY GATING                            |
|  - Static Prompt Linting (Injection, Refusal, Templating)                     |
|  - Majority-5 Evaluation (55.3% Variance Reduction)                           |
|  - Exact McNemar Test (Two-Sided Paired Binomial)                             |
|  - Non-Inferiority Bootstrap CI (10,000 Resamples)                            |
|  - Holm-Bonferroni Family-Wise Slices Correction                              |
|  - Critical Invariant Gating (Zero Tolerance on Safety Tests)                 |
+---------------------------------------+---------------------------------------+
                                        |
                                        v
+-------------------------------------------------------------------------------+
|                     HUMAN OVERSIGHT & ADJUDICATION                            |
|  - Dual-Custody Change Requests (Requester != Approver)                       |
|  - Human Review Queue with Cohen's Kappa Tracking                             |
|  - Authoritative Score Overrides with Written Rationale                       |
+---------------------------------------+---------------------------------------+
                                        |
                                        v
+-------------------------------------------------------------------------------+
|                   AUDITABILITY & POST-MARKET MONITORING                       |
|  - Cryptographic SHA-256 Chained Ledger (logs/audit.jsonl)                    |
|  - Sealed Replay Bundles (Zero Model Call Verification)                       |
|  - Non-Destructive Git Rollback (Git Revert History Preservation)             |
|  - Multi-Dimensional Drift Telemetry (p50/p95 Latency, Cosine Similarity)     |
+-------------------------------------------------------------------------------+
```
