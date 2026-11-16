import os
from pathlib import Path
import yaml

BASE_DIR = Path(__file__).resolve().parent.parent


def get_default_policy():
    return {
        "version": "1.0.0",
        "alpha": 0.05,
        "minimum_tests": 10,
        "k": 5,
        "allowed_models": ["qwen2.5:3b", "qwen2.5:7b", "qwen2.5:latest", "qwen3:4b"],
        "critical_test_ids": [
            "ent_01",
            "sent_01",
            "sum_01",
            "doc_json_crit_01",
            "doc_json_crit_02",
            "sql_crit_01",
            "sql_crit_02",
            "meet_crit_01",
            "meet_crit_02",
        ],
        "required_approvers": ["Alice Reviewer", "Bob Lead", "Carol Admin"],
    }


def load_policy(policy_path=None):
    if policy_path is None:
        policy_path = BASE_DIR / "policy.yaml"
    else:
        policy_path = Path(policy_path)

    if not policy_path.exists():
        return get_default_policy()

    try:
        with open(policy_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except Exception:
        return get_default_policy()

    default = get_default_policy()
    for k, v in default.items():
        if k not in data:
            data[k] = v
    return data


def load_approvers(approvers_path=None):
    if approvers_path is None:
        approvers_path = BASE_DIR / "approvers.yaml"
    else:
        approvers_path = Path(approvers_path)

    if not approvers_path.exists():
        return ["Alice Reviewer", "Bob Lead", "Carol Admin"]

    try:
        with open(approvers_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        entries = data.get("approvers", [])
        names = []
        for e in entries:
            if isinstance(e, dict) and "name" in e:
                names.append(e["name"])
            elif isinstance(e, str):
                names.append(e)
        return names if names else ["Alice Reviewer", "Bob Lead", "Carol Admin"]
    except Exception:
        return ["Alice Reviewer", "Bob Lead", "Carol Admin"]


def is_valid_approver(name, approvers_path=None):
    if not name or not str(name).strip():
        return False
    valid = load_approvers(approvers_path)
    clean_target = str(name).strip().lower()
    for v in valid:
        if str(v).strip().lower() == clean_target:
            return True
    return False


def validate_candidate_model(model_name, policy=None):
    if policy is None:
        policy = load_policy()
    allowed = policy.get("allowed_models", [])
    if not allowed:
        return True
    return str(model_name).strip() in allowed

