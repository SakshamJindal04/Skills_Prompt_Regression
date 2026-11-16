from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest

BASE_DIR = Path(__file__).resolve().parent.parent


def test_home_page():
    at = AppTest.from_file(str(BASE_DIR / "app" / "Home.py")).run()
    assert not at.exception


def test_overview_page():
    at = AppTest.from_file(str(BASE_DIR / "app" / "pages" / "0_Overview.py")).run()
    assert not at.exception


def test_versions_and_diffs_page():
    at = AppTest.from_file(str(BASE_DIR / "app" / "pages" / "1_Versions_and_Diffs.py")).run()
    assert not at.exception


def test_run_comparison_page():
    at = AppTest.from_file(str(BASE_DIR / "app" / "pages" / "2_Run_Comparison.py")).run()
    assert not at.exception


def test_slices_page():
    at = AppTest.from_file(str(BASE_DIR / "app" / "pages" / "3_Slices.py")).run()
    assert not at.exception


def test_skill_activation_page():
    at = AppTest.from_file(str(BASE_DIR / "app" / "pages" / "4_Skill_Activation.py")).run()
    assert not at.exception


def test_evaluation_results_page():
    at = AppTest.from_file(str(BASE_DIR / "app" / "pages" / "5_Evaluation_Results.py")).run()
    assert not at.exception


def test_rollback_page():
    at = AppTest.from_file(str(BASE_DIR / "app" / "pages" / "6_Rollback.py")).run()
    assert not at.exception


def test_change_requests_page():
    at = AppTest.from_file(str(BASE_DIR / "app" / "pages" / "7_Change_Requests.py")).run()
    assert not at.exception


def test_audit_log_page():
    at = AppTest.from_file(str(BASE_DIR / "app" / "pages" / "8_Audit_Log.py")).run()
    assert not at.exception


def test_model_matrix_page():
    at = AppTest.from_file(str(BASE_DIR / "app" / "pages" / "9_Model_Matrix.py")).run()
    assert not at.exception


def test_panel_lab_page():
    at = AppTest.from_file(str(BASE_DIR / "app" / "pages" / "10_Panel_Lab.py")).run()
    assert not at.exception


def test_responsible_ai_scorecard_page():
    at = AppTest.from_file(str(BASE_DIR / "app" / "pages" / "11_Responsible_AI_Scorecard.py")).run()
    assert not at.exception


def test_test_health_page():
    at = AppTest.from_file(str(BASE_DIR / "app" / "pages" / "12_Test_Health.py")).run()
    assert not at.exception


def test_deliverables_page():
    at = AppTest.from_file(str(BASE_DIR / "app" / "pages" / "13_Deliverables.py")).run()
    assert not at.exception


def test_project_scorecard_page():
    at = AppTest.from_file(str(BASE_DIR / "app" / "pages" / "14_Project_Scorecard.py")).run()
    assert not at.exception

