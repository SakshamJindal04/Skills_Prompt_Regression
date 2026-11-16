"""
Automated Playwright Screenshot and Console Error Verification Script.
Captures full-page screenshots of all 17 dashboard views across:
- Light and Dark modes
- 1280x800, 1440x900 and 1920x1080 viewport resolutions
Verifies that 0 browser console errors are raised across all views.
"""

import sys
import argparse
import time
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE_DIR = Path(__file__).resolve().parent.parent

PAGES = [
    {"slug": "00_overview", "nav": "System Overview", "name": "System Overview"},
    {"slug": "01_versions_and_diffs", "nav": "Versions & Diffs", "name": "Versions and Diffs"},
    {"slug": "02_run_comparison", "nav": "Run Comparison", "name": "Run Comparison"},
    {"slug": "03_slices", "nav": "Slices & Simpson's Paradox", "name": "Slices Breakdown"},
    {"slug": "04_skill_activation", "nav": "Skill Activation", "name": "Skill Activation"},
    {"slug": "05_evaluation_results", "nav": "Evaluation Results", "name": "Evaluation Results"},
    {"slug": "06_rollback", "nav": "Rollback Workflow", "name": "Rollback Workflow"},
    {"slug": "07_change_requests", "nav": "Change Requests", "name": "Change Requests"},
    {"slug": "08_audit_log", "nav": "System Audit Trail", "name": "Audit Log"},
    {"slug": "09_model_matrix", "nav": "Model Matrix", "name": "Model Matrix"},
    {"slug": "10_panel_lab", "nav": "Panel Lab", "name": "Panel Lab"},
    {"slug": "11_responsible_ai_scorecard", "nav": "Responsible AI Scorecard", "name": "Responsible AI Scorecard"},
    {"slug": "12_test_health", "nav": "Test Health & Flakiness", "name": "Test Health"},
    {"slug": "13_deliverables", "nav": "Deliverables Verification", "name": "Deliverables Verification"},
    {"slug": "14_project_scorecard", "nav": "Project Scorecard", "name": "Project Scorecard"},
    {"slug": "15_human_review", "nav": "Human Review Queue", "name": "Human Review Queue"},
    {"slug": "16_environments", "nav": "Environments & Releases", "name": "Environments & Releases"},
]

RESOLUTIONS = [
    {"name": "1280x800", "width": 1280, "height": 800},
    {"name": "1440x900", "width": 1440, "height": 900},
    {"name": "1920x1080", "width": 1920, "height": 1080},
]

THEMES = ["light", "dark"]


def run_capture(target_dir: Path, quick: bool = False):
    target_dir.mkdir(parents=True, exist_ok=True)
    active_resolutions = [RESOLUTIONS[1]] if quick else RESOLUTIONS

    results = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "target_dir": str(target_dir),
        "pages_tested": len(PAGES),
        "screenshots_captured": 0,
        "load_times_ms": {},
        "console_errors": {},
        "status": "PASS",
    }

    print(f"Starting Playwright UI Capture across {len(PAGES)} pages -> {target_dir}...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        for theme in THEMES:
            for res in active_resolutions:
                res_name = res["name"]
                print(f"\n--- Testing Theme: {theme.upper()} | Viewport: {res_name} ---")

                context = browser.new_context(
                    viewport={"width": res["width"], "height": res["height"]},
                    color_scheme=theme,
                )

                page = context.new_page()
                errors_for_context = []

                def on_console(msg):
                    if msg.type in ("error", "assert"):
                        text = msg.text
                        if "favicon.ico" not in text and "use_container_width" not in text:
                            errors_for_context.append(f"[{msg.type}] {text}")

                def on_page_error(exc):
                    errors_for_context.append(f"[pageerror] {exc}")

                page.on("console", on_console)
                page.on("pageerror", on_page_error)

                # Cold load root
                page.goto("http://localhost:8501/", wait_until="networkidle", timeout=30000)
                page.wait_for_timeout(600)

                for page_info in PAGES:
                    slug = page_info["slug"]
                    nav_text = page_info["nav"]
                    errors_for_context.clear()

                    t0 = time.time()
                    link = page.locator("[data-testid='stSidebar'] a").filter(has_text=nav_text).first
                    link.click()

                    page.wait_for_load_state("networkidle")
                    page.wait_for_timeout(600)
                    t_load = (time.time() - t0) * 1000

                    if theme == "light" and res_name == "1440x900":
                        results["load_times_ms"][slug] = round(t_load, 1)

                    img_name = f"{slug}_{theme}_{res_name}.png"
                    img_path = target_dir / img_name

                    page.screenshot(path=str(img_path), full_page=True)
                    results["screenshots_captured"] += 1

                    if errors_for_context:
                        key = f"{slug}_{theme}_{res_name}"
                        results["console_errors"][key] = list(errors_for_context)
                        print(f" [!] {page_info['name']} ({theme}, {res_name}): {len(errors_for_context)} console errors: {errors_for_context}")
                    else:
                        print(f" [OK] {page_info['name']} ({theme}, {res_name}) -> {img_name} ({t_load:.0f}ms)")

                context.close()

        browser.close()

    error_count = sum(len(errs) for errs in results["console_errors"].values())
    results["status"] = "PASS" if error_count == 0 else "FAIL"
    print(f"\nCompleted: {results['screenshots_captured']} screenshots captured into {target_dir} (Status: {results['status']}).")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-dir", default="docs/screenshots/before", help="Output directory for screenshots")
    parser.add_argument("--quick", action="store_true", help="Capture single resolution (1440x900) for faster capture")
    args = parser.parse_args()

    out_dir = BASE_DIR / args.target_dir
    run_capture(out_dir, quick=args.quick)
