# Streamlit Dashboard UI Actions & Button Inventory

This document catalogs every interactive button, submission form, and control across all 10 Streamlit dashboard pages, including its backend function, target database table, and verification via automated `AppTest`.

---

## 1. Inventory of Interactive Controls

| Page | Button / Control Label | Backend Function Call | Database / Storage Effect | AppTest Verification |
| :--- | :--- | :--- | :--- | :--- |
| **`Home.py`** | *Refresh Status* | `default_client.is_available()`, `get_active_db_type()` | Queries Ollama daemon and database connection | `tests/test_streamlit_pages.py::test_home_page` |
| **`Home.py`** | *Go to Run Tests* | `st.switch_page("pages/2_Run_Tests.py")` | Navigates to test runner | `tests/test_streamlit_pages.py::test_home_page` |
| **`Home.py`** | *Go to Compare Versions* | `st.switch_page("pages/3_Compare_Versions.py")` | Navigates to comparator | `tests/test_streamlit_pages.py::test_home_page` |
| **`Home.py`** | *Go to Change Requests* | `st.switch_page("pages/7_Change_Requests.py")` | Navigates to governance queue | `tests/test_streamlit_pages.py::test_home_page` |
| **`1_Repository.py`** | *Compare Commits (Diff)* | `core.repo:get_diff(c1, c2)` | Reads Git tree objects from `workspace/.git` | `tests/test_streamlit_pages.py::test_versions_and_diffs_page` |
| **`2_Run_Tests.py`** | *Run Test Suite* | `core.runner:run_test()`, `core.scorer:score_artifact_runs()` | Writes traces to `traces` and scores to `scores` | `tests/test_streamlit_pages.py::test_run_comparison_page` |
| **`3_Compare_Versions.py`** | *Run Statistical Comparison* | `core.comparator:compare_test_results()`, `core.gate:evaluate_gate()` | Writes comparison record to `comparisons` table | `tests/test_streamlit_pages.py::test_run_comparison_page` |
| **`3_Compare_Versions.py`** | *Download Comparison CSV* | `st.download_button()` | Streams CSV export of flip table to browser | `tests/test_streamlit_pages.py::test_run_comparison_page` |
| **`4_Slice_Heatmap.py`** | *Render Slice Breakdown* | `core.comparator:calculate_slice_metrics()` | Reads test slice tags and renders Plotly heatmap | `tests/test_streamlit_pages.py::test_slices_page` |
| **`5_Skill_Selection.py`** | *Run Skill Benchmark* | `core.skills:run_skill_benchmark()` | Computes Top-1/Top-3 accuracy and latency metrics | `tests/test_streamlit_pages.py::test_skill_activation_page` |
| **`6_Rollback.py`** | *Run Attribution Ablation* | `core.attribution:ablate_and_attribute()` | Executes single-file restores and isolates guilty commit | `tests/test_streamlit_pages.py::test_rollback_page` |
| **`6_Rollback.py`** | *Revert Commit* | `core.repo:revert_commit()` | Creates non-destructive revert commit in Git history | `tests/test_streamlit_pages.py::test_rollback_page` |
| **`7_Change_Requests.py`** | *Submit Change Request* | `core.workflow:submit_change_request()` | Inserts row into `change_requests` table with status `submitted` | `tests/test_streamlit_pages.py::test_change_requests_page` |
| **`7_Change_Requests.py`** | *Run Automated Gate* | `core.workflow:run_change_request_gate()` | Updates request status to `gated` or `rejected` | `tests/test_streamlit_pages.py::test_change_requests_page` |
| **`7_Change_Requests.py`** | *Approve & Promote* | `core.workflow:approve_change_request()` | Verifies authorization in `approvers.yaml`, promotes baseline | `tests/test_streamlit_pages.py::test_change_requests_page` |
| **`7_Change_Requests.py`** | *Reject Change Request* | `core.workflow:reject_change_request()` | Updates status to `rejected` with required reviewer comment | `tests/test_streamlit_pages.py::test_change_requests_page` |
| **`8_Audit_Log.py`** | *Filter Audit Trail* | `core.audit:get_audit_logs()` | Queries `audit_logs` table with action/verdict filters | `tests/test_streamlit_pages.py::test_audit_log_page` |
| **`8_Audit_Log.py`** | *Export Audit Report* | `core.audit:export_audit_report()` | Writes compliance summary to `results/audit_report.md` | `tests/test_streamlit_pages.py::test_audit_log_page` |
| **`9_Model_Matrix.py`** | *Drill-Down Flips Filter* | Interactive Streamlit selectionbox | Filters flip table by candidate model and outcome status | `tests/test_streamlit_pages.py::test_model_matrix_page` |
| **`9_Model_Matrix.py`** | *Download Matrix CSV* | `st.download_button()` | Streams `results/model_matrix.csv` (1,620 rows) | `tests/test_streamlit_pages.py::test_model_matrix_page` |

---

## 2. Automated AppTest Verification Results

Every page was verified using Streamlit's official `streamlit.testing.v1.AppTest` framework in `tests/test_streamlit_pages.py`:
- All 10 pages initialize without uncaught Python tracebacks.
- Form inputs validate required parameters before execution.
- Missing models, empty test cases, and database disconnections render user-facing warning banners (`st.warning`, `st.error`) rather than unhandled crash dumps.

