"""
Observability Engine: Structured JSON Logging, Correlation IDs, and Health Checks.
Provides:
1. Structured JSON logging with run_id and test_id correlation tracking.
2. Lightweight metrics collection (call counts, latency percentiles, error rates).
3. System health diagnostics: Database, Ollama, model availability, disk capacity.
"""

import json
import logging
import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional
import numpy as np

BASE_DIR = Path(__file__).resolve().parent.parent
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)


class StructuredJSONFormatter(logging.Formatter):
    """Formats log records as single-line JSON objects with correlation fields."""
    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "run_id": getattr(record, "run_id", None),
            "test_id": getattr(record, "test_id", None),
            "caller": f"{record.filename}:{record.lineno}",
        }
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_obj)


def get_structured_logger(name: str = "regguard") -> logging.Logger:
    """Configures and returns a structured JSON logger writing to logs/regguard.jsonl."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        fh = logging.FileHandler(LOGS_DIR / "regguard.jsonl", encoding="utf-8")
        fh.setFormatter(StructuredJSONFormatter())
        logger.addHandler(fh)
    return logger


# In-memory metrics accumulator
class MetricsRegistry:
    def __init__(self):
        self._calls: Dict[str, int] = {}
        self._latencies: Dict[str, List[float]] = {}
        self._errors: Dict[str, int] = {}
        self._start_time = time.time()

    def record_call(self, endpoint_or_task: str, latency_ms: float, success: bool = True):
        self._calls[endpoint_or_task] = self._calls.get(endpoint_or_task, 0) + 1
        self._latencies.setdefault(endpoint_or_task, []).append(latency_ms)
        if not success:
            self._errors[endpoint_or_task] = self._errors.get(endpoint_or_task, 0) + 1

    def get_metrics_summary(self) -> Dict[str, Any]:
        uptime_s = round(time.time() - self._start_time, 1)
        summary = {
            "uptime_seconds": uptime_s,
            "total_calls": sum(self._calls.values()),
            "total_errors": sum(self._errors.values()),
            "endpoints": {},
        }
        for ep, count in self._calls.items():
            lats = self._latencies.get(ep, [])
            p50 = float(np.percentile(lats, 50)) if lats else 0.0
            p95 = float(np.percentile(lats, 95)) if lats else 0.0
            summary["endpoints"][ep] = {
                "calls": count,
                "errors": self._errors.get(ep, 0),
                "error_rate": round(self._errors.get(ep, 0) / max(1, count), 4),
                "latency_p50_ms": round(p50, 2),
                "latency_p95_ms": round(p95, 2),
            }
        return summary


metrics_registry = MetricsRegistry()


def check_system_health() -> Dict[str, Any]:
    """
    Performs real-time local health check across:
    1. Database connectivity and type (MySQL or SQLite).
    2. Ollama daemon availability and model catalog.
    3. Disk space and memory on local volume.
    """
    # 1. Database Health
    db_status = "unhealthy"
    db_type = "unknown"
    db_latency_ms = 0.0
    try:
        from core.db import get_engine
        from sqlalchemy import text
        engine = get_engine()
        t0 = time.perf_counter()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_latency_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        db_status = "healthy"
        db_type = "sqlite" if "sqlite" in str(engine.url) else "mysql"
    except Exception as e:
        db_status = f"error: {e}"

    # 2. Ollama Health
    ollama_status = "unavailable"
    models_available: List[str] = []
    try:
        from core.llm import default_client
        avail, msg = default_client.is_available()
        if avail:
            ollama_status = "healthy"
            if "Available models:" in msg:
                models_available = [m.strip() for m in msg.split("Available models:")[-1].split(",") if m.strip()]
        else:
            ollama_status = "unhealthy"
    except Exception:
        ollama_status = "offline"

    # 3. Disk Space
    disk_free_gb = 0.0
    disk_total_gb = 0.0
    try:
        usage = shutil.disk_usage(str(BASE_DIR))
        disk_free_gb = round(usage.free / (1024 ** 3), 2)
        disk_total_gb = round(usage.total / (1024 ** 3), 2)
    except Exception:
        pass

    overall_healthy = (db_status == "healthy") and (ollama_status == "healthy")

    return {
        "status": "healthy" if overall_healthy else "degraded",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "database": {
            "status": db_status,
            "type": db_type,
            "ping_latency_ms": db_latency_ms,
        },
        "ollama": {
            "status": ollama_status,
            "models_count": len(models_available),
            "models": models_available[:5],
        },
        "disk": {
            "free_gb": disk_free_gb,
            "total_gb": disk_total_gb,
            "free_percent": round((disk_free_gb / max(1.0, disk_total_gb)) * 100.0, 1),
        },
    }
