# UI Audit & Functional Inventory

This document catalogs every page, interactive widget, visual chart, table, and data action in the Streamlit application prior to the enterprise visual redesign.

---

## 1. Application-Wide Structure & Navigation

- **Hosting Framework**: Streamlit multi-page application.
- **Entrypoint**: `app/Home.py`
- **Managed Pages Directory**: `app/pages/`
- **Total Pages**: 15 distinct views.
- **Runtime Persistence**: MySQL 8 primary database with automatic failover to SQLite (`regression_manager.db`), local Git workspace (`workspace/`), local Ollama runtime (`localhost:11434`), and append-only cryptographic audit logs (`logs/audit.jsonl`).

---

## 2. Page-by-Page Inventory of Widgets, Data, and Actions

### Page 0: Home (`app/Home.py`)
- **Status Indicators**:
  - Ollama service availability chip (Online / Offline with details).
  - Active Baseline info chip (Artifact ID, Name, 7-char short hash).
  - Last Gate Verdict indicator (PROMOTE / BLOCK with p-value).
- **Drift Monitor Panel**:
  - Text display of active baseline model (`qwen2.5:3b`) and live SHA-256 digest prefix.
  - Button: `Check Drift Now` (triggers `core/drift.py::check_model_drift`).
- **Live Models & Runtime Infrastructure**:
  - Interactive table of configured and discovered Ollama models (Role, Family, Parameters, Digest, Installation status, Last latency).
  - Resident VRAM Table (`/api/ps`) showing resident model names, VRAM footprints in MB, and expiration timestamps.
- **Summary KPI Cards**:
  - Registered Artifacts count.
  - Golden Test Cases count.
  - Evaluated Traces count.
  - Delta Pass Rate percentage.
- **Visualizations**:
  - Plotly line chart: Pass Rate (%) Across Artifact Versions.
- **Report Preview**:
  - Expander displaying markdown report from the most recent gate comparison.

---

### Page 1: Versions and Diffs (`app/pages/1_Versions_and_Diffs.py`)
- **Tab 1: Version History**:
  - Git Commit Log dataframe (`Commit`, `Message`, `Author`, `Date`, `Files Changed`).
  - Registered Artifacts dataframe from DB (`ID`, `Hash`, `Name`, `Path`, `Created At`).
- **Tab 2: Diff Viewer**:
  - Dropdown `Baseline Version (A)` and `Candidate Version (B)`.
  - Unified syntax-highlighted diff display (`get_diff(sha1, sha2)`).
- **Tab 3: Edit & Commit**:
  - Dropdown selector for managed prompts (`prompts/*.md`) and skills (`skills/*/SKILL.md`).
  - Multiline text area for editing raw content.
  - Text inputs: `Commit Message` and `Author`.
  - Action button: `Save and Commit` (commits to Git workspace, registers artifact in DB).
- **Tab 4: Static Quality Lint**:
  - Target artifact selector dropdown.
  - Dataframe of static lint warnings (`code`, `severity`, `message`, `line`).

---

### Page 2: Run Comparison (`app/pages/2_Run_Comparison.py`)
- **Live Test Runner (Expander)**:
  - Target artifact dropdown selector.
  - Quick Mode toggle checkbox (20 tests vs. full suite).
  - Button: `Run Live Tests` with progress bar and step message.
- **Comparison Selection Bar**:
  - Baseline Artifact dropdown.
  - Candidate Artifact dropdown.
  - Significance Alpha numerical input (default `0.05`).
- **Statistical Summary Metric Cards**:
  - Baseline Pass Rate, Candidate Pass Rate, Delta (95% Bootstrap CI), McNemar p-value with Gate verdict delta chip.
- **Alert Banners**:
  - Large PROMOTE / BLOCK status banner.
  - Simpson's Paradox warning banner (triggers if aggregate delta is flat but individual tests regressed).
- **Tab 1: Flip Table**:
  - Filter radio: `All Tests`, `Regressed (Pass -> Fail)`, `Fixed (Fail -> Pass)`.
  - Individual flip expanders displaying old output vs. new output side by side.
- **Tab 2: Change Attribution (Ablation)**:
  - Base Commit dropdown and Bad Commit dropdown.
  - Action button: `Run Ablation Attribution`.
  - Display of guilty file and file-by-file recovery impact dataframe.
- **Tab 3: Full Report**:
  - Markdown rendered `report.md`.
  - Action button: `Download report.md`.

---

### Page 3: Slices (`app/pages/3_Slices.py`)
- **Selectors**: Baseline Artifact and Candidate Artifact dropdowns.
- **Slice Breakdown Table**: Dataframe with Slice Tag, Tests count, Baseline Rate, Candidate Rate, Delta, and Verdict (`REGRESSED`, `IMPROVED`, `STABLE`).
- **Visualization**: Plotly bar chart displaying Delta (%) by test slice.
- **Documentation**: Case study explanation of Simpson's Paradox detection.

---

### Page 4: Skill Activation (`app/pages/4_Skill_Activation.py`)
- **Tab 1: Try a Task**:
  - Task query text input.
  - `with_skill` instruction injection checkbox.
  - Router selector dropdown (Embedding, BM25, Embedding + LLM Re-rank).
  - Action button: `Inspect Routing & Execute Live`.
  - Metrics: Selected Skill, Top Cosine Score, Execution Latency (ms).
  - Ranked candidates dataframe and raw agent response block.
- **Tab 2: Overlap & Similarity Matrix**:
  - Action button: `Compute Overlap Matrix`.
  - Plotly 2D interactive heatmap of pairwise cosine similarities.
  - Warning callouts for skill pairs exceeding `0.75` threshold.
- **Tab 3: 120-Task Benchmark**:
  - Action button: `Run 120-Task Benchmark`.
  - Comparison table (Top-1, Top-3, Mean, p50, p95 latencies for Embedding vs. BM25).
  - Category breakdown table (Clear, Ambiguous, Paraphrased, Multi-skill, Out-of-scope).
  - Router confusions table.
- **Tab 4: Scalability**:
  - Action button: `Run Scalability Scaling Test`.
  - Dataframe and Plotly latency curves for $N = 6, 12, 24$ skills.
- **Tab 5: Skills Catalog**:
  - Expanders for each of the 21 registered skills with metadata, triggers, and instructions.

---

### Page 5: Evaluation Results (`app/pages/5_Evaluation_Results.py`)
- **Top Actions**: Action button: `Re-run Full Evaluation` (executes 4 baselines across 26 mutations).
- **Summary Table**: Comprehensive dataframe of Precision, Recall, F1, Latency, and Cost.
- **Visualizations**:
  - Grouped bar chart: Precision, Recall, and F1 by method.
  - Bar chart: Mean Latency across methods.
  - Bar chart: Measured model calls per evaluation.
- **Exports**: Rendered markdown report and download buttons for `summary.md` and `summary.csv`.

---

### Page 6: Rollback Workflow (`app/pages/6_Rollback.py`)
- **Status Cards**: Active Baseline metadata and Current Git HEAD commit metadata.
- **Revert Selector**: Dropdown to select historical commit to revert.
- **Impact Preview**: Expected metric recovery summary from historical comparisons.
- **Diff Preview**: Unified diff block of the selected commit.
- **Execution Bar**: Rollback commit message text input and `Confirm Rollback (Git Revert)` action button.
- **Post-Rollback Verification**: Artifact selector and post-revert test scores dataframe.

---

### Page 7: Change Requests (`app/pages/7_Change_Requests.py`)
- **Policy Banner**: Current gate policy version, alpha, and sample size $k$.
- **Tab 1: Submit New Request**:
  - Base commit and Candidate commit dropdowns.
  - Requester Name text input.
  - Immediate policy gate checkbox.
  - Action button: `Submit Change Request`.
- **Tab 2: Change Request Management**:
  - Filter dropdown by status (`All`, `submitted`, `gated`, `approved`, `rejected`, `promoted`).
  - Change request selector dropdown.
  - 4 status metric cards: Status, Gate Verdict, Requester, Approver.
  - Approver Review Box: Authorized approver selectbox, required justification text area, and action buttons (`Approve & Promote Baseline`, `Reject Change Request`).
  - Separation of duties validator (`requester != approver`) and policy freeze check.
  - Report viewer and `Run Policy Gate Now` action button.

---

### Page 8: Audit Log (`app/pages/8_Audit_Log.py`)
- **Hash Chain Banner**: Live cryptographic SHA-256 chain status (VERIFIED / COMPROMISED, record count, head hash).
- **Filters**: Action filter dropdown, Verdict filter dropdown.
- **Export Button**: `Export Audit Report (Markdown)`.
- **Audit Table**: Dataframe of historical audit events with timestamps, actors, commits, verdicts, p-values, and hashes.
- **Event Detail Inspector**: Dropdown to select audit ID and inspect raw event payload.
- **Download Action**: `Download audit.jsonl` button.

---

### Page 9: Model Matrix (`app/pages/9_Model_Matrix.py`)
- **Action Bar**: Dev mode checkbox, `Run Model Study` button, `Run Judge Calibration` button.
- **Summary Metrics**: Combined suite pass rates with Wilson CIs, latencies, and verdicts per model.
- **Visualizations**:
  - Pass rate heatmap across prompt targets and models.
  - Latency bar chart across models.
- **Calibration Panel**: Observed agreement, Cohen's kappa score, and bias breakdown for LLM-as-a-judge.
- **Detailed Table**: Full metric matrix dataframe with export to CSV button.

---

### Page 10: Panel Lab (`app/pages/10_Panel_Lab.py`)
- **Advisory Notices**: Compliance methodology notice and small-sample power warning.
- **Tab 1: Interactive Lab Pipeline**:
  - Section 1: Base prompt textarea, Candidate prompt textarea, Model selectbox, $k$ repetitions, test budget $N$.
  - Section 2: Custom test inputs textarea with template insertion buttons.
  - Action button: `Run Full Lab Pipeline`.
  - Section 3: Overall pass rate, p50 latency, p95 latency, wall clock time metrics.
  - Static lint findings table.
  - Per-rule compliance breakdown table.
  - Candidate V2 Gate Comparison (Verdict, Delta pass rate, McNemar p-value, Flips $b/c$, Bootstrap CI, Flip Table drill-down).
  - Execution traces dataframe.
  - Section 4: Save to workspace button, download report markdown button, download traces CSV button.
- **Tab 2: Try a Task Live**: Ad-hoc query tester.
- **Tab 3: Add & Validate Skill**: Skill editor, YAML frontmatter validator, and save button.

---

### Page 11: Responsible AI Scorecard (`app/pages/11_Responsible_AI_Scorecard.py`)
- **Top Metrics**: Refusal Rate (Safety), Injection Success Rate, PII Leakage Rate, Fairness Parity Gap.
- **Tab 1: Test Family Breakdown**: Dataframe across 7 families with Wilson 95% CIs.
- **Tab 2: Fairness Demographic Pairs**: Counterfactual group pass rates and parity gaps.
- **Tab 3: Safety & Privacy Details**: Safety jailbreak and PII red-team test explorer.
- **Tab 4: Test Explorer & Slices**: Complete test suite explorer.

---

### Page 12: Test Health (`app/pages/12_Test_Health.py`)
- **Summary Metrics**: Evaluated tests count, Flaky count, Quarantined count, Always pass count, Stale count.
- **Tab 1: Flaky Tests**: Dataframe of tests with $0.20 \le p \le 0.80$.
- **Tab 2: Quarantined Tests**: Dataframe of tests with consistency $< 0.70$.
- **Tab 3: Always Pass / Always Fail**: Dataframe of dead-weight and unachievable tests.
- **Tab 4: Stale Tests**: Dataframe of tests unaligned with recent commit revisions.

---

### Page 13: Deliverables (`app/pages/13_Deliverables.py`)
- **Deliverables 1 to 5**:
  - 1. Skill Repository: Location, skill count, `Verify Skill Repo` button.
  - 2. Test Runner: Active adapter, checkers list, `Verify Runner` button.
  - 3. Version Comparison Dashboard: Recorded comparisons count, `Verify Comparator` button.
  - 4. Rollback Workflow: Available rollback targets, `Verify Rollback` button.
  - 5. Documented Best Practices: File existence check, `Verify & Render Doc` button.

---

### Page 14: Project Scorecard (`app/pages/14_Project_Scorecard.py`)
- **Primary Scorecard Table**: Mapping of all 5 project metrics (Skill selection, Task success delta, Regression detection recall, Run-to-run consistency, Retrieval latency) with Target, Measured, Status, and Source File.
- **Deep Dive Expanders**: Per-metric technical breakdown with methodology notes.

---

## 3. Preserved Invariants

1. **Zero Data Invention**: All tables, numbers, and charts read directly from the database, Git commits, Ollama runtime, or `results/*.csv` files.
2. **Statistical Core Untouched**: McNemar exact test, 95% bootstrap confidence intervals, and Wilson score intervals remain bit-for-bit identical.
3. **Local-First Runtime**: Zero external fonts or CDNs; all styling is self-contained.
4. **Zero Emojis**: Replaced completely with standard Material Icons (`:material/...`).
