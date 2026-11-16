"""
Git repository operations on the managed workspace/ folder.
Handles commit creation, version history, unified diffs, checkout, reverting, and database synchronization.
"""

import os
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

import git
from git import Repo, GitCommandError

from core.models import Version, Artifact
from core.db import get_session


def get_workspace_path(subpath: str = "") -> Path:
    """Return absolute path inside workspace/."""
    base = Path(__file__).resolve().parent.parent / "workspace"
    base.mkdir(parents=True, exist_ok=True)
    if subpath:
        return base / subpath
    return base


def init_repo(workspace_dir: Optional[str] = None) -> Repo:
    """
    Ensure the workspace directory is an initialized Git repository.
    Creates an initial commit if the repo is empty.
    """
    ws = Path(workspace_dir) if workspace_dir else get_workspace_path()
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "prompts").mkdir(parents=True, exist_ok=True)
    (ws / "skills").mkdir(parents=True, exist_ok=True)

    try:
        repo = Repo(ws)
    except git.InvalidGitRepositoryError:
        repo = Repo.init(ws)

    # Configure default git user for this local repo if not already set
    with repo.config_writer() as config:
        if not config.has_section("user"):
            config.add_section("user")
        if not config.has_option("user", "name"):
            config.set_value("user", "name", "Regression Manager")
        if not config.has_option("user", "email"):
            config.set_value("user", "email", "regression@local.test")

    # If repo has no commits, create a README and initial commit
    if not repo.heads or len(repo.branches) == 0:
        readme_file = ws / "README.md"
        if not readme_file.exists():
            readme_file.write_text("# Managed Workspace for Prompts & Skills\n")
        repo.git.add(A=True)
        repo.index.commit("Initial workspace setup")

    return repo


def commit_changes(
    message: str,
    author_name: str = "Developer",
    author_email: str = "dev@local.test",
    files: Optional[List[str]] = None,
    workspace_dir: Optional[str] = None,
) -> str:
    """
    Stage specified files (or all changes) and create a Git commit.
    Returns the full commit hash.
    """
    repo = init_repo(workspace_dir)
    actor = git.Actor(author_name, author_email)

    if files:
        for f in files:
            repo.git.add(f)
    else:
        repo.git.add(A=True)

    # Check if there are changes to commit
    if not repo.is_dirty(untracked_files=True):
        if repo.head.is_valid():
            return repo.head.commit.hexsha
        raise ValueError("No changes to commit and no valid HEAD.")

    commit = repo.index.commit(message, author=actor, committer=actor)
    return commit.hexsha


def list_versions(workspace_dir: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    List all commits in reverse chronological order with changed files and metadata.
    """
    repo = init_repo(workspace_dir)
    versions = []

    for commit in repo.iter_commits():
        # Determine changed files
        files_changed = []
        if commit.parents:
            diffs = commit.parents[0].diff(commit)
            for d in diffs:
                if d.a_path:
                    files_changed.append(d.a_path)
                elif d.b_path:
                    files_changed.append(d.b_path)
        else:
            # Root commit: all files
            files_changed = list(commit.stats.files.keys())

        commit_dt = datetime.fromtimestamp(commit.committed_date, tz=timezone.utc)
        versions.append({
            "git_hash": commit.hexsha,
            "short_hash": commit.hexsha[:7],
            "message": commit.message.strip(),
            "author": f"{commit.author.name} <{commit.author.email}>",
            "created_at": commit_dt.isoformat(),
            "files_changed": sorted(list(set(files_changed))),
        })

    return versions


def get_diff(commit_a: str, commit_b: Optional[str] = None, workspace_dir: Optional[str] = None) -> str:
    """
    Return unified diff between commit_a and commit_b.
    If commit_b is omitted, returns the diff of commit_a relative to its parent.
    """
    repo = init_repo(workspace_dir)
    try:
        if commit_b is None:
            commit_obj = repo.commit(commit_a)
            if commit_obj.parents:
                return repo.git.diff(commit_obj.parents[0].hexsha, commit_a)
            else:
                return repo.git.show(commit_a)
        diff_text = repo.git.diff(commit_a, commit_b)
        return diff_text
    except GitCommandError as e:
        return f"Error computing diff: {e}"


def get_file_at_version(
    git_hash: str,
    file_path: str,
    workspace_dir: Optional[str] = None,
) -> str:
    """
    Retrieve content of a file at a specific git commit without changing the working tree.
    """
    repo = init_repo(workspace_dir)
    try:
        commit = repo.commit(git_hash)
        # file_path should be relative to workspace repo root
        rel_path = file_path.replace("\\", "/").lstrip("/")
        blob = commit.tree / rel_path
        return blob.data_stream.read().decode("utf-8")
    except Exception as e:
        raise FileNotFoundError(f"File '{file_path}' not found at version {git_hash}: {e}")


def checkout_version(git_hash: str, workspace_dir: Optional[str] = None):
    """
    Check out a specific git version into the workspace.
    """
    repo = init_repo(workspace_dir)
    repo.git.checkout(git_hash)


def revert_commit(
    git_hash: str,
    message: Optional[str] = None,
    author_name: str = "Regression Manager",
    workspace_dir: Optional[str] = None,
) -> str:
    """
    Revert the specified commit using Git revert, preserving non-destructive history.
    Returns the new revert commit hash.
    """
    repo = init_repo(workspace_dir)
    actor = git.Actor(author_name, "regression@local.test")

    commit_to_revert = repo.commit(git_hash)
    default_msg = f"Revert '{commit_to_revert.message.strip()}' (hash: {git_hash[:7]})"
    commit_msg = message or default_msg

    try:
        repo.git.revert(git_hash, no_commit=True)
    except GitCommandError:
        # Fallback: checkout file contents from parent commit and stage
        if commit_to_revert.parents:
            parent = commit_to_revert.parents[0]
            diffs = parent.diff(commit_to_revert)
            for d in diffs:
                target_path = d.b_path or d.a_path
                try:
                    repo.git.checkout(parent.hexsha, "--", target_path)
                except Exception:
                    pass
        else:
            raise

    revert_commit_obj = repo.index.commit(commit_msg, author=actor, committer=actor)
    return revert_commit_obj.hexsha


def restore_file_from_version(
    git_hash: str,
    file_path: str,
    workspace_dir: Optional[str] = None,
):
    """
    Restore a single file to its state at git_hash in the working tree.
    Used for ablation testing.
    """
    repo = init_repo(workspace_dir)
    repo.git.checkout(git_hash, "--", file_path)


def sync_repo_to_db(workspace_dir: Optional[str] = None):
    """
    Synchronize all git commits and prompt/skill artifacts into the database.
    """
    ws = Path(workspace_dir) if workspace_dir else get_workspace_path()
    versions_data = list_versions(workspace_dir=str(ws))

    with get_session() as session:
        # Sync versions
        for v in versions_data:
            existing = session.query(Version).filter_by(git_hash=v["git_hash"]).first()
            if not existing:
                created_dt = datetime.fromisoformat(v["created_at"])
                ver = Version(
                    git_hash=v["git_hash"],
                    message=v["message"],
                    author=v["author"],
                    created_at=created_dt,
                    files_changed=v["files_changed"],
                )
                session.add(ver)

        # Sync artifacts (prompts and skills)
        prompt_dir = ws / "prompts"
        if prompt_dir.exists():
            for p in prompt_dir.glob("*.md"):
                rel = str(p.relative_to(ws))
                name = p.stem
                if not session.query(Artifact).filter_by(path=rel).first():
                    import hashlib
                    file_hash = hashlib.sha256(p.read_bytes()).hexdigest()
                    session.add(Artifact(hash=file_hash, type="prompt", name=name, path=rel))

        skills_dir = ws / "skills"
        if skills_dir.exists():
            for s in skills_dir.iterdir():
                skill_file = s / "SKILL.md"
                if s.is_dir() and skill_file.exists():
                    rel = str(skill_file.relative_to(ws))
                    name = s.name
                    if not session.query(Artifact).filter_by(path=rel).first():
                        import hashlib
                        file_hash = hashlib.sha256(skill_file.read_bytes()).hexdigest()
                        session.add(Artifact(hash=file_hash, type="skill", name=name, path=rel))

