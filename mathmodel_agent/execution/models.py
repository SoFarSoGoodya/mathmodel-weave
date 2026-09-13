"""Small, explicit execution-record validation helpers."""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any, Mapping

from mathmodel_agent.contracts import sha256_file


RUN_ID = re.compile(r"XR-[A-Za-z0-9][A-Za-z0-9._-]{0,79}\Z")
OUTCOMES = {"complete", "partial", "invalid", "not_run", "unknown"}
CLASSES = {"prototype", "formal", "recompute"}


class ExperimentValidationError(ValueError):
    pass


def require_case_file(case_root: Path, value: object, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ExperimentValidationError(f"{label} must be a non-empty case-relative path")
    path = case_root / value
    if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(case_root):
        raise ExperimentValidationError(f"{label} is missing, unsafe, or outside the case: {value}")
    return path.resolve()


def file_ref(case_root: Path, value: str, label: str) -> dict[str, str]:
    path = require_case_file(case_root, value, label)
    return {"path": path.relative_to(case_root).as_posix(), "sha256": sha256_file(path)}


def validate_artifact_ref(value: object, label: str) -> dict[str, str]:
    if not isinstance(value, Mapping) or set(value) != {"artifact_id", "sha256"}:
        raise ExperimentValidationError(f"{label} must be an ArtifactRef")
    artifact_id, digest = value["artifact_id"], value["sha256"]
    if not isinstance(artifact_id, str) or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ExperimentValidationError(f"{label} is invalid")
    return {"artifact_id": artifact_id, "sha256": digest}


def load_contract(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ExperimentValidationError(f"comparison contract is not valid JSON: {path}") from exc
    if not isinstance(value, dict) or not isinstance(value.get("metrics"), list) or not value["metrics"]:
        raise ExperimentValidationError("comparison contract needs a non-empty metrics list")
    for metric in value["metrics"]:
        if not isinstance(metric, dict) or not all(isinstance(metric.get(key), str) and metric[key] for key in ("name", "field", "unit")):
            raise ExperimentValidationError("each metric needs name, field, and unit")
        if metric.get("aggregation", "mean") not in {"mean", "max"}:
            raise ExperimentValidationError("metric aggregation must be mean or max")
    if not isinstance(value.get("constraints", []), list):
        raise ExperimentValidationError("comparison contract constraints must be a list")
    return value


def validate_manifest(manifest: Mapping[str, Any]) -> None:
    if manifest.get("schema_version") != "execution-run-v1":
        raise ExperimentValidationError("unsupported execution manifest version")
    if not isinstance(manifest.get("experiment_run_id"), str) or not RUN_ID.fullmatch(manifest["experiment_run_id"]):
        raise ExperimentValidationError("manifest experiment_run_id is invalid")
    if manifest.get("class") not in CLASSES:
        raise ExperimentValidationError("manifest class is invalid")
    if manifest.get("outcome") not in OUTCOMES:
        raise ExperimentValidationError("manifest outcome is invalid")
    if not isinstance(manifest.get("instances"), list) or not isinstance(manifest.get("metrics"), list):
        raise ExperimentValidationError("manifest instances and metrics must be lists")


def validate_result(result: Mapping[str, Any]) -> None:
    if result.get("outcome") not in OUTCOMES:
        raise ExperimentValidationError("result outcome is invalid")
    if not isinstance(result.get("coverage"), dict) or not isinstance(result.get("issues"), list):
        raise ExperimentValidationError("result coverage and issues are required")
