"""
Security & Input Sanitization Module.
Provides:
1. Path-traversal defense and directory confinement (`safe_resolve_path`).
2. Safe YAML file loader (`safe_load_yaml`).
3. Model prompt input sanitizer.
"""

import os
from pathlib import Path
from typing import Optional, Union, Dict, Any
import yaml

BASE_DIR = Path(__file__).resolve().parent.parent


class PathTraversalError(PermissionError):
    """Raised when an input path attempts to traverse outside the permitted boundary."""
    pass


def safe_resolve_path(
    user_path: Union[str, Path],
    allowed_base: Optional[Union[str, Path]] = None,
) -> Path:
    """
    Resolves and normalizes user-provided path inputs.
    Strictly asserts that the resolved path is confined within allowed_base.
    Prevents directory traversal attacks via `../`, symlinks, or absolute paths.
    """
    base = Path(allowed_base).resolve() if allowed_base else BASE_DIR.resolve()
    
    raw_path = Path(user_path)
    if raw_path.is_absolute():
        resolved = raw_path.resolve()
    else:
        resolved = (base / raw_path).resolve()

    try:
        resolved.relative_to(base)
    except ValueError:
        raise PathTraversalError(
            f"Path traversal detected: Path '{user_path}' resolves outside allowed root '{base}'."
        )

    return resolved


def safe_load_yaml(
    file_path: Union[str, Path],
    allowed_base: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """Safely loads YAML documents using yaml.safe_load."""
    target = safe_resolve_path(file_path, allowed_base=allowed_base)
    if not target.exists():
        raise FileNotFoundError(f"YAML file not found: {target}")
    with open(target, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}
