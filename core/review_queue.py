"""
Human Review Queue & Inter-Rater Agreement (Cohen's Kappa).

Provides:
1. Enqueueing undecidable or flagged LLM-judge results.
2. Reviewer interface: label pass/fail with mandatory reviewer ID and rationale.
3. Score override with cryptographic audit logging.
4. Calculation of Cohen's kappa (κ) between LLM Judge and Human Reviewers.
"""

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

from core.db import get_session
from core.models import ReviewItem, Score, Trace
from core.audit import record_audit_event


def enqueue_review_item(
    trace_id: int,
    test_id: str,
    artifact_id: int,
    flag_reason: str,
    score_id: Optional[int] = None,
    judge_score: Optional[float] = None,
    judge_passed: Optional[bool] = None,
    model_output: Optional[str] = None,
) -> int:
    """Enqueues an item needing human review."""
    with get_session() as session:
        # Check if already enqueued
        existing = session.query(ReviewItem).filter_by(
            trace_id=trace_id, test_id=test_id, artifact_id=artifact_id
        ).first()
        if existing:
            return existing.id

        if not model_output:
            trace = session.query(Trace).filter_by(id=trace_id).first()
            if trace:
                model_output = trace.output

        item = ReviewItem(
            score_id=score_id,
            trace_id=trace_id,
            test_id=test_id,
            artifact_id=artifact_id,
            flag_reason=flag_reason,
            model_output=model_output,
            judge_score=judge_score,
            judge_passed=judge_passed,
            status="pending",
        )
        session.add(item)
        session.flush()
        return item.id


def list_review_items(status: Optional[str] = None, artifact_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """Lists review items with optional status and artifact filtering."""
    with get_session() as session:
        query = session.query(ReviewItem)
        if status:
            query = query.filter_by(status=status)
        if artifact_id:
            query = query.filter_by(artifact_id=artifact_id)
        items = query.order_by(ReviewItem.created_at.desc()).all()
        return [item.to_dict() for item in items]


def submit_human_review(
    review_id: int,
    human_passed: bool,
    reviewer_id: str,
    comment: str,
    override_score: bool = True,
) -> Dict[str, Any]:
    """
    Records a human review decision, optionally overrides score, and writes to audit log.
    """
    clean_reviewer = str(reviewer_id or "").strip()
    if not clean_reviewer:
        raise ValueError("Reviewer ID is required.")

    clean_comment = str(comment or "").strip()
    if not clean_comment:
        raise ValueError("Review comment/rationale is required.")

    with get_session() as session:
        item = session.query(ReviewItem).filter_by(id=review_id).first()
        if not item:
            raise ValueError(f"Review item #{review_id} not found.")

        item.human_passed = human_passed
        item.reviewer_id = clean_reviewer
        item.comment = clean_comment
        item.status = "reviewed"
        item.reviewed_at = datetime.now(timezone.utc)

        original_passed = item.judge_passed
        score_overridden = False

        if override_score and item.score_id:
            score = session.query(Score).filter_by(id=item.score_id).first()
            if score:
                score.passed = human_passed
                score.score = 1.0 if human_passed else 0.0
                score_overridden = True

        session.flush()

        # Write audit log entry
        record_audit_event(
            who=clean_reviewer,
            what="human_review_label",
            comment=f"Human review #{review_id} for test '{item.test_id}': {'PASS' if human_passed else 'FAIL'}. Comment: {clean_comment}",
            metadata_json={
                "review_id": review_id,
                "test_id": item.test_id,
                "artifact_id": item.artifact_id,
                "score_id": item.score_id,
                "original_passed": original_passed,
                "human_passed": human_passed,
                "score_overridden": score_overridden,
            },
        )

        return item.to_dict()


def compute_cohens_kappa(items: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """
    Computes Cohen's kappa (κ) between LLM Judge and Human Reviewer.
    Requires pairs where both judge_passed and human_passed are non-null.
    """
    if items is None:
        items = list_review_items(status="reviewed")

    # Filter to pairs where both ratings exist
    valid_pairs: List[Tuple[bool, bool]] = []
    for it in items:
        j_pass = it.get("judge_passed")
        h_pass = it.get("human_passed")
        if j_pass is not None and h_pass is not None:
            valid_pairs.append((bool(j_pass), bool(h_pass)))

    n = len(valid_pairs)
    if n == 0:
        return {
            "n": 0,
            "kappa": 0.0,
            "interpretation": "No reviewed items with judge comparisons.",
            "contingency_table": {"both_pass": 0, "both_fail": 0, "judge_only": 0, "human_only": 0},
            "observed_agreement": 0.0,
            "expected_agreement": 0.0,
        }

    # Contingency Table:
    #                 Human Pass    Human Fail
    # Judge Pass          a             b
    # Judge Fail          c             d
    a = sum(1 for j, h in valid_pairs if j and h)
    b = sum(1 for j, h in valid_pairs if j and not h)
    c = sum(1 for j, h in valid_pairs if not j and h)
    d = sum(1 for j, h in valid_pairs if not j and not h)

    p_observed = (a + d) / n

    p_judge_pos = (a + b) / n
    p_judge_neg = (c + d) / n
    p_human_pos = (a + c) / n
    p_human_neg = (b + d) / n

    p_expected = (p_judge_pos * p_human_pos) + (p_judge_neg * p_human_neg)

    denom = 1.0 - p_expected
    if abs(denom) < 1e-9:
        kappa = 1.0 if p_observed == 1.0 else 0.0
    else:
        kappa = (p_observed - p_expected) / denom

    # Standard Landis & Koch (1977) interpretation
    if kappa < 0:
        interp = "Poor (less than chance agreement)"
    elif kappa <= 0.20:
        interp = "Slight agreement"
    elif kappa <= 0.40:
        interp = "Fair agreement"
    elif kappa <= 0.60:
        interp = "Moderate agreement"
    elif kappa <= 0.80:
        interp = "Substantial agreement"
    else:
        interp = "Almost perfect agreement"

    return {
        "n": n,
        "kappa": round(kappa, 4),
        "interpretation": interp,
        "contingency_table": {
            "both_pass": a,
            "both_fail": d,
            "judge_only": b,
            "human_only": c,
        },
        "observed_agreement": round(p_observed, 4),
        "expected_agreement": round(p_expected, 4),
    }
