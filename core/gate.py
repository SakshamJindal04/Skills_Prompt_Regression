import os
import sys
import argparse
import logging
from pathlib import Path
import requests
from dotenv import load_dotenv

from core.db import get_session
from core.models import Comparison, BaselineRegistry, Artifact
from core.versioner import get_current_baseline, set_current_baseline
from core.reporter import generate_markdown_report
from core.policy import load_policy
from core.audit import record_audit_event
from core.decision_rules import evaluate_all_decision_rules

load_dotenv()
logger = logging.getLogger("gate")


def send_alert(message, verdict, candidate_id):
    # Log to local alert log file
    log_dir = Path(__file__).resolve().parent.parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    with open(log_dir / "alerts.log", "a", encoding="utf-8") as f:
        f.write(f"[{verdict}] Candidate {candidate_id}: {message}\n")

    # Optional webhook from .env
    webhook_url = os.getenv("ALERT_WEBHOOK_URL")
    if webhook_url:
        try:
            requests.post(webhook_url, json={"text": f"[{verdict}] {message}"}, timeout=5)
        except Exception:
            pass


def evaluate_gate(
    comparison,
    alpha=None,
    candidate_id=None,
    baseline_id=None,
    auto_promote=True,
    policy_version=None,
    base_model=None,
    cand_model=None,
    base_digest=None,
    cand_digest=None,
):
    """
    Gate policy:
    Verdict BLOCK if (p < alpha AND regressed > fixed) OR any test marked critical regressed; else PROMOTE.
    Parameters read from policy.yaml unless explicitly passed.
    """
    policy = load_policy()
    if alpha is None:
        alpha = policy.get("alpha", 0.05)
    if policy_version is None:
        policy_version = policy.get("version", "1.0.0")

    policy_crit_ids = set(policy.get("critical_test_ids", []))

    b = comparison["regressed_count"]
    c = comparison["fixed_count"]
    p_val = comparison["p_value"]

    # Evaluate all 4 frozen decision rules
    active_rule = policy.get("active_decision_rule", "mcnemar_exact")
    margin = policy.get("non_inferiority_margin", 0.05)
    or_thresh = policy.get("odds_ratio_threshold", 1.5)

    all_rules_eval = evaluate_all_decision_rules(
        comparison,
        alpha=alpha,
        margin=margin,
        odds_ratio_threshold=or_thresh,
        policy_critical_ids=policy_crit_ids,
    )
    comparison["decision_rules"] = all_rules_eval

    # Selected rule determines primary verdict
    primary_eval = all_rules_eval.get(active_rule, all_rules_eval["mcnemar_exact"])
    verdict = primary_eval["verdict"]
    reason = primary_eval["reason"]

    report_md = generate_markdown_report(
        comparison,
        candidate_id=candidate_id,
        baseline_id=baseline_id,
        verdict=verdict,
        policy_version=policy_version,
        base_model=base_model,
        cand_model=cand_model,
        base_digest=base_digest,
        cand_digest=cand_digest,
    )

    # Save to database
    if candidate_id and baseline_id:
        with get_session() as session:
            rec = Comparison(
                baseline_id=baseline_id,
                candidate_id=candidate_id,
                delta_pass_rate=comparison.get("delta_pass_rate", comparison.get("delta", 0.0)),
                p_value=comparison.get("p_value"),
                regressed_count=b,
                fixed_count=c,
                unchanged_count=comparison.get("unchanged_count", 0),
                still_failing_count=comparison.get("still_failing_count", 0),
                verdict=verdict,
                report_md=report_md,
            )
            session.add(rec)

    # If promoted and auto_promote is enabled, candidate becomes the new baseline
    if verdict == "PROMOTE" and candidate_id and auto_promote:
        set_current_baseline(candidate_id, notes="Promoted via gate")

    # If blocked, dispatch alerts
    if verdict == "BLOCK":
        send_alert(reason, verdict, candidate_id or cand_model)

    # Log to audit trail
    record_audit_event(
        who="gate_evaluator",
        what=f"gate_evaluated_{verdict.lower()}",
        base_commit=str(baseline_id) if baseline_id else str(base_model),
        candidate_commit=str(candidate_id) if candidate_id else str(cand_model),
        model_id=cand_model or "qwen2.5:3b",
        model_digest=cand_digest,
        p_value=p_val,
        b=b,
        c=c,
        verdict=verdict,
        comment=f"Evaluated gate policy v{policy_version}: {reason}",
        report_path="report.md",
    )

    return verdict, report_md


def resolve_ref_to_artifact(ref, quick=False, workspace_dir=None):
    """
    Resolve ref (artifact ID integer/string, or git commit hash) to an Artifact ID.
    If git commit hash is passed and runs have not been executed, executes tests live.
    """
    if not ref:
        return None

    # Check if ref is an integer artifact id
    ref_str = str(ref).strip()
    if ref_str.isdigit():
        art_id = int(ref_str)
        with get_session() as session:
            art = session.query(Artifact).filter_by(id=art_id).first()
            if art:
                return art.id

    # Treat as Git commit reference
    from git import Repo
    from core.repo import get_workspace_path, init_repo
    from core.versioner import hash_content, build_manifest
    from core.runner import run_test, sync_tests_to_db
    from core.scorer import score_artifact_runs
    from core.models import TestCase, Score

    ws = Path(workspace_dir) if workspace_dir else get_workspace_path()
    repo = init_repo(str(ws))
    try:
        commit = repo.commit(ref_str)
    except Exception as e:
        logger.error(f"Cannot resolve git reference {ref_str}: {e}")
        return None

    commit_sha = commit.hexsha

    # Check if artifact already registered for this commit
    with get_session() as session:
        for a in session.query(Artifact).all():
            m = a.manifest or {}
            params = m.get("params", {})
            matches_commit = (
                m.get("git_commit") == commit_sha
                or m.get("commit") == commit_sha
                or params.get("commit") == commit_sha
                or params.get("git_commit") == commit_sha
                or a.name == f"commit_{commit_sha[:7]}"
            )
            if matches_commit:
                art_id = a.id
                # Check if scores exist
                scores_count = session.query(Score).filter_by(artifact_id=art_id).count()
                if scores_count > 0:
                    return art_id
                else:
                    # Found artifact, but needs runs
                    break
        else:
            art_id = None

    # Extract files at this commit
    file_contents = {}
    for item in commit.tree.traverse():
        if item.type == 'blob' and (item.path.startswith("prompts/") or item.path.startswith("skills/")):
            file_contents[item.path] = item.data_stream.read().decode("utf-8", errors="replace")

    params = {"temperature": 0.7, "git_commit": commit_sha}
    art_hash = hash_content(file_contents, "qwen2.5:3b", params)
    manifest = build_manifest(file_contents, "qwen2.5:3b", params)
    manifest["git_commit"] = commit_sha
    manifest["commit_message"] = commit.message.strip()

    if art_id is None:
        with get_session() as session:
            existing = session.query(Artifact).filter_by(hash=art_hash).first()
            if existing:
                art_id = existing.id
            else:
                art = Artifact(
                    hash=art_hash,
                    type="commit",
                    name=f"commit_{commit_sha[:7]}",
                    path="workspace",
                    manifest=manifest,
                )
                session.add(art)
                session.flush()
                art_id = art.id

    # If scores are missing, run tests live
    with get_session() as session:
        scores_count = session.query(Score).filter_by(artifact_id=art_id).count()

    if scores_count == 0:
        sync_tests_to_db()
        with get_session() as session:
            test_cases = [tc.to_dict() for tc in session.query(TestCase).all()]

        k_val = 3 if quick else 5
        if quick:
            test_cases = test_cases[:20]

        print(f"Running live tests for commit {commit_sha[:7]} (Artifact #{art_id}, {len(test_cases)} tests x {k_val} runs)...")
        for tc in test_cases:
            target = tc.get("target", "")
            prompt_content = None
            for p_path, p_text in file_contents.items():
                if target in p_path:
                    prompt_content = p_text
                    break
            run_test(
                artifact_id=art_id,
                test_case=tc,
                k=k_val,
                model_id="qwen2.5:3b",
                workspace_dir=str(ws),
                prompt_template_override=prompt_content,
            )

        score_artifact_runs(art_id, test_cases)

    return art_id


def run_cross_model_gate(
    base_model="qwen2.5:3b",
    cand_model="llama3.2:3b",
    k=None,
    alpha=None,
    policy_path="policy.yaml",
    report_path="report.md",
    quick=False,
    suite="golden",
):
    import yaml
    from core.comparator import compare_test_results
    from core.scorer import score_trace
    from core.llm import default_client

    policy = load_policy(policy_path)
    alpha_val = alpha if alpha is not None else policy.get("alpha", 0.05)
    k_val = k if k is not None else policy.get("k", 5)
    if quick:
        k_val = min(k_val, 3)

    base_meta = default_client.get_model_metadata(base_model)
    cand_meta = default_client.get_model_metadata(cand_model)
    base_digest = base_meta.get("digest", "unknown")
    cand_digest = cand_meta.get("digest", "unknown")

    base_dir = Path(__file__).resolve().parent.parent
    suite_file = base_dir / "tests_data" / f"{suite}_tests.yaml"
    if not suite_file.exists():
        suite_file = base_dir / "tests_data" / "golden_tests.yaml"

    suite_data = yaml.safe_load(suite_file.read_text(encoding="utf-8"))
    test_cases = suite_data.get("tests", [])

    if quick:
        test_cases = test_cases[:20]

    print(f"Executing Cross-Model Gate: Baseline `{base_model}` vs Candidate `{cand_model}`", flush=True)
    print(f"Suite: {suite_file.name} ({len(test_cases)} tests x {k_val} runs), alpha={alpha_val}", flush=True)

    prompts = {}
    ws_prompts = base_dir / "workspace" / "prompts"
    if ws_prompts.exists():
        for pf in ws_prompts.glob("*.md"):
            prompts[pf.stem] = pf.read_text(encoding="utf-8")

    def run_tests_on_model(model_id, digest):
        runs_map = {}
        for tc in test_cases:
            tid = tc["id"]
            target = tc.get("target", "")
            prompt_tmpl = prompts.get(target, "")
            inp = tc["input"]
            if "{input}" in prompt_tmpl:
                full_prompt = prompt_tmpl.replace("{input}", inp)
            elif prompt_tmpl:
                full_prompt = f"{prompt_tmpl}\n\nInput:\n{inp}\nOutput:"
            else:
                full_prompt = inp

            runs = []
            for r_idx in range(k_val):
                seed = 42 + r_idx * 1000
                resp = default_client.generate(
                    prompt=full_prompt,
                    temperature=0.7,
                    seed=seed,
                    model=model_id,
                )
                trace = {
                    "output": resp.text.strip(),
                    "model": model_id,
                    "model_digest": digest,
                    "test_id": tid,
                    "run_index": r_idx,
                }
                res = score_trace(trace, tc.get("checks", []), client=default_client)
                runs.append(bool(res["passed"]))
            runs_map[tid] = runs
        return runs_map

    print(f"Running baseline model: {base_model}...", flush=True)
    base_runs = run_tests_on_model(base_model, base_digest)

    print(f"Running candidate model: {cand_model}...", flush=True)
    cand_runs = run_tests_on_model(cand_model, cand_digest)

    comp_res = compare_test_results(test_cases, base_runs, cand_runs, k=k_val)
    verdict, report_md = evaluate_gate(
        comp_res,
        alpha=alpha_val,
        policy_version=policy.get("version", "1.0.0"),
        base_model=base_model,
        cand_model=cand_model,
        base_digest=base_digest,
        cand_digest=cand_digest,
        auto_promote=False,
    )

    print(f"Gate Verdict: {verdict}", flush=True)
    if report_path and report_md:
        Path(report_path).write_text(report_md, encoding="utf-8")
        print(f"Report written to {report_path}", flush=True)

    return verdict, report_md, comp_res


def main():
    parser = argparse.ArgumentParser(description="Skill & Prompt Regression Manager Gate CLI")
    parser.add_argument("--base", "--baseline", dest="baseline", type=str, help="Baseline commit hash or artifact ID", required=False)
    parser.add_argument("--cand", "--candidate", dest="candidate", type=str, help="Candidate commit hash or artifact ID", required=False)
    parser.add_argument("--base-model", dest="base_model", type=str, default=None, help="Baseline model ID (e.g. qwen2.5:3b)")
    parser.add_argument("--cand-model", dest="cand_model", type=str, default=None, help="Candidate model ID (e.g. llama3.2:3b)")
    parser.add_argument("-k", type=int, default=None, help="Number of runs per test")
    parser.add_argument("--suite", type=str, default="golden", help="Test suite (golden, analytics, promptpex, gpr)")
    parser.add_argument("--quick", action="store_true", help="Quick mode (k=3, 20 tests)")
    parser.add_argument("--alpha", type=float, default=None, help="Significance threshold (defaults to policy.yaml)")
    parser.add_argument("--policy", type=str, default="policy.yaml", help="Path to policy configuration YAML file")
    parser.add_argument("--report", type=str, default="report.md", help="Path to save markdown report")
    args = parser.parse_args()

    # If cross-model comparison requested
    if args.cand_model:
        base_m = args.base_model or "qwen2.5:3b"
        verdict, report_md, _ = run_cross_model_gate(
            base_model=base_m,
            cand_model=args.cand_model,
            k=args.k,
            alpha=args.alpha,
            policy_path=args.policy,
            report_path=args.report,
            quick=args.quick,
            suite=args.suite,
        )
        sys.exit(1 if verdict == "BLOCK" else 0)

    # Load baseline if not specified
    cand_ref = args.candidate
    base_ref = args.baseline

    if not cand_ref:
        print("Error: candidate commit hash or artifact ID (--cand) is required.")
        sys.exit(1)

    if not base_ref:
        base_art = get_current_baseline()
        base_ref = str(base_art["id"]) if base_art else None

    if not base_ref:
        print("Error: baseline commit hash or artifact ID (--base) is required.")
        sys.exit(1)

    baseline_id = resolve_ref_to_artifact(base_ref, quick=args.quick)
    candidate_id = resolve_ref_to_artifact(cand_ref, quick=args.quick)

    if not baseline_id or not candidate_id:
        print(f"Error: failed to resolve baseline '{base_ref}' or candidate '{cand_ref}'.")
        sys.exit(1)

    with get_session() as session:
        last_comp = session.query(Comparison).filter_by(
            baseline_id=baseline_id,
            candidate_id=candidate_id,
        ).order_by(Comparison.id.desc()).first()

    from core.comparator import compare_test_results
    from core.models import TestCase, Score
    from core.scorer import score_artifact_runs

    with get_session() as session:
        test_cases = [t.to_dict() for t in session.query(TestCase).all()]
        base_scores = session.query(Score).filter_by(artifact_id=baseline_id).all()
        cand_scores = session.query(Score).filter_by(artifact_id=candidate_id).all()

    if not base_scores:
        score_artifact_runs(baseline_id, test_cases)
        with get_session() as session:
            base_scores = session.query(Score).filter_by(artifact_id=baseline_id).all()

    if not cand_scores:
        score_artifact_runs(candidate_id, test_cases)
        with get_session() as session:
            cand_scores = session.query(Score).filter_by(artifact_id=candidate_id).all()

    if not base_scores or not cand_scores:
        print(f"Error: no scores or traces found for baseline {baseline_id} or candidate {candidate_id}.")
        sys.exit(1)

    base_map = {}
    for s in base_scores:
        base_map.setdefault(s.test_id, []).append(bool(s.passed))
    cand_map = {}
    for s in cand_scores:
        cand_map.setdefault(s.test_id, []).append(bool(s.passed))

    policy = load_policy(args.policy)
    alpha_val = args.alpha if args.alpha is not None else policy.get("alpha", 0.05)
    comp_res = compare_test_results(test_cases, base_map, cand_map)
    verdict, report_md = evaluate_gate(
        comp_res,
        alpha=alpha_val,
        candidate_id=candidate_id,
        baseline_id=baseline_id,
        policy_version=policy.get("version", "1.0.0"),
    )

    print(f"Gate Verdict: {verdict}")
    if args.report and report_md:
        Path(args.report).write_text(report_md, encoding="utf-8")
        print(f"Report written to {args.report}")

    sys.exit(1 if verdict == "BLOCK" else 0)


if __name__ == "__main__":
    main()
