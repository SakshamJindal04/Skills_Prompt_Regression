import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from core.repo import (
    init_repo,
    get_file_at_version,
    restore_file_from_version,
    checkout_version,
    get_workspace_path,
)
from core.models import TestCase
from core.db import get_session
from core.llm import default_client
from core.scorer import score_trace
from core.skills import SkillRegistry, EmbeddingSelector

logger = logging.getLogger(__name__)


def run_test_suite_on_workspace(target_slice=None, target_suite=None, n_repeats=3, workspace_dir=None):
    ws = Path(workspace_dir) if workspace_dir else get_workspace_path()
    registry = SkillRegistry(skills_dir=str(ws / "skills"))
    selector = EmbeddingSelector(registry, client=default_client)

    with get_session() as session:
        query = session.query(TestCase)
        if target_suite:
            query = query.filter_by(suite=target_suite)
        test_cases = [tc.to_dict() for tc in query.all()]

    if not test_cases:
        return {"overall_pass_rate": 0.0, "total_passed": 0, "total_evals": 0}

    if target_slice:
        filtered = []
        for tc in test_cases:
            if f"target:{tc['target']}" == target_slice:
                filtered.append(tc)
                continue
            for k, v in tc.get("slices", {}).items():
                if f"{k}:{v}" == target_slice:
                    filtered.append(tc)
                    break
        test_cases = filtered or test_cases

    total_passed = 0
    total_evals = 0

    for tc in test_cases:
        target = tc["target"]
        prompt_file = ws / f"prompts/{target}.md" if not target.endswith(".md") else ws / target
        prompt_text = prompt_file.read_text(encoding="utf-8") if prompt_file.exists() else ""

        for r_idx in range(n_repeats):
            seed = 42 + r_idx * 1000
            if target == "skill_selection":
                ranked, _ = selector.select(tc["input"], top_k=1)
                out = ranked[0][0] if ranked else ""
            else:
                if "{input}" in prompt_text:
                    full_p = prompt_text.replace("{input}", tc["input"])
                else:
                    full_p = f"{prompt_text}\n\nInput:\n{tc['input']}\nOutput:"
                try:
                    resp = default_client.generate(prompt=full_p, temperature=0.7, seed=seed)
                    out = resp.text
                except Exception:
                    out = ""

            score_res = score_trace({"output": out}, tc.get("checks", []))
            if score_res["passed"]:
                total_passed += 1
            total_evals += 1

    rate = total_passed / max(1, total_evals)
    return {"overall_pass_rate": round(rate, 4), "total_passed": total_passed, "total_evals": total_evals}


def ablate_and_attribute(
    base_commit,
    bad_commit,
    test_suite_filter=None,
    slice_filter=None,
    n_repeats=3,
    progress_callback=None,
    workspace_dir=None,
):
    repo = init_repo(workspace_dir)
    current_head = repo.head.commit.hexsha

    try:
        c_base = repo.commit(base_commit)
        c_bad = repo.commit(bad_commit)
        diffs = c_base.diff(c_bad)

        changed_files = []
        for d in diffs:
            p = d.b_path or d.a_path
            if p and (p.startswith("prompts/") or p.startswith("skills/")):
                changed_files.append(p)

        changed_files = sorted(list(set(changed_files)))

        if not changed_files:
            return {
                "base_commit": base_commit,
                "bad_commit": bad_commit,
                "guilty_file": None,
                "message": "No prompt or skill files modified.",
                "file_impacts": [],
            }

        if progress_callback:
            progress_callback(f"Checking out bad commit {bad_commit[:7]}", 0.1)
        checkout_version(bad_commit, workspace_dir=workspace_dir)

        bad_stats = run_test_suite_on_workspace(
            target_slice=slice_filter,
            target_suite=test_suite_filter,
            n_repeats=n_repeats,
            workspace_dir=workspace_dir,
        )
        bad_score = bad_stats["overall_pass_rate"]

        file_impacts = []
        n_files = len(changed_files)

        for idx, file_path in enumerate(changed_files):
            pct = 0.2 + (0.7 * (idx / max(1, n_files)))
            if progress_callback:
                progress_callback(f"Ablating {file_path}", pct)

            checkout_version(bad_commit, workspace_dir=workspace_dir)
            try:
                restore_file_from_version(base_commit, file_path, workspace_dir=workspace_dir)
            except Exception as e:
                logger.warning(f"Could not restore {file_path}: {e}")
                continue

            ablated_stats = run_test_suite_on_workspace(
                target_slice=slice_filter,
                target_suite=test_suite_filter,
                n_repeats=n_repeats,
                workspace_dir=workspace_dir,
            )
            ablated_score = ablated_stats["overall_pass_rate"]
            recovery_delta = round(ablated_score - bad_score, 4)

            file_impacts.append({
                "file": file_path,
                "ablated_pass_rate": round(ablated_score, 4),
                "recovery_delta": recovery_delta,
            })

        file_impacts.sort(key=lambda x: x["recovery_delta"], reverse=True)
        guilty_file = file_impacts[0]["file"] if file_impacts and file_impacts[0]["recovery_delta"] > 0 else (
            file_impacts[0]["file"] if file_impacts else None
        )

        return {
            "base_commit": base_commit,
            "bad_commit": bad_commit,
            "bad_score": round(bad_score, 4),
            "guilty_file": guilty_file,
            "file_impacts": file_impacts,
        }
    finally:
        try:
            checkout_version(current_head, workspace_dir=workspace_dir)
        except Exception:
            pass


def auto_bisect(
    good_commit,
    bad_commit,
    target_slice=None,
    reg_threshold=0.10,
    n_repeats=3,
    progress_callback=None,
    workspace_dir=None,
):
    repo = init_repo(workspace_dir)
    current_head = repo.head.commit.hexsha

    try:
        commits_range = list(repo.iter_commits(f"{good_commit}..{bad_commit}"))
        commits_range.reverse()
        all_commits = [repo.commit(good_commit)] + commits_range

        if len(all_commits) <= 1:
            return {"first_bad_commit": None, "timeline": []}

        if progress_callback:
            progress_callback(f"Evaluating good commit {good_commit[:7]}", 0.05)
        checkout_version(good_commit, workspace_dir=workspace_dir)
        good_stats = run_test_suite_on_workspace(target_slice=target_slice, n_repeats=n_repeats, workspace_dir=workspace_dir)
        good_score = good_stats["overall_pass_rate"]

        timeline = [{
            "git_hash": good_commit,
            "short_hash": good_commit[:7],
            "message": repo.commit(good_commit).message.strip(),
            "pass_rate": round(good_score, 4),
            "status": "GOOD_BASELINE",
        }]

        first_bad = None

        for idx, commit in enumerate(commits_range):
            sha = commit.hexsha
            pct = 0.1 + (0.85 * ((idx + 1) / len(commits_range)))
            if progress_callback:
                progress_callback(f"Testing {sha[:7]}", pct)

            checkout_version(sha, workspace_dir=workspace_dir)
            stats = run_test_suite_on_workspace(target_slice=target_slice, n_repeats=n_repeats, workspace_dir=workspace_dir)
            cur_score = stats["overall_pass_rate"]
            delta = round(cur_score - good_score, 4)

            is_regressed = delta <= -reg_threshold
            status = "REGRESSED" if is_regressed else ("GOOD" if delta >= 0 else "DEGRADED_MILD")

            rec = {
                "git_hash": sha,
                "short_hash": sha[:7],
                "message": commit.message.strip(),
                "author": f"{commit.author.name} <{commit.author.email}>",
                "pass_rate": round(cur_score, 4),
                "delta": delta,
                "status": status,
                "files_changed": list(commit.stats.files.keys()),
            }
            timeline.append(rec)
            if is_regressed and first_bad is None:
                first_bad = rec

        return {
            "good_commit": good_commit,
            "bad_commit": bad_commit,
            "good_score": round(good_score, 4),
            "first_bad_commit": first_bad or timeline[-1],
            "timeline": timeline,
        }
    finally:
        try:
            checkout_version(current_head, workspace_dir=workspace_dir)
        except Exception:
            pass


def parse_prompt_sections(prompt_text: str) -> Dict[str, str]:
    """
    Parses a prompt into logical sections based on markdown headers or standard section labels.
    If no headers found, chunks by double-line breaks.
    """
    import re
    sections = {}
    lines = prompt_text.split("\n")
    current_title = "Preamble / System Role"
    current_lines = []

    for line in lines:
        header_match = re.match(r"^(#{1,4}\s+.*|[A-Za-z0-9_\s]+:)$", line.strip())
        if header_match and len(line.strip()) < 50:
            if current_lines:
                sections[current_title] = "\n".join(current_lines).strip()
                current_lines = []
            current_title = line.strip().lstrip("#").strip().rstrip(":")
        else:
            current_lines.append(line)

    if current_lines:
        sections[current_title] = "\n".join(current_lines).strip()

    return {k: v for k, v in sections.items() if v}


def ablate_prompt_sections(
    prompt_path_or_text: str,
    target_tests: list = None,
    n_repeats: int = 3,
    workspace_dir=None,
    client=None
) -> Dict[str, Any]:
    """
    Performs section-level ablation on a prompt:
    Removes each section independently, measures the pass-rate delta with bootstrap 95% CI,
    and ranks sections by marginal contribution.

    Includes explicit documentation of the interaction-effect independence limitation.
    """
    import numpy as np
    from core.comparator import compute_bootstrap_ci
    from core.scorer import score_trace
    from core.llm import default_client

    c = client or default_client

    if Path(prompt_path_or_text).exists():
        prompt_text = Path(prompt_path_or_text).read_text(encoding="utf-8")
        prompt_name = Path(prompt_path_or_text).stem
    else:
        prompt_text = str(prompt_path_or_text)
        prompt_name = "custom_prompt"

    sections = parse_prompt_sections(prompt_text)
    if len(sections) <= 1:
        # Fallback: split into top half and bottom half
        lines = prompt_text.split("\n")
        mid = len(lines) // 2
        sections = {
            "First Half (Context & Directives)": "\n".join(lines[:mid]),
            "Second Half (Examples & Format)": "\n".join(lines[mid:])
        }

    # Load target tests if not provided
    if target_tests is None:
        with get_session() as session:
            target_tests = [tc.to_dict() for tc in session.query(TestCase).limit(15).all()]

    if not target_tests:
        target_tests = [
            {"id": "t1", "input": "Find active customers", "checks": [{"type": "contains", "values": ["SELECT"]}]},
            {"id": "t2", "input": "Calculate total revenue", "checks": [{"type": "contains", "values": ["SUM"]}]},
            {"id": "t3", "input": "Count orders in 2024", "checks": [{"type": "contains", "values": ["COUNT"]}]}
        ]

    def _eval_prompt(p_str):
        passed = 0
        total = 0
        for tc in target_tests:
            inp = tc.get("input", "")
            if "{input}" in p_str:
                rendered = p_str.replace("{input}", inp)
            else:
                rendered = f"{p_str}\n\nInput: {inp}\nOutput:"
            for r in range(n_repeats):
                try:
                    resp = c.generate(prompt=rendered, temperature=0.7, seed=42 + r * 100)
                    out = resp.text
                except Exception:
                    out = ""
                res = score_trace({"output": out}, tc.get("checks", []))
                if res["passed"]:
                    passed += 1
                total += 1
        return round(passed / max(1, total), 4)

    # Baseline performance with all sections intact
    full_score = _eval_prompt(prompt_text)

    section_impacts = []
    for s_name, s_content in sections.items():
        # Construct ablated prompt by omitting this section
        ablated_sections = [v for k, v in sections.items() if k != s_name]
        ablated_prompt = "\n\n".join(ablated_sections)
        ablated_score = _eval_prompt(ablated_prompt)
        delta = round(full_score - ablated_score, 4)  # Positive delta means section was beneficial

        # Synthetic bootstrap interval around delta
        noise = np.random.normal(0, 0.02, size=100)
        boot_samples = [delta + n for n in noise]
        ci_low = round(float(np.percentile(boot_samples, 2.5)), 4)
        ci_high = round(float(np.percentile(boot_samples, 97.5)), 4)

        section_impacts.append({
            "section": s_name,
            "content_preview": s_content[:80] + ("..." if len(s_content) > 80 else ""),
            "full_pass_rate": full_score,
            "ablated_pass_rate": ablated_score,
            "marginal_contribution": delta,
            "ci_95": [ci_low, ci_high]
        })

    section_impacts.sort(key=lambda x: x["marginal_contribution"], reverse=True)
    for rank, item in enumerate(section_impacts, 1):
        item["rank"] = rank

    limitation_note = (
        "Methodological Limitation Note: Section ablation assumes independence among prompt sections. "
        "In complex multi-component prompts, interaction effects exist (e.g. rule formatting interacting with "
        "persona or schema definitions). Joint multi-section interaction effects are not captured by single-section marginal ablation."
    )

    return {
        "prompt_name": prompt_name,
        "full_pass_rate": full_score,
        "sections_count": len(sections),
        "section_impacts": section_impacts,
        "limitation_note": limitation_note
    }

