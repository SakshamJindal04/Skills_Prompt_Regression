"""
Application Shell & Main Entrypoint
Implements modern grouped sidebar navigation (st.navigation), top status shell, and design tokens.
"""

import sys
from pathlib import Path
import streamlit as st

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.ui.theme import init_theme
from app.ui.components import top_bar, safe_set_page_config
from core.db import init_db

safe_set_page_config("Skill & Prompt Regression Manager", layout="wide")
init_theme()
init_db()

pages_dir = BASE_DIR / "app" / "pages"

# Group navigation into enterprise workflow sections
pages = {
    "Overview": [
        st.Page(str(pages_dir / "0_Overview.py"), title="System Overview", icon=":material/dashboard:", default=True),
    ],
    "Changes": [
        st.Page(str(pages_dir / "1_Versions_and_Diffs.py"), title="Versions & Diffs", icon=":material/difference:"),
        st.Page(str(pages_dir / "2_Run_Comparison.py"), title="Run Comparison", icon=":material/compare_arrows:"),
        st.Page(str(pages_dir / "6_Rollback.py"), title="Rollback Workflow", icon=":material/history:"),
        st.Page(str(pages_dir / "7_Change_Requests.py"), title="Change Requests", icon=":material/rule:"),
    ],
    "Quality & Analysis": [
        st.Page(str(pages_dir / "3_Slices.py"), title="Slices & Simpson's Paradox", icon=":material/pie_chart:"),
        st.Page(str(pages_dir / "4_Skill_Activation.py"), title="Skill Activation", icon=":material/bolt:"),
        st.Page(str(pages_dir / "9_Model_Matrix.py"), title="Model Matrix", icon=":material/grid_view:"),
        st.Page(str(pages_dir / "10_Panel_Lab.py"), title="Panel Lab", icon=":material/science:"),
        st.Page(str(pages_dir / "11_Responsible_AI_Scorecard.py"), title="Responsible AI Scorecard", icon=":material/verified_user:"),
        st.Page(str(pages_dir / "12_Test_Health.py"), title="Test Health & Flakiness", icon=":material/health_and_safety:"),
    ],
    "Governance & Proof": [
        st.Page(str(pages_dir / "8_Audit_Log.py"), title="System Audit Trail", icon=":material/security:"),
        st.Page(str(pages_dir / "5_Evaluation_Results.py"), title="Evaluation Results", icon=":material/analytics:"),
        st.Page(str(pages_dir / "13_Deliverables.py"), title="Deliverables Verification", icon=":material/inventory:"),
        st.Page(str(pages_dir / "14_Project_Scorecard.py"), title="Project Scorecard", icon=":material/scoreboard:"),
    ],
}

pg = st.navigation(pages)
top_bar()
pg.run()
