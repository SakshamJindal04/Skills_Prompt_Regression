import hashlib
import json
from pathlib import Path
from core.db import get_session
from core.models import Artifact, BaselineRegistry


def hash_content(file_contents, model_id, params):
    hasher = hashlib.sha256()
    for path in sorted(file_contents.keys()):
        hasher.update(path.encode("utf-8"))
        hasher.update(b"::")
        hasher.update(file_contents[path].encode("utf-8"))
        hasher.update(b"\n")
    hasher.update(f"model:{model_id}".encode("utf-8"))
    sorted_params = json.dumps(params or {}, sort_keys=True)
    hasher.update(f"params:{sorted_params}".encode("utf-8"))
    return hasher.hexdigest()


def build_manifest(file_contents, model_id, params):
    manifest = {
        "files": {p: hashlib.sha256(c.encode("utf-8")).hexdigest() for p, c in file_contents.items()},
        "model_id": model_id,
        "params": params or {},
    }
    return manifest


def register_artifact(file_paths, model_id="qwen2.5:3b", params=None, artifact_type="prompt", name=None, workspace_dir=None):
    base = Path(workspace_dir) if workspace_dir else Path(__file__).resolve().parent.parent / "workspace"
    file_contents = {}

    for p in file_paths:
        full_p = base / p if not Path(p).is_absolute() else Path(p)
        if full_p.exists():
            rel_p = str(full_p.relative_to(base)) if full_p.is_relative_to(base) else str(full_p)
            file_contents[rel_p] = full_p.read_text(encoding="utf-8")

    params = params or {"temperature": 0.7}
    art_hash = hash_content(file_contents, model_id, params)
    manifest = build_manifest(file_contents, model_id, params)
    artifact_name = name or (Path(file_paths[0]).stem if file_paths else "artifact")
    primary_path = file_paths[0] if file_paths else ""

    with get_session() as session:
        existing = session.query(Artifact).filter_by(hash=art_hash).first()
        if existing:
            return existing.id, manifest

        artifact = Artifact(
            hash=art_hash,
            type=artifact_type,
            name=artifact_name,
            path=str(primary_path),
            manifest=manifest,
        )
        session.add(artifact)
        session.flush()
        art_id = artifact.id

    return art_id, manifest


def get_current_baseline():
    with get_session() as session:
        last = session.query(BaselineRegistry).order_by(BaselineRegistry.id.desc()).first()
        if last:
            art = session.query(Artifact).filter_by(id=last.artifact_id).first()
            return art.to_dict() if art else None
    return None


def set_current_baseline(artifact_id, notes=None, set_by="gate"):
    with get_session() as session:
        entry = BaselineRegistry(
            artifact_id=artifact_id,
            notes=notes,
            set_by=set_by,
        )
        session.add(entry)

