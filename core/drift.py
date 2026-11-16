import os
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any

from core.llm import OllamaClient, default_client
from core.versioner import get_current_baseline
from core.db import get_session
from core.models import Artifact, Score, Comparison
from core.comparator import compare_test_results
from core.audit import record_audit_event
from core.reporter import generate_markdown_report

logger = logging.getLogger("drift")
BASE_DIR = Path(__file__).resolve().parent.parent


def check_model_drift(
    model_tag: str = "qwen2.5:3b",
    suite: str = "golden",
    k: int = 5,
    client: Optional[OllamaClient] = None,
    report_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Checks if local model digest has silently drifted from baseline manifest digest.
    If drifted, runs test suite against the new digest and computes McNemar statistical comparison.
    """
    c = client or default_client
    current_show = c.show(model_tag)
    current_digest = current_show.get("digest")

    baseline_art = get_current_baseline()
    baseline_digest = None
    baseline_art_id = None

    if baseline_art:
        baseline_art_id = baseline_art.get("id")
        manifest = baseline_art.get("manifest", {})
        baseline_digest = manifest.get("model_digest")

    if not baseline_digest:
        # Fallback to last recorded score or trace digest
        with get_session() as session:
            last_score = session.query(Score).filter(Score.model_id == model_tag, Score.model_digest.isnot(None)).order_by(Score.id.desc()).first()
            if last_score:
                baseline_digest = last_score.model_digest

    if not baseline_digest:
        baseline_digest = current_digest

    digest_match = (current_digest == baseline_digest)

    result = {
        "model": model_tag,
        "current_digest": current_digest,
        "baseline_digest": baseline_digest,
        "digest_match": digest_match,
        "drift_detected": not digest_match,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "details": current_show.get("details", {}),
        "report_md": ""
    }

    if digest_match:
        result["message"] = f"Model '{model_tag}' digest matches baseline ({current_digest[:12]}...). No drift detected."
        return result

    # Drift detected: model weights or quantization have changed
    warning_msg = (
        f"CRITICAL WARNING: Silent model update detected for '{model_tag}'. "
        f"Baseline digest: {baseline_digest[:12]}... -> Current digest: {current_digest[:12]}..."
    )
    logger.warning(warning_msg)
    result["message"] = warning_msg

    # Run golden evaluation against new digest to quantify behavioral drift
    from core.runner import run_test_suite_live
    from core.scorer import score_artifact_runs
    import yaml

    suite_file = "tests_data/golden_tests.yaml" if suite == "golden" else "tests_data/analytics_tests.yaml"
    with open(BASE_DIR / suite_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
        tests = data.get("test_cases", data.get("tests", []))[:20]

    # Create synthetic candidate artifact for new model digest
    with get_session() as session:
        cand_art = Artifact(
            hash=baseline_art.get("short_hash", "HEAD") if baseline_art else "HEAD",
            name=f"drift_eval_{model_tag}",
            type="prompt",
            path="prompts",
            manifest={
                "model": model_tag,
                "model_digest": current_digest,
                "drift_check": True
            }
        )
        session.add(cand_art)
        session.flush()
        cand_art_id = cand_art.id

    # Run tests and score
    run_test_suite_live(cand_art_id, tests, k=k, model=model_tag, client=c)
    score_artifact_runs(cand_art_id, tests)

    # Compare against baseline scores
    with get_session() as session:
        cand_scores = session.query(Score).filter_by(artifact_id=cand_art_id).all()
        base_scores = session.query(Score).filter_by(artifact_id=baseline_art_id).all() if baseline_art_id else []

    base_map = {}
    for s in base_scores:
        base_map.setdefault(s.test_id, []).append(bool(s.passed))
    cand_map = {}
    for s in cand_scores:
        cand_map.setdefault(s.test_id, []).append(bool(s.passed))

    comp_res = compare_test_results(tests, base_map, cand_map, k=k)
    b_val = comp_res.get("regressed_count", 0)
    c_val = comp_res.get("fixed_count", 0)
    p_val = comp_res.get("p_value", 1.0)
    verdict = "BLOCK" if (p_val < 0.05 and b_val > c_val) else "PROMOTE"

    rep_path = report_path or str(BASE_DIR / "results" / f"drift_report_{model_tag.replace(':', '_')}.md")
    report_md = f"""# Model Drift Diagnostic Report: `{model_tag}`

- **Check Timestamp**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}
- **Baseline Digest**: `{baseline_digest}`
- **Current Digest**: `{current_digest}`
- **Digest Status**: **DRIFT DETECTED** (Silent re-pull or weight change)
- **Gate Verdict**: **{verdict}**
- **McNemar p-value**: {p_val:.4f}
- **Regressed Tests (b)**: {b_val}
- **Fixed Tests (c)**: {c_val}
- **Delta Pass Rate**: {comp_res.get('delta_pass_rate', 0.0):+.2%}

### Action Required
The weights or quant of model `{model_tag}` changed without an artifact version update.
Review regressed test cases and promote only after team approval.
"""
    Path(rep_path).parent.mkdir(parents=True, exist_ok=True)
    Path(rep_path).write_text(report_md, encoding="utf-8")
    result["report_md"] = report_md
    result["report_path"] = rep_path

    record_audit_event(
        who="drift_monitor",
        what="model_drift_detected",
        model_id=model_tag,
        model_digest=current_digest,
        verdict=verdict,
        b=b_val,
        c=c_val,
        p_value=p_val,
        comment=f"Silent drift detected on {model_tag}: {baseline_digest[:8]} -> {current_digest[:8]}"
    )

    return result
