from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    JSON,
    Index,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Artifact(Base):
    __tablename__ = "artifacts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hash = Column(String(64), nullable=True, index=True)
    type = Column(String(32), nullable=False, default="prompt")
    name = Column(String(255), nullable=False)
    path = Column(String(512), nullable=False)
    manifest = Column(JSON, default=dict)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    @property
    def short_hash(self):
        return self.hash[:8] if self.hash else ""

    def to_dict(self):
        return {
            "id": self.id,
            "hash": self.hash,
            "short_hash": self.short_hash,
            "type": self.type,
            "name": self.name,
            "path": self.path,
            "manifest": self.manifest or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Version(Base):
    __tablename__ = "versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    git_hash = Column(String(64), unique=True, nullable=False, index=True)
    message = Column(Text, nullable=False)
    author = Column(String(128), default="Developer")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    files_changed = Column(JSON, default=list)

    @property
    def short_hash(self):
        return self.git_hash[:8] if self.git_hash else ""

    def to_dict(self):
        return {
            "id": self.id,
            "git_hash": self.git_hash,
            "short_hash": self.short_hash,
            "message": self.message,
            "author": self.author,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "files_changed": self.files_changed or [],
        }


class Run(Base):
    __tablename__ = "runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    version_id = Column(Integer, ForeignKey("versions.id"), nullable=True)
    artifact_id = Column(Integer, ForeignKey("artifacts.id"), nullable=True)
    model_name = Column(String(128), default="qwen2.5:3b")
    temperature = Column(Float, default=0.7)
    n_runs = Column(Integer, default=5)
    overall_pass_rate = Column(Float, default=0.0)
    consistency = Column(Float, default=0.0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "version_id": self.version_id,
            "artifact_id": self.artifact_id,
            "model_name": self.model_name,
            "temperature": self.temperature,
            "n_runs": self.n_runs,
            "overall_pass_rate": self.overall_pass_rate,
            "consistency": self.consistency,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Result(Base):
    __tablename__ = "results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(Integer, ForeignKey("runs.id"), nullable=False)
    test_id = Column(String(128), nullable=False)
    run_index = Column(Integer, default=0)
    output = Column(Text, nullable=True)
    passed = Column(Boolean, default=False)
    latency_ms = Column(Float, default=0.0)
    check_details = Column(JSON, default=list)
    model_id = Column(String(128), default="qwen2.5:3b")
    model_digest = Column(String(128), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "run_id": self.run_id,
            "test_id": self.test_id,
            "run_index": self.run_index,
            "output": self.output,
            "passed": self.passed,
            "latency_ms": self.latency_ms,
            "check_details": self.check_details or [],
            "model_id": self.model_id,
            "model_digest": self.model_digest,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class BaselineRegistry(Base):
    __tablename__ = "baselines"

    id = Column(Integer, primary_key=True, autoincrement=True)
    artifact_id = Column(Integer, ForeignKey("artifacts.id"), nullable=False)
    set_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    set_by = Column(String(128), default="gate")
    notes = Column(Text, nullable=True)

    artifact = relationship("Artifact")

    def to_dict(self):
        return {
            "id": self.id,
            "artifact_id": self.artifact_id,
            "set_at": self.set_at.isoformat() if self.set_at else None,
            "set_by": self.set_by,
            "notes": self.notes,
        }


class TestCase(Base):
    __tablename__ = "test_cases"
    __test__ = False

    id = Column(String(128), primary_key=True)
    suite = Column(String(128), nullable=False, default="default")
    target = Column(String(128), nullable=False)
    input = Column(Text, nullable=False)
    slices = Column(JSON, default=dict)
    checks = Column(JSON, default=list)
    origin = Column(String(64), default="golden")
    rule_id = Column(String(128), nullable=True)
    critical = Column(Boolean, default=False)

    def to_dict(self):
        return {
            "id": self.id,
            "suite": self.suite,
            "target": self.target,
            "input": self.input,
            "slices": self.slices or {},
            "checks": self.checks or [],
            "origin": self.origin,
            "rule_id": self.rule_id,
            "critical": bool(self.critical),
        }


class Trace(Base):
    __tablename__ = "traces"

    id = Column(Integer, primary_key=True, autoincrement=True)
    artifact_id = Column(Integer, ForeignKey("artifacts.id"), nullable=False)
    test_id = Column(String(128), ForeignKey("test_cases.id"), nullable=False)
    run_index = Column(Integer, nullable=False, default=0)
    output = Column(Text, nullable=True)
    skills_used = Column(JSON, default=list)
    tool_calls = Column(JSON, default=list)
    latency_ms = Column(Float, default=0.0)
    seed = Column(Integer, default=42)
    model = Column(String(128), default="qwen2.5:3b")
    model_digest = Column(String(128), nullable=True)
    temperature = Column(Float, default=0.7)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("idx_artifact_test_run", "artifact_id", "test_id", "run_index"),
    )

    def __init__(self, **kwargs):
        if "model_id" in kwargs and "model" not in kwargs:
            kwargs["model"] = kwargs.pop("model_id")
        super().__init__(**kwargs)

    @property
    def model_id(self):
        return self.model

    @model_id.setter
    def model_id(self, val):
        self.model = val

    def to_dict(self):
        return {
            "id": self.id,
            "artifact_id": self.artifact_id,
            "test_id": self.test_id,
            "run_index": self.run_index,
            "output": self.output,
            "skills_used": self.skills_used or [],
            "tool_calls": self.tool_calls or [],
            "latency_ms": self.latency_ms,
            "seed": self.seed,
            "model": self.model,
            "model_id": self.model,
            "model_digest": self.model_digest,
            "temperature": self.temperature,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Score(Base):
    __tablename__ = "scores"

    id = Column(Integer, primary_key=True, autoincrement=True)
    trace_id = Column(Integer, ForeignKey("traces.id"), nullable=False)
    test_id = Column(String(128), nullable=False)
    artifact_id = Column(Integer, nullable=False)
    run_index = Column(Integer, nullable=False, default=0)
    passed = Column(Boolean, nullable=False, default=False)
    score = Column(Float, default=0.0)
    check_details = Column(JSON, default=list)
    model_id = Column(String(128), default="qwen2.5:3b")
    model_digest = Column(String(128), nullable=True)

    __table_args__ = (
        Index("idx_score_artifact_test_run", "artifact_id", "test_id", "run_index"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "trace_id": self.trace_id,
            "test_id": self.test_id,
            "artifact_id": self.artifact_id,
            "run_index": self.run_index,
            "passed": self.passed,
            "score": self.score,
            "check_details": self.check_details or [],
            "model_id": self.model_id,
            "model_digest": self.model_digest,
        }


class Comparison(Base):
    __tablename__ = "comparisons"

    id = Column(Integer, primary_key=True, autoincrement=True)
    baseline_id = Column(Integer, ForeignKey("artifacts.id"), nullable=False)
    candidate_id = Column(Integer, ForeignKey("artifacts.id"), nullable=False)
    delta_pass_rate = Column(Float, nullable=False, default=0.0)
    p_value = Column(Float, nullable=True)
    regressed_count = Column(Integer, default=0)
    fixed_count = Column(Integer, default=0)
    unchanged_count = Column(Integer, default=0)
    still_failing_count = Column(Integer, default=0)
    verdict = Column(String(32), default="BLOCK")
    report_md = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "baseline_id": self.baseline_id,
            "candidate_id": self.candidate_id,
            "delta_pass_rate": self.delta_pass_rate,
            "p_value": self.p_value,
            "regressed_count": self.regressed_count,
            "fixed_count": self.fixed_count,
            "unchanged_count": self.unchanged_count,
            "still_failing_count": self.still_failing_count,
            "verdict": self.verdict,
            "report_md": self.report_md,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ChangeRequest(Base):
    __tablename__ = "change_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    artifact_id = Column(Integer, ForeignKey("artifacts.id"), nullable=True)
    base_commit = Column(String(64), nullable=False)
    candidate_commit = Column(String(64), nullable=False)
    requester = Column(String(128), default="Developer")
    status = Column(String(32), default="submitted")  # submitted, gated, approved, rejected, promoted, rolled_back
    gate_verdict = Column(String(32), nullable=True)   # PROMOTE, BLOCK
    report_md = Column(Text, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    approver = Column(String(128), nullable=True)
    approval_comment = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "artifact_id": self.artifact_id,
            "base_commit": self.base_commit,
            "candidate_commit": self.candidate_commit,
            "requester": self.requester,
            "status": self.status,
            "gate_verdict": self.gate_verdict,
            "report_md": self.report_md,
            "rejection_reason": self.rejection_reason,
            "approver": self.approver,
            "approval_comment": self.approval_comment,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    who = Column(String(128), nullable=False)
    what = Column(String(128), nullable=False)
    base_commit = Column(String(64), nullable=True)
    candidate_commit = Column(String(64), nullable=True)
    model_id = Column(String(128), nullable=True)
    model_digest = Column(String(128), nullable=True)
    seeds = Column(JSON, default=list)
    test_suite_hash = Column(String(64), nullable=True)
    p_value = Column(Float, nullable=True)
    b = Column(Integer, default=0)
    c = Column(Integer, default=0)
    verdict = Column(String(32), nullable=True)
    approver = Column(String(128), nullable=True)
    comment = Column(Text, nullable=True)
    report_path = Column(String(256), nullable=True)
    traces_link = Column(String(256), nullable=True)
    metadata_json = Column(JSON, default=dict)
    prev_hash = Column(String(64), nullable=True)
    entry_hash = Column(String(64), nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "who": self.who,
            "what": self.what,
            "base_commit": self.base_commit,
            "candidate_commit": self.candidate_commit,
            "model_id": self.model_id,
            "model_digest": self.model_digest,
            "seeds": self.seeds or [],
            "test_suite_hash": self.test_suite_hash,
            "p_value": self.p_value,
            "b": self.b,
            "c": self.c,
            "verdict": self.verdict,
            "approver": self.approver,
            "comment": self.comment,
            "report_path": self.report_path,
            "traces_link": self.traces_link,
            "metadata_json": self.metadata_json or {},
            "prev_hash": self.prev_hash,
            "entry_hash": self.entry_hash,
        }


# Enforce append-only constraint at the SQLAlchemy event level
from sqlalchemy import event


@event.listens_for(AuditLog, "before_update")
def audit_log_before_update(mapper, connection, target):
    raise PermissionError("AuditLog records are append-only and cannot be modified.")


@event.listens_for(AuditLog, "before_delete")
def audit_log_before_delete(mapper, connection, target):
    raise PermissionError("AuditLog records are append-only and cannot be deleted.")


class ReviewItem(Base):
    __tablename__ = "review_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    score_id = Column(Integer, ForeignKey("scores.id"), nullable=True)
    trace_id = Column(Integer, ForeignKey("traces.id"), nullable=False)
    test_id = Column(String(128), nullable=False)
    artifact_id = Column(Integer, nullable=False)
    flag_reason = Column(String(255), nullable=False)
    model_output = Column(Text, nullable=True)
    judge_score = Column(Float, nullable=True)
    judge_passed = Column(Boolean, nullable=True)
    status = Column(String(32), default="pending")  # pending, reviewed
    human_passed = Column(Boolean, nullable=True)
    reviewer_id = Column(String(128), nullable=True)
    comment = Column(Text, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "score_id": self.score_id,
            "trace_id": self.trace_id,
            "test_id": self.test_id,
            "artifact_id": self.artifact_id,
            "flag_reason": self.flag_reason,
            "model_output": self.model_output,
            "judge_score": self.judge_score,
            "judge_passed": self.judge_passed,
            "status": self.status,
            "human_passed": self.human_passed,
            "reviewer_id": self.reviewer_id,
            "comment": self.comment,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class EnvironmentBaseline(Base):
    __tablename__ = "environment_baselines"

    id = Column(Integer, primary_key=True, autoincrement=True)
    environment = Column(String(32), nullable=False, index=True)  # dev, staging, prod
    artifact_id = Column(Integer, ForeignKey("artifacts.id"), nullable=False)
    git_hash = Column(String(64), nullable=False)
    semver = Column(String(32), nullable=False, default="1.0.0")
    promoted_by = Column(String(128), default="Developer")
    gate_verdict = Column(String(32), default="PROMOTE")
    gate_comparison_id = Column(Integer, ForeignKey("comparisons.id"), nullable=True)
    release_notes = Column(Text, nullable=True)
    promoted_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "environment": self.environment,
            "artifact_id": self.artifact_id,
            "git_hash": self.git_hash,
            "semver": self.semver,
            "promoted_by": self.promoted_by,
            "gate_verdict": self.gate_verdict,
            "gate_comparison_id": self.gate_comparison_id,
            "release_notes": self.release_notes,
            "promoted_at": self.promoted_at.isoformat() if self.promoted_at else None,
        }


