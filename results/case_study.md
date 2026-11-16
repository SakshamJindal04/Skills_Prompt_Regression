# Analytics Workflow Case Study: Live Regression Detection and Approval

Date: 2026-11-10 10:45:00 UTC
Workflow Target: Enterprise Analytics & Document Extraction System
Evaluated Models: `qwen2.5:3b` (baseline) and `qwen2.5:latest` (candidate swap)
Repetitions per test: k=3 (Majority voting threshold: 2)
Total Suite Size: 30 tests across 3 tasks

## 1. Workflow Architecture & Components

The enterprise analytics workflow combines three components:
1. **PostgreSQL Analytics Query Generator** (`prompts/analytics_sql.md` + `skills/analytics-sql`):
   Translates complex natural language metric queries into join-aware SQL queries across `orders`, `customers`, and `products`.
2. **Financial Document-to-JSON Extractor** (`prompts/doc_json_extractor.md` + `skills/extract-invoice-json`):
   Extracts vendor metadata, transaction timestamps, and normalized numeric totals (`entity`, `date`, `amount`) from unstructured receipts and invoices.
3. **Executive Meeting Summarizer** (`prompts/meeting_summarizer.md` + `skills/executive-meeting-notes`):
   Condenses corporate transcripts into executive summaries under 80 words with exactly three numbered action items.

---

## 2. Experimental Scenarios and Live Results

### Scenario Summary Table

| Change ID | Description | Targeted File | Flips (b regressed, c fixed) | McNemar p-value | Gate Verdict | Change Request Decision |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Change 1** | Harmless wording edit (developer comment) | `prompts/meeting_summarizer.md` | b=0, c=0 | 1.0000 | **PROMOTE** | Approved by Alice Reviewer and promoted to baseline. |
| **Change 2** | Silent skill-description weakening (dropped schema) | `skills/analytics-sql/SKILL.md` | b=9, c=0 | 0.0039 | **BLOCK** | Blocked by gate and rejected by Bob Lead. |
| **Change 3** | Local model swap (`qwen2.5:3b` -> `qwen2.5:latest`) | `models.yaml` | b=6, c=0 | 0.0312 | **BLOCK** | Blocked by gate and rejected by Carol Admin. |

---

### Detailed Analysis of Change 1: Harmless Wording Edit
- **Modification**: Added non-executable markdown header `<!-- Production meeting summarizer v1.1 revision -->` to `prompts/meeting_summarizer.md`.
- **Measured Metrics**:
  - Regressed tests ($b$): 0
  - Fixed tests ($c$): 0
  - McNemar $p$-value: 1.0000
  - Delta Pass Rate: +0.0%
- **Gate Outcome**: Automated gate declared `PROMOTE`.
- **Approval Flow**: Change Request #10 submitted by Alice Analyst. Gating passed. Alice Reviewer (authorized in `approvers.yaml`) signed off with mandatory justification comment, promoting the version.

---

### Detailed Analysis of Change 2: Silent Skill Weakening
- **Modification**: Replaced detailed schema and dialect guidance in `skills/analytics-sql/SKILL.md` with a single sentence generic prompt: `You are a database assistant. Help with SQL.`
- **Measured Metrics**:
  - Regressed tests ($b$): 9
  - Fixed tests ($c$): 0
  - McNemar $p$-value: 0.0039
  - Critical test regressions: Detected on `sql_crit_01` (aggregations) and `sql_crit_02` (joins).
- **Gate Outcome**: Automated gate declared `BLOCK`.
- **Approval Flow**: Change Request #11 submitted by Bob Contributor. Gate intercepted regressions and automatically rejected candidate promotion.

---

### Detailed Analysis of Change 3: Local Model Swap
- **Modification**: Swapped default inference engine from `qwen2.5:3b` to `qwen2.5:latest`.
- **Measured Metrics on Representative Slice**:
  - Regressed tests ($b$): 6
  - Fixed tests ($c$): 0
  - McNemar $p$-value: 0.0312
  - Candidate Wall-Clock Latency: 191.94s (4.27s per call)
- **Gate Outcome**: `BLOCK`.
- **Governance Audit**: Change Request #12 recorded in system audit trail.

---

## 3. Governance and Audit Log Trail

Every stage of this case study generated immutable audit trail entries in `logs/audit.jsonl` and the database `audit_logs` table:
1. `submit_change_request` for CR #10, #11, and #12.
2. `gate_evaluation_promote` and `gate_evaluation_block` logging exact $(b, c)$ counts and $p$-values.
3. `approve_and_promote` verifying approver permissions against `approvers.yaml`.
4. `reject_change_request` documenting root-cause justifications.
