"""
Versions and Diffs View
Inspect managed prompts and skills, view commit history, examine side-by-side diffs, and run static quality linting.
"""

import sys
from pathlib import Path
import streamlit as st
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.db import get_session
from core.models import Artifact
from core.repo import init_repo, list_versions, get_diff, commit_changes, get_workspace_path, sync_repo_to_db
from core.versioner import register_artifact
from core.lint import lint_prompt, lint_skill
from app.ui.theme import init_theme
from app.ui.components import (
    safe_set_page_config,
    top_bar,
    page_header,
    copyable_hash,
    status_chip,
    empty_state,
    error_panel,
    labelled_divider,
    source_caption,
)

safe_set_page_config("Versions & Diffs")
init_theme()
top_bar()

page_header(
    "Versions & Diffs Management",
    "Inspect managed prompt and skill revisions, examine unified Git diffs, author changes, and execute static lint analysis.",
)

ws = get_workspace_path()
init_repo(str(ws))

tab_list, tab_diff, tab_edit, tab_lint = st.tabs([
    "Version History",
    "Side-by-Side Diff Viewer",
    "Edit & Commit",
    "Static Quality Lint",
])

with tab_list:
    st.subheader("Git Commit History")
    st.caption("Immutable Git commit log for prompts and skills managed inside workspace/.")

    commits = list_versions()
    if commits:
        commit_rows = []
        for c in commits:
            files_str = ", ".join(c["files_changed"]) if c["files_changed"] else "none"
            commit_rows.append({
                "Commit": c["short_hash"],
                "Message": c["message"],
                "Author": c["author"],
                "Date (UTC)": c["created_at"],
                "Modified Files": files_str,
            })
        st.dataframe(pd.DataFrame(commit_rows), use_container_width=True, hide_index=True)
        source_caption("Source: Local Git repository in workspace/. Immutable commit log history.")
    else:
        empty_state("No Git commits found in workspace/.", "Use the Edit & Commit tab to commit your first prompt or skill.")

    labelled_divider("Registered Artifact Manifests in Relational Database")

    with get_session() as session:
        artifacts = session.query(Artifact).order_by(Artifact.id.desc()).all()
        art_dicts = [a.to_dict() for a in artifacts]

    if art_dicts:
        df_art = pd.DataFrame([
            {
                "ID": a["id"],
                "Hash": a["short_hash"],
                "Name": a["name"],
                "Type": a.get("type", "prompt"),
                "Path": a["path"],
                "Created At": a["created_at"][:19] if a.get("created_at") else "-",
            }
            for a in art_dicts
        ])
        st.dataframe(df_art, use_container_width=True, hide_index=True)
        source_caption("Source: Local MySQL database 'artifacts' table. Content-addressed manifests.")
    else:
        empty_state("No database artifacts recorded.", "Artifacts are automatically registered upon commit or test execution.")

with tab_diff:
    st.subheader("Unified & Colored Diff Viewer")
    st.caption("Inspect exact additions and deletions between any two commits in the workspace.")

    commits = list_versions()
    if len(commits) < 2:
        empty_state("At least two commits are required to compute a diff.", "Create another version in the Edit & Commit tab to compare changes.")
    else:
        labels = [f"{c['short_hash']} - {c['message'][:40]}" for c in commits]
        col1, col2 = st.columns(2)
        c1 = col1.selectbox("Baseline Version (A)", labels, index=min(1, len(labels) - 1))
        c2 = col2.selectbox("Candidate Version (B)", labels, index=0)

        sha1 = commits[labels.index(c1)]["git_hash"]
        sha2 = commits[labels.index(c2)]["git_hash"]

        diff_text = get_diff(sha1, sha2)
        if diff_text.strip():
            # Render visually colored diff block
            diff_lines = diff_text.split("\n")
            formatted_lines = []
            for line in diff_lines:
                if line.startswith("+") and not line.startswith("+++"):
                    formatted_lines.append(f"<div style='background: var(--arm-success-bg); color: var(--arm-success-text); padding: 1px 8px; font-family: var(--arm-font-mono); font-size: 0.85rem;'>{line}</div>")
                elif line.startswith("-") and not line.startswith("---"):
                    formatted_lines.append(f"<div style='background: var(--arm-danger-bg); color: var(--arm-danger-text); padding: 1px 8px; font-family: var(--arm-font-mono); font-size: 0.85rem;'>{line}</div>")
                elif line.startswith("@@"):
                    formatted_lines.append(f"<div style='background: var(--arm-info-bg); color: var(--arm-info-text); padding: 2px 8px; font-family: var(--arm-font-mono); font-size: 0.85rem; font-weight: 600;'>{line}</div>")
                else:
                    safe_l = line if line.strip() else "&nbsp;"
                    formatted_lines.append(f"<div style='padding: 1px 8px; font-family: var(--arm-font-mono); font-size: 0.85rem; color: var(--arm-text);'>{safe_l}</div>")

            st.markdown(
                f"<div style='border: 1px solid var(--arm-border); border-radius: var(--arm-radius-md); overflow-x: auto; padding: 8px 0; background: var(--arm-surface);'>{''.join(formatted_lines)}</div>",
                unsafe_allow_html=True,
            )
            source_caption("Source: Local Git diff between selected commits in workspace/.")
        else:
            st.info("Identical file contents detected: zero textual differences between these two commits.")

with tab_edit:
    st.subheader("Edit Artifact & Record Version")
    st.caption("Directly update prompt rules or skill definitions with form validation and instant database registration.")

    prompts = sorted(list((ws / "prompts").glob("*.md")))
    skills = sorted(list((ws / "skills").glob("*/SKILL.md")))
    all_files = [str(p.relative_to(ws)) for p in prompts + skills]

    if all_files:
        selected_file = st.selectbox("Select Target File to Edit", all_files)
        file_path = ws / selected_file
        cur_text = file_path.read_text(encoding="utf-8") if file_path.exists() else ""
        new_text = st.text_area("File Content", value=cur_text, height=280)

        c_col1, c_col2 = st.columns([2, 1])
        c_msg = c_col1.text_input("Commit Message", value="Update prompt rules")
        c_auth = c_col2.text_input("Author Name", value="Developer")

        # Form validation
        has_error = False
        if not c_msg.strip():
            st.error("Commit message cannot be empty.")
            has_error = True
        if not c_auth.strip():
            st.error("Author name cannot be empty.")
            has_error = True

        if st.button("Save & Commit Version", type="primary", disabled=has_error):
            try:
                file_path.write_text(new_text, encoding="utf-8")
                commit_sha = commit_changes(c_msg, author_name=c_auth, files=[selected_file])
                sync_repo_to_db()

                # Register artifact
                art_id, _ = register_artifact([selected_file], name=Path(selected_file).stem)
                st.success(f"Commit created: {commit_sha[:8]} (Registered as Artifact #{art_id}).")
                st.rerun()
            except Exception as e:
                error_panel(f"Failed to record commit: {e}", "Ensure workspace Git working tree is clean.")
    else:
        empty_state("No prompt or skill files found in workspace/.", "Create prompts/*.md or skills/<name>/SKILL.md in the workspace directory.")

with tab_lint:
    st.subheader("Static Quality & Safety Linter")
    st.caption("Validates prompts and skills against specification constraints, contradiction checks, vagueness, refusal directives, and prompt injection vectors.")

    prompts = sorted(list((ws / "prompts").glob("*.md")))
    skills = sorted(list((ws / "skills").glob("*/SKILL.md")))
    all_files = [str(p.relative_to(ws)) for p in prompts + skills]

    if all_files:
        lint_target = st.selectbox("Select Target to Lint", all_files, key="lint_target_select")
        target_path = ws / lint_target
        content = target_path.read_text(encoding="utf-8") if target_path.exists() else ""

        if lint_target.startswith("prompts/"):
            findings = lint_prompt(content)
        else:
            lint_res = lint_skill(target_path)
            findings = lint_res.get("findings", [])

        if findings:
            df_findings = pd.DataFrame([
                {
                    "Code": f.get("code", "rule"),
                    "Severity": f.get("severity", "warning").upper(),
                    "Message": f.get("message", ""),
                    "Line": f.get("line", "-"),
                }
                for f in findings
            ])
            st.dataframe(df_findings, use_container_width=True, hide_index=True)
            source_caption("Source: Local static lint analysis (core/lint.py) of target prompt/skill content.")
        else:
            st.success("Clean: Zero static lint violations detected. Conforms to quality and safety standards.")
    else:
        empty_state("No files available for linting.")
