"""
RegGuard Client Adapter.
Supports switching between direct in-process Python calls and the local FastAPI REST API.
Configured via `USE_REST_API=true` environment variable or policy setting.
"""

import os
import requests
from typing import Dict, Any, List, Optional


class RegGuardClient:
    def __init__(self, base_url: str = "http://127.0.0.1:8000", mode: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        # mode: "api" or "direct"
        self.mode = mode or os.getenv("REGGUARD_CLIENT_MODE", "direct").lower()

    def is_api_mode(self) -> bool:
        if self.mode != "api":
            return False
        # Test if API is actually responsive
        try:
            r = requests.get(f"{self.base_url}/health", timeout=0.5)
            return r.status_code == 200
        except Exception:
            return False

    def get_health(self) -> Dict[str, Any]:
        if self.is_api_mode():
            try:
                resp = requests.get(f"{self.base_url}/health", timeout=2.0)
                if resp.status_code == 200:
                    return resp.json()
            except Exception:
                pass
        # Fallback to direct Python call
        from core.observability import check_system_health
        return check_system_health()

    def get_metrics(self) -> Dict[str, Any]:
        if self.is_api_mode():
            try:
                resp = requests.get(f"{self.base_url}/metrics", timeout=2.0)
                if resp.status_code == 200:
                    return resp.json()
            except Exception:
                pass
        from core.observability import metrics_registry
        return metrics_registry.get_metrics_summary()

    def list_runs(self, limit: int = 20, verdict: Optional[str] = None) -> List[Dict[str, Any]]:
        if self.is_api_mode():
            try:
                params: Dict[str, Any] = {"limit": limit}
                if verdict:
                    params["verdict"] = verdict
                resp = requests.get(f"{self.base_url}/runs", params=params, timeout=2.0)
                if resp.status_code == 200:
                    return resp.json()
            except Exception:
                pass
        from core.db import get_session
        from core.models import Comparison
        with get_session() as session:
            q = session.query(Comparison)
            if verdict:
                q = q.filter_by(verdict=verdict.upper())
            return [r.to_dict() for r in q.order_by(Comparison.created_at.desc()).limit(limit).all()]


default_api_client = RegGuardClient()
