"""
Comprehensive Tier 2 Test Suite: Engineering, Architecture, API, Security, and Extensibility.

Covers:
1. Pydantic v2 Configuration & Validation (core.config)
2. Security & Path Traversal Confinement (core.security)
3. Local RBAC & Authentication (core.auth)
4. Plugin Registry & Extension Points (core.plugins)
5. Structured JSON Logging, Metrics Registry & System Diagnostics (core.observability)
6. FastAPI Local REST API Endpoints & Telemetry (core.api)
7. Dual-Mode Client Adapter (core.api_client)
"""

import json
import pytest
from pathlib import Path
from fastapi import HTTPException
from pydantic import ValidationError

from core.config import AppSettings, get_settings
from core.security import safe_resolve_path, safe_load_yaml, PathTraversalError
from core.auth import (
    authenticate_user,
    has_permission,
    check_action_permitted,
    hash_password,
    ROLE_PERMISSIONS,
)
from core.plugins import (
    register_model_provider,
    get_model_provider,
    list_model_providers,
    register_check,
    get_custom_check,
    BaseModelProvider,
)
from core.observability import (
    get_structured_logger,
    metrics_registry,
    check_system_health,
    MetricsRegistry,
)
from core.api import (
    app,
    get_health,
    get_metrics,
    list_runs,
    get_run,
    run_gate,
    review_decision,
    GateRequest,
    ReviewRequest,
)
from core.api_client import RegGuardClient


# ==============================================================================
# 1. Pydantic v2 Configuration & Validation
# ==============================================================================
def test_app_settings_defaults():
    settings = AppSettings()
    assert settings.alpha == 0.05
    assert settings.k == 5
    assert settings.environment == "dev"
    assert settings.active_decision_rule == "mcnemar_exact"
    assert settings.non_inferiority_margin == 0.05
    assert settings.api_port == 8000


def test_app_settings_validation_errors():
    # Alpha must be in (0, 1)
    with pytest.raises(ValueError, match="Alpha significance level"):
        AppSettings(alpha=1.5)

    with pytest.raises(ValueError, match="Alpha significance level"):
        AppSettings(alpha=-0.05)

    # k must be an odd positive integer
    with pytest.raises(ValueError, match="must be an odd integer"):
        AppSettings(k=4)

    with pytest.raises(ValueError, match="must be at least 1"):
        AppSettings(k=-1)

    # Environment must be dev, staging, or prod
    with pytest.raises(ValueError, match="Invalid environment"):
        AppSettings(environment="sandbox")

    # Decision rule must be one of the four frozen variants
    with pytest.raises(ValueError, match="Invalid decision rule"):
        AppSettings(active_decision_rule="uncalibrated_heuristic")

    # Non-inferiority margin must be positive
    with pytest.raises(ValueError, match="Non-inferiority margin must be positive"):
        AppSettings(non_inferiority_margin=-0.01)


def test_get_settings_singleton():
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2


# ==============================================================================
# 2. Security & Path Traversal Confinement
# ==============================================================================
def test_safe_resolve_path_within_boundary(tmp_path):
    sub = tmp_path / "safe_dir" / "file.txt"
    sub.parent.mkdir(parents=True)
    sub.write_text("hello")

    resolved = safe_resolve_path("safe_dir/file.txt", allowed_base=tmp_path)
    assert resolved == sub.resolve()


def test_safe_resolve_path_traversal_rejection(tmp_path):
    forbidden = tmp_path.parent / "escape.txt"

    with pytest.raises(PathTraversalError, match="Path traversal detected"):
        safe_resolve_path("../escape.txt", allowed_base=tmp_path)

    with pytest.raises(PathTraversalError, match="Path traversal detected"):
        safe_resolve_path("/etc/passwd", allowed_base=tmp_path)


def test_safe_load_yaml(tmp_path):
    yaml_file = tmp_path / "test_policy.yaml"
    yaml_file.write_text("version: 2.0\ngate:\n  alpha: 0.01\n")

    data = safe_load_yaml(yaml_file, allowed_base=tmp_path)
    assert data["version"] == 2.0
    assert data["gate"]["alpha"] == 0.01

    with pytest.raises(FileNotFoundError):
        safe_load_yaml(tmp_path / "non_existent.yaml", allowed_base=tmp_path)


# ==============================================================================
# 3. Local RBAC & Authentication
# ==============================================================================
def test_password_hashing():
    h1 = hash_password("secret_password", salt="fixed_salt")
    h2 = hash_password("secret_password", salt="fixed_salt")
    h3 = hash_password("different_password", salt="fixed_salt")
    assert h1 == h2
    assert h1 != h3
    assert len(h1) == 64  # SHA-256 hex string


def test_authenticate_default_roles():
    author = authenticate_user("developer", "dev_pass")
    assert author is not None
    assert author["role"] == "author"

    reviewer = authenticate_user("reviewer_lead", "review_pass")
    assert reviewer is not None
    assert reviewer["role"] == "reviewer"

    admin = authenticate_user("admin", "admin_pass")
    assert admin is not None
    assert admin["role"] == "admin"

    # Invalid password
    assert authenticate_user("admin", "wrong_password") is None
    # Unknown user
    assert authenticate_user("ghost_user", "dev_pass") is None


def test_rbac_permission_enforcement():
    # Author permissions
    assert has_permission("author", "run_tests") is True
    assert has_permission("author", "view_dashboard") is True
    assert has_permission("author", "approve_change_request") is False
    assert has_permission("author", "promote_prod") is False

    # Reviewer permissions
    assert has_permission("reviewer", "approve_change_request") is True
    assert has_permission("reviewer", "promote_staging") is True
    assert has_permission("reviewer", "promote_prod") is False

    # Admin permissions
    assert has_permission("admin", "promote_prod") is True
    assert has_permission("admin", "execute_rollback") is True
    assert has_permission("admin", "edit_policy") is True

    # Check action permitted helper
    assert check_action_permitted("reviewer", "promote_staging") is True
    with pytest.raises(PermissionError, match="Action 'promote_prod' is prohibited"):
        check_action_permitted("reviewer", "promote_prod")


# ==============================================================================
# 4. Plugin Registry & Extension Points
# ==============================================================================
def test_model_provider_plugin_registration():
    @register_model_provider("test_mock_provider")
    class TestMockProvider(BaseModelProvider):
        def generate(self, prompt, system=None, temperature=0.0, seed=None):
            return "MOCK_OUTPUT", 42.0

        def get_digest(self):
            return "sha256:testmock123"

    assert "test_mock_provider" in list_model_providers()
    provider = get_model_provider("test_mock_provider", model_id="custom-mock")
    out, lat = provider.generate("hello")
    assert out == "MOCK_OUTPUT"
    assert lat == 42.0
    assert provider.get_digest() == "sha256:testmock123"


def test_custom_check_plugin_registration():
    @register_check("test_length_check")
    def length_check(output, test_case):
        max_len = test_case.get("max_length", 100)
        passed = len(str(output)) <= max_len
        reason = "Pass" if passed else f"Output length {len(str(output))} exceeds {max_len}"
        return passed, reason

    fn = get_custom_check("test_length_check")
    assert fn is not None

    p1, r1 = fn("short", {"max_length": 10})
    assert p1 is True
    assert r1 == "Pass"

    p2, r2 = fn("this string is much too long", {"max_length": 10})
    assert p2 is False
    assert "exceeds 10" in r2


# ==============================================================================
# 5. Structured JSON Logging & Observability
# ==============================================================================
def test_structured_logger_emission(tmp_path):
    logger = get_structured_logger("test_telemetry")
    extra = {"run_id": "test_run_123", "test_id": "case_01"}
    logger.info("Test event telemetry recorded", extra=extra)

    log_file = Path("logs/regguard.jsonl")
    assert log_file.exists()

    with open(log_file, "r", encoding="utf-8") as f:
        lines = f.readlines()
        assert len(lines) > 0
        last = json.loads(lines[-1])
        assert "timestamp" in last
        assert last["level"] in {"INFO", "WARNING", "ERROR"}


def test_metrics_registry_percentiles():
    reg = MetricsRegistry()
    for latency in [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]:
        reg.record_call("/api/test", latency, success=True)
    reg.record_call("/api/test", 200.0, success=False)

    summary = reg.get_metrics_summary()
    assert summary["total_calls"] == 11
    assert summary["total_errors"] == 1
    ep = summary["endpoints"]["/api/test"]
    assert ep["calls"] == 11
    assert ep["errors"] == 1
    assert ep["latency_p50_ms"] >= 40.0
    assert ep["latency_p95_ms"] >= 100.0


def test_system_health_diagnostics():
    health = check_system_health()
    assert "timestamp" in health
    assert "status" in health
    assert "database" in health
    assert "ollama" in health
    assert "disk" in health


# ==============================================================================
# 6. FastAPI Local REST API Endpoints & Telemetry
# ==============================================================================
def test_api_health_endpoint():
    data = get_health()
    assert isinstance(data, dict)
    assert data["status"] in {"healthy", "degraded"}
    assert "database" in data
    assert "ollama" in data
    assert "disk" in data


def test_api_metrics_endpoint():
    data = get_metrics()
    assert isinstance(data, dict)
    assert "uptime_seconds" in data
    assert "total_calls" in data
    assert "endpoints" in data


def test_api_runs_endpoint():
    runs = list_runs(limit=5)
    assert isinstance(runs, list)


def test_api_run_detail_not_found():
    with pytest.raises(HTTPException) as exc_info:
        get_run(run_id=999999999)
    assert exc_info.value.status_code == 404


def test_api_gate_validation():
    # Valid GateRequest schema
    valid_req = GateRequest(baseline_id=1, candidate_id=2, alpha=0.05)
    assert valid_req.baseline_id == 1
    assert valid_req.candidate_id == 2
    assert valid_req.alpha == 0.05

    # Invalid alpha out of range
    with pytest.raises(ValidationError):
        GateRequest(baseline_id=1, candidate_id=2, alpha=0.99)


def test_api_review_validation():
    valid_rev = ReviewRequest(
        review_id=1,
        human_passed=True,
        reviewer_id="lead_reviewer",
        comment="Adjudicated as valid dialect output.",
    )
    assert valid_rev.reviewer_id == "lead_reviewer"
    assert valid_rev.human_passed is True

    # Empty reviewer_id validation error
    with pytest.raises(ValidationError):
        ReviewRequest(
            review_id=1,
            human_passed=True,
            reviewer_id="",
            comment="comment",
        )


# ==============================================================================
# 7. Dual-Mode Client Adapter
# ==============================================================================
def test_api_client_direct_fallback():
    client_adapter = RegGuardClient(mode="direct")
    health = client_adapter.get_health()
    assert "status" in health
    assert "database" in health
    assert "ollama" in health

    metrics = client_adapter.get_metrics()
    assert "total_calls" in metrics
