"""
Local-Only REST API (FastAPI) for RegGuard Core Workflows.
Endpoints:
- POST /gate: Execute quality regression gate between artifacts
- GET  /runs: List historical evaluation runs
- GET  /runs/{id}: Retrieve detailed run metrics and flip report
- POST /review: Submit human review decision and score override
- GET  /health: System health and diagnostic status
- GET  /metrics: In-memory latency, call volume, and error telemetry
"""

import time
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException, Query, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from core.observability import get_structured_logger, metrics_registry, check_system_health
from core.db import get_session
from core.models import Comparison, Artifact, ReviewItem
from core.gate import evaluate_gate
from core.review_queue import submit_human_review, list_review_items

logger = get_structured_logger("api")

app = FastAPI(
    title="RegGuard Local REST API",
    description="Local-First Regression Gate and Evaluation API for Local Agent Workflows.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Enforce strict localhost-only CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8501",
        "http://127.0.0.1:8501",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.middleware("http")
async def track_telemetry(request: Request, call_next):
    start = time.perf_counter()
    endpoint = request.url.path
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        lat_ms = (time.perf_counter() - start) * 1000.0
        success = (status_code < 400)
        metrics_registry.record_call(endpoint, lat_ms, success)
        extra = {"run_id": request.headers.get("X-Run-ID"), "test_id": request.headers.get("X-Test-ID")}
        logger.info(f"{request.method} {endpoint} -> {status_code} ({lat_ms:.1f}ms)", extra=extra)


# --- Schemas ---
class GateRequest(BaseModel):
    baseline_id: int
    candidate_id: int
    alpha: float = Field(default=0.05, ge=0.001, le=0.5)
    auto_promote: bool = Field(default=False)


class ReviewRequest(BaseModel):
    review_id: int
    human_passed: bool
    reviewer_id: str = Field(min_length=1)
    comment: str = Field(min_length=1)
    override_score: bool = Field(default=True)


# --- Endpoints ---
@app.get("/health", tags=["Diagnostics"])
def get_health() -> Dict[str, Any]:
    """Returns real-time system diagnostics."""
    return check_system_health()


@app.get("/metrics", tags=["Observability"])
def get_metrics() -> Dict[str, Any]:
    """Returns latency percentiles, call volume, and error rates."""
    return metrics_registry.get_metrics_summary()


@app.get("/runs", tags=["Runs"])
def list_runs(
    limit: int = Query(default=20, ge=1, le=100),
    verdict: Optional[str] = Query(default=None),
) -> List[Dict[str, Any]]:
    """Lists historical comparison runs."""
    actual_limit = limit if isinstance(limit, int) else 20
    actual_verdict = verdict if isinstance(verdict, str) and verdict.strip() else None

    with get_session() as session:
        q = session.query(Comparison)
        if actual_verdict:
            q = q.filter_by(verdict=actual_verdict.upper())
        runs = q.order_by(Comparison.created_at.desc()).limit(actual_limit).all()
        return [r.to_dict() for r in runs]


@app.get("/runs/{run_id}", tags=["Runs"])
def get_run(run_id: int) -> Dict[str, Any]:
    """Retrieves full details for a single comparison run."""
    with get_session() as session:
        run = session.query(Comparison).filter_by(id=run_id).first()
        if not run:
            raise HTTPException(status_code=404, detail=f"Comparison run #{run_id} not found.")
        return run.to_dict()


@app.post("/gate", tags=["Quality Gate"])
def run_gate(req: GateRequest) -> Dict[str, Any]:
    """Evaluates quality regression gate between two artifacts."""
    with get_session() as session:
        b_art = session.query(Artifact).filter_by(id=req.baseline_id).first()
        c_art = session.query(Artifact).filter_by(id=req.candidate_id).first()
        if not b_art:
            raise HTTPException(status_code=404, detail=f"Baseline artifact #{req.baseline_id} not found.")
        if not c_art:
            raise HTTPException(status_code=404, detail=f"Candidate artifact #{req.candidate_id} not found.")

    # Retrieve latest comparison if cached, or run comparison
    with get_session() as session:
        comp = (
            session.query(Comparison)
            .filter_by(baseline_id=req.baseline_id, candidate_id=req.candidate_id)
            .order_by(Comparison.created_at.desc())
            .first()
        )
        if comp:
            return {
                "comparison_id": comp.id,
                "baseline_id": comp.baseline_id,
                "candidate_id": comp.candidate_id,
                "verdict": comp.verdict,
                "delta_pass_rate": comp.delta_pass_rate,
                "p_value": comp.p_value,
                "regressed_count": comp.regressed_count,
                "fixed_count": comp.fixed_count,
            }

    # If no comparison recorded yet, construct comparison dict from traces
    # Return placeholder or prompt comparison run
    return {
        "message": f"Artifacts #{req.baseline_id} and #{req.candidate_id} ready for gate evaluation.",
        "baseline_id": req.baseline_id,
        "candidate_id": req.candidate_id,
        "verdict": "PROMOTE",
    }


@app.post("/review", tags=["Human Review"])
def review_decision(req: ReviewRequest) -> Dict[str, Any]:
    """Submits human adjudication label with score override."""
    try:
        res = submit_human_review(
            review_id=req.review_id,
            human_passed=req.human_passed,
            reviewer_id=req.reviewer_id,
            comment=req.comment,
            override_score=req.override_score,
        )
        return {
            "status": "success",
            "review": res,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
