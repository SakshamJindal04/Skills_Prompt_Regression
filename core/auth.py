"""
Local Role-Based Access Control (RBAC) & Authentication Engine.
Supports:
1. Single-user mode (default, backwards compatible).
2. Multi-role access control (author, reviewer, admin) backed by local hashed credentials.
3. Permission enforcement for promotion, rollback, and policy modification.
"""

import hashlib
import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, List

BASE_DIR = Path(__file__).resolve().parent.parent
CREDENTIALS_FILE = BASE_DIR / "data" / "credentials.json"

ROLE_PERMISSIONS = {
    "author": {
        "view_dashboard",
        "run_tests",
        "run_comparison",
        "view_traces",
        "submit_change_request",
    },
    "reviewer": {
        "view_dashboard",
        "run_tests",
        "run_comparison",
        "view_traces",
        "submit_change_request",
        "human_review_label",
        "score_override",
        "approve_change_request",
        "promote_dev",
        "promote_staging",
    },
    "admin": {
        "view_dashboard",
        "run_tests",
        "run_comparison",
        "view_traces",
        "submit_change_request",
        "human_review_label",
        "score_override",
        "approve_change_request",
        "promote_dev",
        "promote_staging",
        "promote_prod",
        "execute_rollback",
        "edit_policy",
        "manage_users",
    },
}


def hash_password(password: str, salt: str = "regguard_local_salt") -> str:
    """Computes PBKDF2 HMAC SHA-256 hash for local user passwords."""
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations=100_000,
    ).hex()


def _ensure_default_credentials():
    """Seeds default local role accounts if credentials file does not exist."""
    if not CREDENTIALS_FILE.exists():
        CREDENTIALS_FILE.parent.mkdir(parents=True, exist_ok=True)
        default_users = {
            "developer": {
                "username": "developer",
                "role": "author",
                "password_hash": hash_password("dev_pass"),
            },
            "reviewer_lead": {
                "username": "reviewer_lead",
                "role": "reviewer",
                "password_hash": hash_password("review_pass"),
            },
            "admin": {
                "username": "admin",
                "role": "admin",
                "password_hash": hash_password("admin_pass"),
            },
        }
        CREDENTIALS_FILE.write_text(json.dumps(default_users, indent=2), encoding="utf-8")


def authenticate_user(username: str, password: str) -> Optional[Dict[str, Any]]:
    """Authenticates local user credentials, returning user record if valid."""
    _ensure_default_credentials()
    try:
        users = json.loads(CREDENTIALS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None

    clean_user = username.strip().lower()
    user_record = users.get(clean_user)
    if not user_record:
        return None

    hashed = hash_password(password)
    if hashed == user_record.get("password_hash"):
        return {
            "username": user_record["username"],
            "role": user_record["role"],
        }
    return None


def has_permission(role: str, action: str) -> bool:
    """Verifies whether a given role holds permission for an action."""
    clean_role = str(role or "author").strip().lower()
    allowed_actions = ROLE_PERMISSIONS.get(clean_role, set())
    return action in allowed_actions


def check_action_permitted(user_role: str, action: str) -> bool:
    """Raises PermissionError if action is unauthorized for the user's role."""
    if not has_permission(user_role, action):
        raise PermissionError(
            f"Action '{action}' is prohibited for role '{user_role}'. Required permission level exceeds caller grant."
        )
    return True
