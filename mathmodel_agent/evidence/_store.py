"""Small file-backed records shared by the evidence domain modules."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import re

from mathmodel_agent.contracts import read_json, write_json


REGISTRY_PATH = Path("knowledge") / "registry.json"


def now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def case_path(case_root: str | Path) -> Path:
    return Path(case_root).expanduser().resolve()


def registry_path(case_root: str | Path) -> Path:
    return case_path(case_root) / REGISTRY_PATH


def empty_registry() -> dict:
    return {
        "revision": 0,
        "sources": {},
        "datasets": {},
        "claims": {},
        "consumers": {},
        "batches": {},
        "errors": {},
    }


def load_registry(case_root: str | Path) -> dict:
    path = registry_path(case_root)
    if not path.exists():
        return empty_registry()
    registry = read_json(path)
    for key, default in empty_registry().items():
        registry.setdefault(key, default)
    return registry


def save_registry(case_root: str | Path, registry: dict) -> None:
    registry["revision"] = int(registry.get("revision", 0)) + 1
    registry["updated_at"] = now()
    write_json(registry_path(case_root), registry)


def slug(value: str, *, fallback: str = "item") -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return normalized or fallback


def require_local_path(case_root: str | Path, path: str | Path) -> Path:
    root = case_path(case_root)
    candidate = Path(path).expanduser().resolve()
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise ValueError(f"path must be inside case root: {candidate}") from error
    return candidate


def relative_to_case(case_root: str | Path, path: str | Path) -> str:
    return str(Path(path).resolve().relative_to(case_path(case_root)))
