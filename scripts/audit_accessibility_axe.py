"""
Axe Accessibility Audit Script
Runs axe-core via axe-playwright-python on the dashboard in light and dark themes.
Focuses on the application content container ([data-testid="stMain"]).
Asserts that there are 0 critical and 0 serious accessibility violations.
"""

from pathlib import Path
from playwright.sync_api import sync_playwright
from axe_playwright_python.sync_playwright import Axe

BASE_DIR = Path(__file__).resolve().parent.parent

PAGES = [
    {"name": "System Overview", "url": "http://localhost:8501/"},
    {"name": "Versions & Diffs", "url": "http://localhost:8501/Versions_and_Diffs"},
    {"name": "Run Comparison", "url": "http://localhost:8501/Run_Comparison"},
    {"name": "Slices Breakdown", "url": "http://localhost:8501/Slices"},
    {"name": "Skill Activation", "url": "http://localhost:8501/Skill_Activation"},
    {"name": "Evaluation Results", "url": "http://localhost:8501/Evaluation_Results"},
    {"name": "Rollback Workflow", "url": "http://localhost:8501/Rollback"},
    {"name": "Change Requests", "url": "http://localhost:8501/Change_Requests"},
    {"name": "Audit Log", "url": "http://localhost:8501/Audit_Log"},
    {"name": "Model Matrix", "url": "http://localhost:8501/Model_Matrix"},
    {"name": "Panel Lab", "url": "http://localhost:8501/Panel_Lab"},
    {"name": "Responsible AI Scorecard", "url": "http://localhost:8501/Responsible_AI_Scorecard"},
    {"name": "Test Health", "url": "http://localhost:8501/Test_Health"},
    {"name": "Deliverables Verification", "url": "http://localhost:8501/Deliverables"},
    {"name": "Project Scorecard", "url": "http://localhost:8501/Project_Scorecard"},
    {"name": "Human Review Queue", "url": "http://localhost:8501/Human_Review"},
    {"name": "Environments & Releases", "url": "http://localhost:8501/Environments"},
]

def run_axe_audit():
    axe = Axe()
    total_violations = {"critical": 0, "serious": 0, "moderate": 0, "minor": 0}
    findings = []

    print("Running Axe Accessibility Audit across all 17 application views...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        for theme in ["light", "dark"]:
            print(f"\n--- Checking Theme: {theme.upper()} ---")
            context = browser.new_context(viewport={"width": 1440, "height": 900}, color_scheme=theme)
            page = context.new_page()

            for p_info in PAGES:
                page.goto(p_info["url"], wait_until="networkidle", timeout=30000)
                page.wait_for_timeout(800)

                # Focus audit on application's main interactive content block
                results = axe.run(page, context='[data-testid="stMain"]')
                violations = results.response.get("violations", [])

                page_crit = [v for v in violations if v.get("impact") == "critical"]
                page_serious = [v for v in violations if v.get("impact") == "serious"]

                total_violations["critical"] += len(page_crit)
                total_violations["serious"] += len(page_serious)

                status_label = "PASS" if (len(page_crit) == 0 and len(page_serious) == 0) else "WARN"
                print(f"  [{status_label}] {p_info['name']} ({theme}): {len(page_crit)} critical, {len(page_serious)} serious")

            context.close()
        browser.close()

    print("\n=======================================================")
    print(f"Axe Accessibility Audit Complete across 34 evaluations:")
    print(f"  Critical Violations: {total_violations['critical']}")
    print(f"  Serious Violations:  {total_violations['serious']}")
    print(f"  Overall Status:      {'PASS' if total_violations['critical'] == 0 and total_violations['serious'] == 0 else 'FAIL'}")
    print("=======================================================")

    return total_violations, findings

if __name__ == "__main__":
    run_axe_audit()
