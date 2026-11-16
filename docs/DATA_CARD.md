# Data Card: Regression Evaluation & Benchmark Test Suites

## 1. Test Suite Composition & Overview

The regression manager repository maintains two primary test suites, one skill benchmark suite, and dynamic PromptPex suites generated at runtime:
1. **Analytics Case Study Suite (`tests_data/analytics_tests.yaml`)**: 210 comprehensive test cases partitioned across 7 evaluation families.
2. **Golden Core Suite (`tests_data/golden_tests.yaml`)**: 108 regression tests covering foundational NLP tasks (SQL query drafting, entity extraction, sentiment classification, code explanation, translation).
3. **Skill Routing Benchmark (`tests_data/skill_benchmarks.yaml`)**: 120 realistic user tasks evaluated across 5 routing categories (clear, ambiguous, paraphrased, multi-skill, out-of-scope abstention).

---

## 2. Test Families & Distribution (Analytics Case Study)

The analytics test suite (`tests_data/analytics_tests.yaml`) contains 210 tests distributed across three production targets:
- `analytics_sql`: Complex PostgreSQL analytics, aggregations, joins, and window functions.
- `doc_json_extractor`: Financial receipt, invoice, and transactional record parser.
- `meeting_summarizer`: Executive meeting notes synthesis with strict length and action-item constraints.

### Family Partitioning

| Family | Count | Primary Objective | Verification Checker |
| :--- | :--- | :--- | :--- |
| **`functional`** | 50 | Validates domain accuracy and logical task correctness. | `contains`, `not_contains`, `exact_match` |
| **`output_format`** | 30 | Enforces strict syntax (valid JSON, raw SQL, max words). | `valid_json`, `max_words`, `not_contains` |
| **`robustness`** | 30 | Assesses resilience against typographical noise, missing fields, and excessive text length. | `contains`, `valid_json`, `max_words` |
| **`safety`** | 30 | Tests defense against jailbreak attempts, system prompt extraction, and instruction overrides. | `not_contains` (system prompt keywords, drop table) |
| **`privacy`** | 25 | Asserts that personal identifiers (SSNs, credit card numbers, DOB) are redacted rather than echoed. | `not_contains` (PII values) |
| **`fairness`** | 30 | 15 counterfactual demographic pairs evaluating parity across names, dialects, and registers. | Binary pass parity calculation |
| **`consistency`** | 15 | Multi-run stability checks with fixed inputs. | Run-to-run pass rate variance |
| **Total** | **210** | **Comprehensive Case Study Coverage** | **Multi-family validation** |

---

## 3. Test Generation Methodology

### 3.1 PromptPex-Style Rule & Inverse Rule Extraction
Dynamic test generation (`core/testgen.py`) follows the PromptPex specification methodology:
1. **Rule Extraction**: An LLM agent parses the prompt and extracts operational rules ($R_i$) along with checkable parameters (e.g. `max_words: 80`, `json_keys: ["entity", "date", "amount"]`).
2. **Inverse Rule Synthesis**: For each rule $R_i$, an adversarial counter-concept $\neg R_i$ is generated (e.g. attempting to induce conversational boilerplate, unescaped markdown blocks, or exceeding word limits).
3. **Test Generation**: Positive compliance inputs and boundary challenge inputs are generated for each rule, tracking the specific parent rule ID for attribution.

### 3.2 Demographic Counterfactual Slices
To evaluate demographic parity and fairness, we authored 15 matched counterfactual pairs:
- **Demographic Names**: Matched pairs comparing traditional names with African-American, Latino, and female names (e.g., James vs Keisha, Robert vs Lakisha, William vs Tamika, David vs Jamal).
- **Register & Formality**: Standard formal English versus colloquial conversational phrasing ("Please calculate total revenue" vs "Compute the sum of completed order revenue if you can").
- **Dialect & Geographic Phrasing**: Standard business English versus regional colloquialisms ("Show all customers in Western territory" vs "Find every customer who lives out West").

The pass-rate parity gap $\Delta = |p_A - p_B|$ is computed alongside Wilson 95% score confidence intervals.

---

## 4. Known Biases & Limitations of the Test Data

1. **Synthetic Nature**: A portion of boundary and robustness tests are synthetically constructed to stress-test token filters; they may not fully capture nuanced, open-ended real-world user queries.
2. **Deterministic Check Reliance**: While deterministic string and JSON checks eliminate judge variance, they cannot verify semantic subtlety in creative or literary text.
3. **Prevalence Paradox**: In highly capable models where deterministic rules pass 100% of samples across repeated runs, the expected agreement equals observed agreement, driving Cohen's kappa $\kappa = 0.0$ despite high percentage consistency.

