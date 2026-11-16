"""
Comprehensive Tier 1 Test Suite: Decision Quality, Reproducibility & Governance.

Covers:
1. Replay Verification & Tamper Detection (core.bundle)
2. Four Frozen Decision Rules (core.decision_rules)
3. Statistical Power & Sample Size Advisory (core.power)
4. Beyond Pass/Fail Quality & Drift Metrics (core.drift_analysis)
5. Agent Trajectory Tools & Invariant Checkers (core.agent, core.checkers)
6. Human Review Queue & Cohen's Kappa (core.review_queue)
7. Environments, Stage Gates & SemVer Engine (core.environments)
8. Release Report HTML/PDF & Anti-Hallucination Number Verification (core.release_report)
"""

import json
import pytest
from pathlib import Path

from core.bundle import (
    create_run_bundle,
    replay_run_bundle,
    BundleTamperedError,
    compute_sha256,
)
from core.decision_rules import (
    evaluate_mcnemar_rule,
    evaluate_non_inferiority_rule,
    evaluate_holm_bonferroni_rule,
    evaluate_odds_ratio_rule,
    evaluate_all_decision_rules,
)
from core.power import compute_mcnemar_power, format_power_report
from core.drift_analysis import (
    compute_percentiles,
    bootstrap_diff_ci,
    analyze_beyond_pass_fail,
)
from core.agent import (
    tool_calculator,
    tool_doc_lookup,
    tool_db_query,
    parse_action_json,
    run_agent_trajectory,
)
from core.checkers import Checker
from core.review_queue import (
    enqueue_review_item,
    list_review_items,
    submit_human_review,
    compute_cohens_kappa,
)
from core.environments import (
    get_environment_baselines,
    suggest_semver,
    promote_baseline,
    compute_skill_model_compatibility,
    generate_release_notes,
)
from core.release_report import (
    generate_release_report_html,
    verify_report_numbers,
    render_report_pdf,
)


# --- 1. Replay Verification Tests ---
def test_bundle_creation_and_verified_replay(tmp_path):
    # Test bundle creation on comparison #100
    bundle_zip = create_run_bundle(comparison_id=100, output_path=str(tmp_path / "test_bundle.zip"))
    assert Path(bundle_zip).exists()

    # Replay without model calls
    res = replay_run_bundle(bundle_zip, assert_exact=True)
    assert res["status"] == "VERIFIED"
    assert res["tampered"] is False
    assert res["recomputed"]["verdict"] == res["recorded"]["verdict"]


def test_bundle_tamper_detection(tmp_path):
    import zipfile
    bundle_zip = Path(create_run_bundle(comparison_id=100, output_path=str(tmp_path / "tamper_test.zip")))
    
    # Extract, tamper with verdict.json, and re-zip
    extract_dir = tmp_path / "extracted"
    with zipfile.ZipFile(bundle_zip, "r") as zf:
        zf.extractall(extract_dir)

    v_file = extract_dir / "verdict.json"
    data = json.loads(v_file.read_text(encoding="utf-8"))
    data["verdict"] = "TAMPERED_VERDICT"
    v_file.write_text(json.dumps(data), encoding="utf-8")

    tampered_zip = tmp_path / "tampered_bundle.zip"
    with zipfile.ZipFile(tampered_zip, "w") as zf:
        for f in extract_dir.rglob("*"):
            if f.is_file():
                zf.write(f, arcname=f.relative_to(extract_dir))

    with pytest.raises(BundleTamperedError):
        replay_run_bundle(str(tampered_zip))


# --- 2. Frozen Decision Rules Tests ---
def test_decision_rules_clean_candidate():
    comp = {
        "regressed_count": 0,
        "fixed_count": 3,
        "p_value": 0.2500,
        "ci_delta": (0.01, 0.08),
        "flips": [{"test_id": "t1", "outcome": "fixed", "critical": False}],
        "slices": [{"slice": "general", "b": 0, "c": 3, "p_value": 0.2500}],
    }
    all_rules = evaluate_all_decision_rules(comp)
    assert all_rules["mcnemar_exact"]["verdict"] == "PROMOTE"
    assert all_rules["non_inferiority"]["verdict"] == "PROMOTE"
    assert all_rules["holm_bonferroni"]["verdict"] == "PROMOTE"
    assert all_rules["odds_ratio"]["verdict"] == "PROMOTE"


def test_decision_rules_regressed_candidate():
    comp = {
        "regressed_count": 8,
        "fixed_count": 0,
        "p_value": 0.0078,
        "ci_delta": (-0.12, -0.04),
        "flips": [
            {"test_id": "t1", "outcome": "regressed", "critical": True},
            {"test_id": "t2", "outcome": "regressed", "critical": False},
        ],
        "slices": [{"slice": "general", "b": 8, "c": 0, "p_value": 0.0078}],
    }
    all_rules = evaluate_all_decision_rules(comp)
    assert all_rules["mcnemar_exact"]["verdict"] == "BLOCK"
    assert all_rules["non_inferiority"]["verdict"] == "BLOCK"
    assert all_rules["holm_bonferroni"]["verdict"] == "BLOCK"
    assert all_rules["odds_ratio"]["verdict"] == "BLOCK"


def test_odds_ratio_haldane_anscombe_continuity_correction():
    # When c = 0, Haldane-Anscombe adds 0.5 to prevent division by zero
    res = evaluate_odds_ratio_rule(b=6, c=0, critical_regressed=False, threshold=1.5)
    assert res["verdict"] == "BLOCK"
    assert res["odds_ratio"] == pytest.approx((6 + 0.5) / 0.5, rel=1e-2)
    assert res["ci_lower"] > 0.5
    assert res["ci_upper"] > 10.0


# --- 3. Power Analysis Tests ---
def test_power_analysis_minimum_detectable():
    res = compute_mcnemar_power(n=100, k=5, alpha=0.05)
    assert res["n"] == 100
    assert res["min_detectable_b"] == 6  # 0.5^5 = 0.03125 <= 0.05
    assert res["min_detectable_rate"] == 0.06
    assert "HIGH POWER" in res["recommendation"]

    report_text = format_power_report(n=100, k=5)
    assert "REGGUARD STATISTICAL POWER" in report_text
    assert "Minimum Discordant (b)  : 6" in report_text


# --- 4. Beyond Pass/Fail Quality & Drift Tests ---
def test_percentiles_and_bootstrap_diff():
    base_lats = [100.0, 105.0, 110.0, 95.0, 102.0]
    cand_lats = [200.0, 210.0, 195.0, 205.0, 215.0]
    p50, p95 = compute_percentiles(cand_lats)
    assert p50 > 190.0
    diff_pt, ci_low, ci_high = bootstrap_diff_ci(base_lats, cand_lats, n_resamples=500)
    assert diff_pt > 80.0
    assert ci_low > 70.0


def test_analyze_beyond_pass_fail_summary():
    base_traces = [
        {"test_id": "t1", "output": "Select * from customers", "latency_ms": 150.0},
        {"test_id": "t2", "output": "Order summary report", "latency_ms": 200.0},
    ]
    cand_traces = [
        {"test_id": "t1", "output": "Select * from customers", "latency_ms": 160.0},
        {"test_id": "t2", "output": "Order summary report with additional details", "latency_ms": 210.0},
    ]
    analysis = analyze_beyond_pass_fail(base_traces, cand_traces)
    assert "latency" in analysis
    assert "output_length" in analysis
    assert "cost" in analysis
    assert analysis["cost"]["base_calls"] == 2


# --- 5. Deterministic Agent Tools & Trajectory Tests ---
def test_agent_tools_execution():
    # Calculator: safe math
    assert tool_calculator("2 * (15 + 35)") == "100"
    assert "ERROR" in tool_calculator("__import__('os').system('ls')")

    # Document Lookup: enterprise docs
    res_doc = tool_doc_lookup("Enterprise Tier", doc_name="sla_policy.txt")
    assert "99.99%" in res_doc

    # SQLite Query: read-only SELECT
    res_db = tool_db_query("SELECT stock_quantity FROM inventory WHERE item_id = 1")
    assert "15" in res_db

    # SQLite Query: write operations blocked
    assert "prohibited" in tool_db_query("DROP TABLE inventory")
    assert "prohibited" in tool_db_query("DELETE FROM orders")


def test_trajectory_checkers():
    traj_data = {
        "step_count": 2,
        "tools_used": ["calculator"],
        "loop_detected": False,
        "trajectory": [
            {"step": 1, "action": "calculator", "args": {"expression": "10 * 10"}},
            {"step": 2, "action": "final_answer", "args": {"answer": "100"}},
        ],
    }
    # Check tool called
    p1, d1 = Checker.check_tool_called(traj_data, {"tool": "calculator"})
    assert p1 is True

    # Check no loops
    p2, d2 = Checker.check_no_loops(traj_data, {})
    assert p2 is True

    # Check step count
    p3, d3 = Checker.check_step_count(traj_data, {"limit": 3})
    assert p3 is True
    p3_fail, _ = Checker.check_step_count(traj_data, {"limit": 1})
    assert p3_fail is False

    # Check valid arguments
    p4, d4 = Checker.check_valid_arguments(
        traj_data, {"tool": "calculator", "required_keys": ["expression"]}
    )
    assert p4 is True


# --- 6. Human Review Queue & Cohen's Kappa Tests ---
def test_human_review_queue_and_kappa():
    # Enqueue review item
    item_id = enqueue_review_item(
        trace_id=1,
        test_id="test_qa_01",
        artifact_id=3,
        flag_reason="borderline_sentiment",
        judge_score=0.5,
        judge_passed=False,
        model_output="neutral tone with positive nuance",
    )
    assert item_id > 0

    # Submit review
    rev = submit_human_review(
        review_id=item_id,
        human_passed=True,
        reviewer_id="lead_reviewer",
        comment="Human expert verified this response complies with policy.",
        override_score=False,
    )
    assert rev["status"] == "reviewed"
    assert rev["human_passed"] is True

    # Compute Kappa
    kappa_res = compute_cohens_kappa()
    assert kappa_res["n"] >= 1
    assert "kappa" in kappa_res
    assert "contingency_table" in kappa_res


# --- 7. Environments, Releases & SemVer Tests ---
def test_semver_suggester():
    # Patch bump on clean refinement
    s1 = suggest_semver(current_version="1.0.0", change_type="patch", regressed_flips=0)
    assert s1["suggested_version"] == "1.0.1"

    # Minor bump on new feature
    s2 = suggest_semver(current_version="1.0.0", change_type="feature")
    assert s2["suggested_version"] == "1.1.0"

    # Major bump on critical regression
    s3 = suggest_semver(current_version="1.0.0", critical_regressions=1)
    assert s3["suggested_version"] == "2.0.0"


def test_environments_promotion_and_notes():
    # Dev promotion
    promo = promote_baseline(
        to_env="dev",
        artifact_id=3,
        approver="test_engineer",
        comment="Initial dev baseline certification",
        semver="1.0.1",
    )
    assert promo["environment"] == "dev"
    assert promo["semver"] == "1.0.1"

    # Check release notes generation
    notes = generate_release_notes(artifact_id=3, version_tag="1.0.1", target_env="dev")
    assert "# Release Notes" in notes
    assert "Artifact Hash" in notes


def test_skill_by_model_compatibility_matrix():
    mat = compute_skill_model_compatibility()
    assert len(mat) > 0
    skills = {row["skill"] for row in mat}
    models = {row["model"] for row in mat}
    assert "sql_authoring" in skills
    assert "qwen2.5:3b" in models


# --- 8. Release Report HTML, Anti-Hallucination & PDF Tests ---
def test_release_report_anti_hallucination_and_pdf(tmp_path):
    comp_data = {
        "comparison_id": 888,
        "verdict": "PROMOTE",
        "baseline_id": 3,
        "candidate_id": 4,
        "model_id": "qwen2.5:3b",
        "base_pass_rate": 0.85,
        "cand_pass_rate": 0.90,
        "delta_pass_rate": 0.05,
        "b": 0,
        "c": 4,
        "p_value": 0.1250,
        "ci_delta": (0.01, 0.09),
        "odds_ratio": 0.11,
        "ci_odds": (0.01, 0.98),
        "non_inferior": True,
        "margin": 0.05,
        "flips": [],
    }
    # HTML generation
    html_f = tmp_path / "report_888.html"
    html_content, _ = generate_release_report_html(comp_data, output_path=html_f)
    assert html_f.exists()

    # Verify anti-hallucination mathematical assertion
    valid, errors = verify_report_numbers(html_content, comp_data)
    assert valid is True, f"Number verification failed with errors: {errors}"

    # Render PDF
    pdf_f = tmp_path / "report_888.pdf"
    render_report_pdf(html_f, pdf_path=pdf_f)
    assert pdf_f.exists()
    assert pdf_f.stat().st_size > 5000
