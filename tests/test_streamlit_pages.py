from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest

BASE_DIR = Path(__file__).resolve().parent.parent


def _run_page_test(page_rel_path: str):
    at = AppTest.from_file(str(BASE_DIR / page_rel_path))
    at.run(timeout=10)
    assert not at.exception
    return at


def test_home_page():
    _run_page_test("app/Home.py")


def test_overview_page():
    _run_page_test("app/pages/0_Overview.py")


def test_versions_and_diffs_page():
    _run_page_test("app/pages/1_Versions_and_Diffs.py")


def test_run_comparison_page():
    _run_page_test("app/pages/2_Run_Comparison.py")


def test_slices_page():
    _run_page_test("app/pages/3_Slices.py")


def test_skill_activation_page():
    _run_page_test("app/pages/4_Skill_Activation.py")


def test_evaluation_results_page():
    _run_page_test("app/pages/5_Evaluation_Results.py")


def test_rollback_page():
    _run_page_test("app/pages/6_Rollback.py")


def test_change_requests_page():
    _run_page_test("app/pages/7_Change_Requests.py")


def test_audit_log_page():
    _run_page_test("app/pages/8_Audit_Log.py")


def test_model_matrix_page():
    _run_page_test("app/pages/9_Model_Matrix.py")


def test_panel_lab_page():
    _run_page_test("app/pages/10_Panel_Lab.py")


def test_responsible_ai_scorecard_page():
    _run_page_test("app/pages/11_Responsible_AI_Scorecard.py")


def test_test_health_page():
    _run_page_test("app/pages/12_Test_Health.py")


def test_deliverables_page():
    _run_page_test("app/pages/13_Deliverables.py")


def test_project_scorecard_page():
    _run_page_test("app/pages/14_Project_Scorecard.py")


def test_human_review_page():
    _run_page_test("app/pages/15_Human_Review.py")


def test_environments_page():
    _run_page_test("app/pages/16_Environments.py")
