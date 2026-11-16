import os
import sys
import argparse
from pathlib import Path
from datetime import datetime, timedelta, timezone

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.db import init_db, get_session
from core.models import Artifact, BaselineRegistry, TestCase, Trace, Score, Comparison, Version
from core.repo import init_repo, commit_changes, sync_repo_to_db, get_workspace_path
from core.versioner import register_artifact, set_current_baseline
from core.comparator import compare_test_results
from core.gate import evaluate_gate
from core.runner import sync_tests_to_db

PROMPT_SENTIMENT_V1 = """You are a sentiment classification model.
Analyze the sentiment of the user input text.
Output EXACTLY ONE of the following three words:
POSITIVE
NEGATIVE
NEUTRAL

Rules:
1. Do not include punctuation.
2. Do not include markdown formatting.
3. Do not include any explanations, sentences, or extra words.
4. Output strictly one uppercase word.

Input:
{input}
Output:
"""

PROMPT_SENTIMENT_V2 = """You are a sentiment classification model.
Analyze the sentiment of the user input text.
Output EXACTLY ONE of the following three words:
POSITIVE
NEGATIVE
NEUTRAL

Rules:
1. Do not include punctuation.
2. Do not include markdown formatting.
3. Do not include any explanations, sentences, or extra words.
4. Output strictly one uppercase word.
5. Factual financial reports without opinion (rate holds, schedules) should be classified as NEUTRAL.

Input:
{input}
Output:
"""

PROMPT_ENTITY_STRICT = """You are a precise Named Entity Recognition (NER) system.
Extract all named entities (Persons, Organizations, Locations) from the text.

Rules:
1. Return ONLY a valid JSON object. No conversational prelude or conclusion.
2. The JSON object must strictly match this structure:
{
  "entities": [
    {
      "text": "<entity name>",
      "type": "PERSON" | "ORG" | "LOC"
    }
  ]
}
3. If no entities are found, return {"entities": []}.

Input:
{input}
Output:
"""

# Silent regression: loses the "only JSON" rule and invites conversational text
PROMPT_ENTITY_BROKEN = """You are an assistant for entity extraction.
Extract all named entities (Persons, Organizations, Locations) from the text.

Provide the extracted entities in a clear and conversational manner.
You can include an introductory explanation or list the entities with details.

Input:
{input}
Output:
"""

PROMPT_SUMMARY_V1 = """You are an expert executive summarizer.
Summarize the key facts of the provided text.

Rules:
1. The summary MUST be at most 40 words in total.
2. Do not write filler intros like "Here is a summary".
3. Write in clear, dense, informative sentences.

Input:
{input}
Output:
"""

PROMPT_SUMMARY_V1_COMMENTED = """<!-- Production prompt: Short Executive Summarizer v1.1 -->
You are an expert executive summarizer.
Summarize the key facts of the provided text.

Rules:
1. The summary MUST be at most 40 words in total.
2. Do not write filler intros like "Here is a summary".
3. Write in clear, dense, informative sentences.

Input:
{input}
Output:
"""

SKILLS = {
    "summarize-text": {
        "description": "Summarize lengthy articles, transcripts, papers, documents, or meeting notes into concise executive takeaways and bullet points.",
        "steps": "1. Read document.\n2. Extract top 3 facts.\n3. Format as clean bullet points.",
    },
    "extract-entities": {
        "description": "Extract structured named entities such as people, organizations, locations, dollar amounts, dates, and products from text.",
        "steps": "1. Scan for proper nouns.\n2. Classify by entity type.\n3. Return structured list.",
    },
    "translate-text": {
        "description": "Translate text accurately between English, Spanish, French, German, Japanese, Chinese, and other languages preserving nuance.",
        "steps": "1. Detect source language.\n2. Translate into target language preserving grammar.",
    },
    "write-sql": {
        "description": "Generate, optimize, and debug SQL queries for PostgreSQL, MySQL, BigQuery, and SQLite including CTEs, joins, and aggregations.",
        "steps": "1. Identify tables and joins.\n2. Write dialect-optimized query.\n3. Add indexes/filters.",
    },
    "explain-code": {
        "description": "Explain programming code, algorithms, architectures, bugs, memory models, and design patterns across Python, TypeScript, C++, Rust, and Go.",
        "steps": "1. Review code syntax.\n2. Step through execution path.\n3. Note edge cases and complexity.",
    },
    "draft-email": {
        "description": "Draft professional business emails, cold outreach, client follow-ups, formal announcements, and customer service correspondence.",
        "steps": "1. State purpose clearly.\n2. Keep tone polite and professional.\n3. Add clear call to action.",
    },
}

SKILL_SQL_BROKEN_DESC = "Database assistant."


def setup_workspace():
    ws = get_workspace_path()
    (ws / "prompts").mkdir(parents=True, exist_ok=True)
    (ws / "skills").mkdir(parents=True, exist_ok=True)

    (ws / "prompts" / "sentiment_classifier.md").write_text(PROMPT_SENTIMENT_V1, encoding="utf-8")
    (ws / "prompts" / "entity_extractor.md").write_text(PROMPT_ENTITY_STRICT, encoding="utf-8")
    (ws / "prompts" / "short_summarizer.md").write_text(PROMPT_SUMMARY_V1, encoding="utf-8")

    for name, data in SKILLS.items():
        s_dir = ws / "skills" / name
        s_dir.mkdir(parents=True, exist_ok=True)
        content = f"---\nname: {name}\ndescription: {data['description']}\n---\n\n## Steps\n{data['steps']}\n"
        (s_dir / "SKILL.md").write_text(content, encoding="utf-8")

    (ws / "README.md").write_text("# Workspace for Prompts & Skills\n", encoding="utf-8")


def create_git_commits():
    ws = get_workspace_path()
    repo = init_repo(str(ws))
    commits = []

    setup_workspace()
    c1 = commit_changes("Initial baseline: production prompts and skills v1.0", author_name="Alice Engineer")
    commits.append(c1)

    # Commit 2: Clear improvement
    (ws / "prompts" / "sentiment_classifier.md").write_text(PROMPT_SENTIMENT_V2, encoding="utf-8")
    c2 = commit_changes("feat(sentiment): clarify neutral edge-cases and boundary conditions", author_name="Alice Engineer")
    commits.append(c2)

    # Commit 3: Harmless edit
    (ws / "prompts" / "short_summarizer.md").write_text(PROMPT_SUMMARY_V1_COMMENTED, encoding="utf-8")
    c3 = commit_changes("docs: add production maintenance notes to short_summarizer", author_name="Bob Reviewer")
    commits.append(c3)

    # Commit 4: Silent regression
    (ws / "prompts" / "entity_extractor.md").write_text(PROMPT_ENTITY_BROKEN, encoding="utf-8")
    c4 = commit_changes("refactor(entity): simplify instructions for faster generation", author_name="Charlie Dev")
    commits.append(c4)

    # Commit 5: Multi-file commit (write-sql description weakened)
    exp = ws / "skills" / "explain-code" / "SKILL.md"
    exp.write_text(exp.read_text(encoding="utf-8") + "\n- Example: Binary search\n", encoding="utf-8")

    sql_f = ws / "skills" / "write-sql" / "SKILL.md"
    sql_f.write_text(f"---\nname: write-sql\ndescription: {SKILL_SQL_BROKEN_DESC}\n---\n\n## Steps\n{SKILLS['write-sql']['steps']}\n", encoding="utf-8")
    c5 = commit_changes("feat(skills): update documentation across developer skills", author_name="Dave Contributor")
    commits.append(c5)

    # Commit 6: Release commit
    (ws / "README.md").write_text("# Workspace for Prompts & Skills\nVersion 1.2-rc\n", encoding="utf-8")
    c6 = commit_changes("chore: bump version to v1.2-rc", author_name="Alice Engineer")
    commits.append(c6)

    return commits


def seed_database_artifacts_and_traces(commits, k=5, quick_mode=False, live_mode=False):
    with get_session() as session:
        raw_tests = session.query(TestCase).all()
        test_cases = [tc.to_dict() for tc in raw_tests]

    if quick_mode:
        test_cases = test_cases[:20]
        k = min(k, 3)

    now = datetime.now(timezone.utc)
    artifact_ids = []

    mode_label = "[live-executed]" if live_mode else "[seeded sample]"

    for idx, sha in enumerate(commits):
        art_id, _ = register_artifact(
            file_paths=["prompts/sentiment_classifier.md", "prompts/entity_extractor.md", "prompts/short_summarizer.md"],
            model_id="qwen2.5:3b",
            params={"temperature": 0.7, "commit": sha, "data_source": mode_label},
            name=f"commit_{sha[:7]}",
        )
        artifact_ids.append(art_id)

    # Set baseline to Commit 1 initially
    set_current_baseline(artifact_ids[0], notes=f"{mode_label} Initial baseline commit {commits[0][:7]}")

    if live_mode:
        from core.runner import run_test
        from core.scorer import score_artifact_runs
        from core.llm import default_client
        print(f"Running live Ollama tests for baseline ({artifact_ids[0]}) and candidate ({artifact_ids[3]})...")
        base_runs_map = {}
        cand_runs_map = {}
        for art_id, c_map in [(artifact_ids[0], base_runs_map), (artifact_ids[3], cand_runs_map)]:
            for tc in test_cases:
                traces = run_test(art_id, tc, k=k, temperature=0.7, model="qwen2.5:3b", client=default_client)
                scores = score_artifact_runs(art_id, [tc], client=default_client)
                c_map[tc["id"]] = [s.get("passed", False) for s in scores[-k:]]
    else:
        traces_all = []
        base_runs_map = {}
        cand_runs_map = {}
        run_results_by_art = {}

        for idx, (sha, art_id) in enumerate(zip(commits, artifact_ids)):
            cur_runs_map = {}
            for tc in test_cases:
                tid = tc["id"]
                target = tc["target"]
                cat = tc["slices"].get("category", "")
                diff = tc["slices"].get("difficulty", "medium")

                if target == "sentiment_classifier":
                    base_p = 0.75 if (idx == 0 and (diff == "hard" or cat == "finance")) else 0.95
                elif target == "entity_extractor":
                    base_p = 0.95 if idx < 3 else (0.15 if (diff == "hard" or cat in ("finance", "legal")) else 0.40)
                elif target == "short_summarizer":
                    base_p = 0.92
                elif target == "skill_selection":
                    base_p = 0.05 if (idx >= 4 and "sql" in tid) else 0.95
                else:
                    base_p = 0.90

                run_bools = []
                for r_idx in range(k):
                    seed = 42 + r_idx * 1000
                    h = (hash(f"{sha}_{tid}_{r_idx}") % 100) / 100.0
                    passed = h < base_p
                    run_bools.append(passed)

                    if target == "sentiment_classifier":
                        out = tc["checks"][0]["value"] if passed else ("POSITIVE" if tc["checks"][0]["value"] == "NEGATIVE" else "NEGATIVE")
                    elif target == "entity_extractor":
                        out = '{"entities": [{"text": "Sample", "type": "ORG"}]}' if passed else "I found these entities: Sample."
                    elif target == "short_summarizer":
                        out = "Executive summary of key findings under forty words." if passed else ("Verbose text exceeding forty words " * 10)
                    else:
                        out = tc["checks"][0]["value"] if passed else "summarize-text"

                    tr = Trace(
                        artifact_id=art_id,
                        test_id=tid,
                        run_index=r_idx,
                        output=out,
                        skills_used=[target] if "skill" in target else [],
                        tool_calls=[],
                        latency_ms=round(85.0 + (hash(f"lat_{tid}_{r_idx}") % 70), 2),
                        seed=seed,
                        model="qwen2.5:3b",
                        temperature=0.7,
                        created_at=now - timedelta(hours=(len(commits) - idx) * 2),
                    )
                    traces_all.append(tr)

                cur_runs_map[tid] = run_bools

            run_results_by_art[art_id] = cur_runs_map
            if idx == 0:
                base_runs_map = cur_runs_map
            if idx == 3:
                cand_runs_map = cur_runs_map

        with get_session() as session:
            session.add_all(traces_all)
            session.flush()

            # Populate relational Score records
            tc_map = {tc["id"]: tc for tc in test_cases}
            scores_all = []
            for tr in traces_all:
                tc_info = tc_map.get(tr.test_id, {})
                art_runs = run_results_by_art.get(tr.artifact_id, {})
                t_runs = art_runs.get(tr.test_id, [])
                p_val = t_runs[tr.run_index] if tr.run_index < len(t_runs) else True
                chks = tc_info.get("checks", [])
                ctype = chks[0].get("type", "contains") if chks else "exact"
                sc = Score(
                    trace_id=tr.id,
                    test_id=tr.test_id,
                    artifact_id=tr.artifact_id,
                    run_index=tr.run_index,
                    passed=p_val,
                    score=1.0 if p_val else 0.0,
                    check_details=[{"type": ctype, "passed": p_val, "score": 1.0 if p_val else 0.0}],
                )
                scores_all.append(sc)
            session.add_all(scores_all)

    # Compute comparison between Baseline (Commit 1) and Candidate (Commit 4)
    if base_runs_map and cand_runs_map:
        comp_res = compare_test_results(test_cases, base_runs_map, cand_runs_map, k=k)
        verdict, report_md = evaluate_gate(
            comp_res,
            alpha=0.05,
            candidate_id=artifact_ids[3],
            baseline_id=artifact_ids[0],
        )
        print(f"Comparison evaluated: Baseline {artifact_ids[0]} vs Candidate {artifact_ids[3]} -> Verdict: {verdict}")


def main():
    parser = argparse.ArgumentParser(description="Seed demo script for regression manager")
    parser.add_argument("--quick", action="store_true", help="Run quick demo setup with k=3, 20 tests")
    parser.add_argument("--live", action="store_true", help="Run real live LLM calls with Ollama instead of seeded sample data")
    args = parser.parse_args()

    print("Initializing database...")
    init_db()

    print("Syncing golden tests...")
    sync_tests_to_db()

    print("Creating git commits in workspace/...")
    commits = create_git_commits()
    sync_repo_to_db()

    k_val = 3 if args.quick else 5
    mode_str = "live Ollama execution" if args.live else "seeded sample dataset (clearly labeled)"
    print(f"Seeding artifacts, traces (k={k_val}), and comparisons using {mode_str}...")
    seed_database_artifacts_and_traces(commits, k=k_val, quick_mode=args.quick, live_mode=args.live)

    print("\n--------------------------------------------------------------")
    print(f"Seed demo completed successfully.")
    print(f"Mode: {'[LIVE OLLAMA]' if args.live else '[SEEDED SAMPLE - CLEARLY LABELED]'}")
    print(f"Created {len(commits)} commits across workspace/. Quick mode: {args.quick}")
    print("--------------------------------------------------------------")


if __name__ == "__main__":
    main()
