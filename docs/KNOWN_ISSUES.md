# Known Issues & Operational Considerations

This document records operational edge cases, platform dependencies, and known constraints in the current implementation.

---

## 1. Multiple Concurrent Models in Ollama on 16GB Machines
- **Issue**: Attempting to query `qwen2.5:3b`, `llama3.2:3b`, and `gemma2:2b` simultaneously without configuring memory limits can cause macOS Unified Memory or Linux swap pressure.
- **Resolution**: We advise setting `export OLLAMA_MAX_LOADED_MODELS=1` in developer environments. Ollama automatically unloads the previous model before serving the next, keeping VRAM utilization below 4GB.

---

## 2. Preamble Text in 3B Model JSON Outputs
- **Issue**: Without strict formatting constraints, 3B models occasionally prepend conversational pleasantries (e.g., *"Here is the requested JSON output:"*) before the JSON object, which causes standard `json.loads()` to raise `JSONDecodeError`.
- **Resolution**: `core/checkers.py` incorporates `extract_json_from_text()`, which uses regular expression bracket matching (`r'\{.*\}'`) and markdown code block extraction to safely isolate JSON payloads before schema validation.

---

## 3. Small-Sample Statistical Power in Exact McNemar Testing
- **Issue**: For exact two-sided McNemar testing at $\alpha = 0.05$ with $c = 0$ fixes, the minimum number of discordant regressions required for statistical significance is $b = 6$ ($0.5^{6-1} = 0.03125 \le 0.05$). For small evaluation sets ($N \le 20$), this requires a $\ge 30\%$ drop.
- **Resolution**: Handled via two complementary mechanisms: (1) `regguard power --n N --k K` provides upfront power warnings and recommended sample sizes; (2) Critical test invariants bypass aggregate p-values, immediately blocking deployment if any critical test regresses ($b_{\text{crit}} \ge 1$).

---

## 4. Multi-Hop Trajectory Reasoning in 3B Parameter Models
- **Issue**: Highly compressed 3B local models (e.g. Qwen 2.5 3B) achieve strong performance on single-step tool execution (calculator, document lookup, SQLite queries), but can struggle with 3+ step compositional reasoning without explicit few-shot trajectories.
- **Resolution**: The agent execution loop enforces step-count limits ($\le 5$), identical-action loop detection, and argument schema validation, terminating looping executions deterministically.

---

## 5. Append-Only Audit Log Constraints
- **Issue**: Direct SQL `UPDATE` or `DELETE` statements on `audit_logs` fail by design via SQLAlchemy event listeners (`before_update`, `before_delete`) to maintain regulatory compliance.
- **Resolution**: Corrections must be appended as new audit entries referencing previous record IDs; test fixtures that reset database state must rebuild tables using `Base.metadata.drop_all()` rather than issuing bulk deletes.
