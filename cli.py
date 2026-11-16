import sys
import argparse
from pathlib import Path


def run_lab_cli(args):
    from core.lab import run_lab_pipeline, export_lab_markdown, export_lab_csv

    prompt_path = Path(args.prompt)
    if not prompt_path.exists():
        print(f"Error: Prompt file not found: {args.prompt}")
        sys.exit(1)

    prompt_text = prompt_path.read_text(encoding="utf-8")
    prompt2_text = None
    if args.prompt2:
        p2_path = Path(args.prompt2)
        if p2_path.exists():
            prompt2_text = p2_path.read_text(encoding="utf-8")

    models = [m.strip() for m in args.models.split(",") if m.strip()] if args.models else ["qwen2.5:3b"]

    print(f"Running Panel Lab pipeline on {args.prompt} (models: {models}, k: {args.k}, tests: {args.tests})...")
    res = run_lab_pipeline(
        prompt_text=prompt_text,
        prompt_v2_text=prompt2_text,
        models=models,
        k=args.k,
        max_tests=args.tests,
    )

    out_md = Path(args.report) if args.report else Path("results/panel_lab_report.md")
    export_lab_markdown(res, output_path=str(out_md))
    out_csv = Path("results/panel_lab_traces.csv")
    export_lab_csv(res, output_path=str(out_csv))

    print("\n--- PANEL LAB RESULTS ---")
    print(f"Pass Rate: {res['overall_pass_rate']:.2%}")
    print(f"Latency: p50={res['latency_p50_ms']}ms, p95={res['latency_p95_ms']}ms")
    print(f"Wall Clock: {res['wall_clock_s']}s")
    print(f"Report written to: {out_md}")
    print(f"Traces written to: {out_csv}")

    if res.get("v2_comparison"):
        v2 = res["v2_comparison"]
        print(f"V2 Gate Verdict: {v2.get('verdict')} (p={v2.get('p_value'):.4f}, b={v2.get('b')}, c={v2.get('c')})")

    sys.exit(0)


def run_skill_lint_cli(args):
    from core.lint import lint_skill
    from core.skills import SkillRegistry

    reg = SkillRegistry()
    existing_skills = [s.metadata for s in reg.list_skills()]
    target_path = Path(args.path) if args.path else Path("workspace/skills")

    has_errors = False
    checked = 0

    if target_path.is_file():
        files = [target_path]
    elif target_path.is_dir():
        files = list(target_path.rglob("SKILL.md"))
    else:
        print(f"Path not found: {target_path}")
        sys.exit(1)

    print(f"Linting {len(files)} skill(s)...")
    for f in sorted(files):
        checked += 1
        res = lint_skill(str(f), existing_skills=existing_skills)
        name = res.get("metadata", {}).get("name", f.parent.name)
        if res["valid"]:
            status = "PASS" if not res["warnings"] else "WARN"
            print(f"[{status}] {name} ({f.relative_to(Path.cwd()) if f.is_relative_to(Path.cwd()) else f})")
            for w in res["warnings"]:
                print(f"  - WARNING: {w}")
        else:
            has_errors = True
            print(f"[FAIL] {name} ({f.relative_to(Path.cwd()) if f.is_relative_to(Path.cwd()) else f})")
            for err in res["errors"]:
                print(f"  - ERROR: {err}")
            for w in res["warnings"]:
                print(f"  - WARNING: {w}")

    print(f"\nSkill Lint completed: {checked} skills checked. Status: {'FAILED' if has_errors else 'PASSED'}")
    sys.exit(1 if has_errors else 0)


def run_drift_cli(args):
    from core.drift import check_model_drift

    model = args.model or "qwen2.5:3b"
    print(f"Checking model drift for '{model}'...")
    res = check_model_drift(model_tag=model, suite=args.suite, k=args.k)

    print(f"Current Digest: {res.get('current_digest')}")
    print(f"Baseline Digest: {res.get('baseline_digest')}")
    print(f"Drift Detected: {res.get('drift_detected')}")
    print(f"Status Message: {res.get('message')}")
    if res.get("report_path"):
        print(f"Drift Report: {res.get('report_path')}")

    sys.exit(1 if res.get("drift_detected") and "BLOCK" in res.get("report_md", "") else 0)


def run_audit_verify_cli(args):
    from core.audit import verify_audit_hash_chain

    print("Verifying append-only cryptographic audit hash chain...")
    status = verify_audit_hash_chain()
    print(f"Records Checked: {status['checked_count']}")
    print(f"Chain Integrity: {'VALID' if status['valid'] else 'COMPROMISED'}")
    print(f"Head Hash: {status.get('head_hash') or 'N/A'}")

    if not status["valid"]:
        print("\nERRORS DETECTED:")
        for err in status["errors"]:
            print(f"  - {err}")
        sys.exit(1)
    else:
        print("All audit log rows are cryptographically intact and unbroken.")
        sys.exit(0)


def main():
    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()
        if cmd == "lab":
            parser = argparse.ArgumentParser(description="Panel Lab CLI")
            parser.add_argument("cmd", help="Subcommand (lab)")
            parser.add_argument("--prompt", required=True, help="Path to base prompt file")
            parser.add_argument("--prompt2", default=None, help="Path to candidate prompt v2 file")
            parser.add_argument("--models", default="qwen2.5:3b", help="Comma-separated model names")
            parser.add_argument("--k", type=int, default=3, help="Repetitions per test")
            parser.add_argument("--tests", type=int, default=20, help="Test budget")
            parser.add_argument("--report", default="results/panel_lab_report.md", help="Output report path")
            args = parser.parse_args()
            run_lab_cli(args)
            return

        elif cmd in ("skill-lint", "skill_lint"):
            parser = argparse.ArgumentParser(description="Skill Linter CLI")
            parser.add_argument("cmd", help="Subcommand (skill-lint)")
            parser.add_argument("path", nargs="?", default="workspace/skills", help="Path to SKILL.md or folder")
            args = parser.parse_args()
            run_skill_lint_cli(args)
            return

        elif cmd == "drift":
            parser = argparse.ArgumentParser(description="Model Drift Detector CLI")
            parser.add_argument("cmd", help="Subcommand (drift)")
            parser.add_argument("--model", default="qwen2.5:3b", help="Model tag to inspect")
            parser.add_argument("--suite", default="golden", help="Test suite to run if drift detected")
            parser.add_argument("-k", type=int, default=5, help="Repetitions per test")
            args = parser.parse_args()
            run_drift_cli(args)
            return

        elif cmd in ("audit-verify", "audit_verify"):
            parser = argparse.ArgumentParser(description="Audit Trail Hash-Chain Verifier CLI")
            parser.add_argument("cmd", help="Subcommand (audit-verify)")
            args = parser.parse_args()
            run_audit_verify_cli(args)
            return

    # Fall back to regression gate CLI
    from core.gate import main as gate_main
    gate_main()


if __name__ == "__main__":
    main()
