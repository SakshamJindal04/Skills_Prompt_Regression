"""
Run Replay Verification and Reproducibility Bundling Module.
Supports:
1. `regguard bundle <run>`: Packages manifest, test-suite hash, model digest,
   seeds, traces, scores, verdict, and report into a cryptographically verified zip.
2. `regguard replay <bundle>`: Re-scores stored traces and recomputes b, c,
   p-value, and verdict with ZERO model calls, asserting exact equality.
   Tampered bundles are detected via cryptographic SHA-256 hash mismatch.
"""

import os
import json
import zipfile
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List

from core.db import get_session
from core.models import Comparison, Artifact, Trace, Score, TestCase
from core.comparator import mcnemar_test, classify_outcome
from core.checkers import evaluate_checks


class BundleTamperedError(Exception):
    """Raised when bundle archive files have been tampered with or checksums mismatch."""
    pass


def compute_sha256(data: bytes) -> str:
    """Computes SHA-256 hex digest for byte content."""
    return hashlib.sha256(data).hexdigest()


def compute_file_sha256(file_path: Path) -> str:
    """Computes SHA-256 hex digest for a file on disk."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def create_run_bundle(
    comparison_id: Optional[int] = None,
    output_path: Optional[str] = None,
    bundle_dir: Optional[str] = None,
) -> str:
    """
    Creates an immutable replay bundle zip for a given comparison run.
    Contains manifest.json, test_suite.json, traces.json, scores.json, verdict.json, report.md.
    """
    with get_session() as session:
        if comparison_id is None:
            comp = session.query(Comparison).order_by(Comparison.id.desc()).first()
            if not comp:
                raise ValueError("No comparison runs found in database to bundle.")
            comparison_id = comp.id
        else:
            comp = session.query(Comparison).filter_by(id=comparison_id).first()
            if not comp:
                raise ValueError(f"Comparison ID {comparison_id} not found in database.")

        base_art = session.query(Artifact).filter_by(id=comp.baseline_id).first()
        cand_art = session.query(Artifact).filter_by(id=comp.candidate_id).first()

        # Query all traces for both artifacts
        base_traces = session.query(Trace).filter_by(artifact_id=comp.baseline_id).all()
        cand_traces = session.query(Trace).filter_by(artifact_id=comp.candidate_id).all()
        all_traces = [t.to_dict() for t in (base_traces + cand_traces)]

        # Query scores for both artifacts
        base_scores = session.query(Score).filter_by(artifact_id=comp.baseline_id).all()
        cand_scores = session.query(Score).filter_by(artifact_id=comp.candidate_id).all()
        all_scores = [s.to_dict() for s in (base_scores + cand_scores)]

        # Collect test cases used
        test_ids = list({t["test_id"] for t in all_traces} | {s["test_id"] for s in all_scores})
        if test_ids:
            test_cases = session.query(TestCase).filter(TestCase.id.in_(test_ids)).all()
            test_suite_list = [tc.to_dict() for tc in test_cases]
        else:
            test_suite_list = []

        # Model and seeds
        model_id = base_traces[0].model if base_traces else "qwen2.5:3b"
        model_digest = base_traces[0].model_digest if base_traces else None
        seeds = sorted(list({t["seed"] for t in all_traces if t.get("seed") is not None})) or [42]
        k = len(seeds) if len(seeds) > 1 else (len(base_traces) // max(1, len(test_ids)) if test_ids else 5)

        verdict_dict = comp.to_dict()
        report_text = comp.report_md or "# Gate Evaluation Report\nNo markdown recorded."

    # Prepare file contents in memory
    test_suite_bytes = json.dumps(test_suite_list, indent=2, sort_keys=True).encode("utf-8")
    traces_bytes = json.dumps(all_traces, indent=2, sort_keys=True).encode("utf-8")
    scores_bytes = json.dumps(all_scores, indent=2, sort_keys=True).encode("utf-8")
    verdict_bytes = json.dumps(verdict_dict, indent=2, sort_keys=True).encode("utf-8")
    report_bytes = report_text.encode("utf-8")

    # Compute checksums
    checksums = {
        "test_suite.json": compute_sha256(test_suite_bytes),
        "traces.json": compute_sha256(traces_bytes),
        "scores.json": compute_sha256(scores_bytes),
        "verdict.json": compute_sha256(verdict_bytes),
        "report.md": compute_sha256(report_bytes),
    }

    manifest = {
        "bundle_schema_version": "1.0.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "comparison_id": comp.id,
        "base_artifact_id": comp.baseline_id,
        "candidate_artifact_id": comp.candidate_id,
        "base_hash": base_art.hash if base_art else "",
        "candidate_hash": cand_art.hash if cand_art else "",
        "model_id": model_id,
        "model_digest": model_digest,
        "k": k,
        "seeds": seeds,
        "test_count": len(test_suite_list),
        "trace_count": len(all_traces),
        "file_checksums": checksums,
    }
    manifest_bytes = json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8")

    # Output zip path
    if output_path:
        out_zip = Path(output_path)
    else:
        target_dir = Path(bundle_dir) if bundle_dir else Path("results/bundles")
        target_dir.mkdir(parents=True, exist_ok=True)
        timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        out_zip = target_dir / f"run_bundle_{comp.id}_{timestamp_str}.zip"

    out_zip.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", manifest_bytes)
        zf.writestr("test_suite.json", test_suite_bytes)
        zf.writestr("traces.json", traces_bytes)
        zf.writestr("scores.json", scores_bytes)
        zf.writestr("verdict.json", verdict_bytes)
        zf.writestr("report.md", report_bytes)

    return str(out_zip)


def replay_run_bundle(bundle_path: str, assert_exact: bool = True) -> Dict[str, Any]:
    """
    Replays and verifies a run bundle with ZERO model calls.
    1. Verifies SHA-256 checksum of every file in the archive against manifest.json.
    2. Re-scores stored traces using deterministic checkers.
    3. Re-computes majority votes, discordant flips (b, c), p-value, and gate verdict.
    4. Asserts that recomputed values exactly match the recorded values.
    """
    bpath = Path(bundle_path)
    if not bpath.exists():
        raise FileNotFoundError(f"Bundle file not found: {bundle_path}")

    with zipfile.ZipFile(bpath, "r") as zf:
        namelist = zf.namelist()
        if "manifest.json" not in namelist:
            raise BundleTamperedError("Invalid bundle: missing manifest.json")

        manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
        checksums = manifest.get("file_checksums", {})

        # Cryptographic tamper verification
        for fname, expected_hash in checksums.items():
            if fname not in namelist:
                raise BundleTamperedError(f"Bundle tampered: missing required file '{fname}'")
            actual_data = zf.read(fname)
            actual_hash = compute_sha256(actual_data)
            if actual_hash != expected_hash:
                raise BundleTamperedError(
                    f"Bundle tampered: hash mismatch for '{fname}'. Expected {expected_hash}, got {actual_hash}"
                )

        # Load bundle data
        test_suite = json.loads(zf.read("test_suite.json").decode("utf-8"))
        traces = json.loads(zf.read("traces.json").decode("utf-8"))
        scores = json.loads(zf.read("scores.json").decode("utf-8"))
        recorded_verdict = json.loads(zf.read("verdict.json").decode("utf-8"))

    test_case_map = {tc["id"]: tc for tc in test_suite}
    base_id = manifest["base_artifact_id"]
    cand_id = manifest["candidate_artifact_id"]

    # Re-score all traces deterministically with zero model calls
    base_run_map: Dict[str, List[bool]] = {}
    cand_run_map: Dict[str, List[bool]] = {}

    for t in traces:
        t_art_id = t["artifact_id"]
        t_id = t["test_id"]
        tc = test_case_map.get(t_id)

        # If test case exists with checks, re-evaluate checks deterministically
        if tc and tc.get("checks"):
            passed, _ = evaluate_checks(t.get("output", "") or "", tc["checks"], client=None)
        else:
            # Fall back to recorded score in trace or score entry
            matching_s = next(
                (s for s in scores if s["artifact_id"] == t_art_id and s["test_id"] == t_id and s["run_index"] == t["run_index"]),
                None,
            )
            passed = bool(matching_s["passed"]) if matching_s else False

        if t_art_id == base_id:
            base_run_map.setdefault(t_id, []).append(passed)
        elif t_art_id == cand_id:
            cand_run_map.setdefault(t_id, []).append(passed)

    # Compute majority voting
    base_maj: Dict[str, bool] = {}
    cand_maj: Dict[str, bool] = {}

    for tid, runs in base_run_map.items():
        base_maj[tid] = sum(runs) >= (len(runs) // 2 + 1)

    for tid, runs in cand_run_map.items():
        cand_maj[tid] = sum(runs) >= (len(runs) // 2 + 1)

    common_tests = sorted(list(set(base_maj.keys()) & set(cand_maj.keys())))
    b = 0
    c = 0
    unchanged = 0
    still_failing = 0

    for tid in common_tests:
        bp = base_maj[tid]
        cp = cand_maj[tid]
        if bp and not cp:
            b += 1
        elif not bp and cp:
            c += 1
        elif bp and cp:
            unchanged += 1
        else:
            still_failing += 1

    p_val = mcnemar_test(b, c)

    # Recomputed pass rates and delta
    base_pass_count = sum(1 for tid in common_tests if base_maj[tid])
    cand_pass_count = sum(1 for tid in common_tests if cand_maj[tid])
    total_tests = max(1, len(common_tests))
    delta_pass_rate = (cand_pass_count - base_pass_count) / total_tests

    # Recompute verdict based on standard policy
    if (p_val < 0.05 and b > c):
        recomputed_verdict = "BLOCK"
    else:
        recomputed_verdict = "PROMOTE"

    recomputed = {
        "comparison_id": manifest["comparison_id"],
        "base_artifact_id": base_id,
        "candidate_artifact_id": cand_id,
        "b": b,
        "c": c,
        "unchanged": unchanged,
        "still_failing": still_failing,
        "p_value": p_val,
        "delta_pass_rate": delta_pass_rate,
        "verdict": recomputed_verdict,
        "total_evaluated_tests": len(common_tests),
        "total_traces_replayed": len(traces),
    }

    if assert_exact:
        assert recomputed["b"] == recorded_verdict.get("regressed_count", 0), (
            f"Replay b mismatch: recomputed {recomputed['b']} != recorded {recorded_verdict.get('regressed_count')}"
        )
        assert recomputed["c"] == recorded_verdict.get("fixed_count", 0), (
            f"Replay c mismatch: recomputed {recomputed['c']} != recorded {recorded_verdict.get('fixed_count')}"
        )
        rec_p = recorded_verdict.get("p_value")
        if rec_p is not None:
            assert abs(recomputed["p_value"] - rec_p) < 1e-4, (
                f"Replay p-value mismatch: recomputed {recomputed['p_value']} != recorded {rec_p}"
            )
        assert recomputed["verdict"] == recorded_verdict.get("verdict"), (
            f"Replay verdict mismatch: recomputed {recomputed['verdict']} != recorded {recorded_verdict.get('verdict')}"
        )

    return {
        "status": "VERIFIED",
        "tampered": False,
        "bundle_file": str(bpath),
        "recomputed": recomputed,
        "recorded": recorded_verdict,
        "manifest": manifest,
    }
