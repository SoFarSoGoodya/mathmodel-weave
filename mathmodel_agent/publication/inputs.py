"""Validate selected-result, freeze, rule, and manifest bindings."""

from __future__ import annotations

from pathlib import Path

from mathmodel_agent.contracts import read_json, sha256_file

from .errors import PublicationError, ScienceRevisionRequired


def case_file(case_root: str | Path, value: str | Path, *, directory: bool = False) -> Path:
    root = Path(case_root).resolve()
    path = Path(value)
    candidate = path.resolve() if path.is_absolute() else (root / path).resolve()
    if not candidate.is_relative_to(root):
        raise PublicationError(f"publication path escapes case root: {value}")
    if directory and not candidate.is_dir():
        raise PublicationError(f"publication directory is missing: {value}")
    if not directory and not candidate.is_file():
        raise PublicationError(f"publication file is missing: {value}")
    return candidate


def _ref_key(value: dict) -> tuple[str, str]:
    try:
        return str(value["experiment_run_id"]), str(value["manifest_sha256"])
    except (KeyError, TypeError) as exc:
        raise PublicationError("result ref must bind experiment_run_id and manifest_sha256") from exc


def validate_frozen_inputs(
    selected_path: str | Path,
    freeze_path: str | Path,
    manifest_path: str | Path,
    *,
    demonstration: bool,
) -> dict:
    selected = read_json(selected_path)
    freeze = read_json(freeze_path)
    manifest = read_json(manifest_path)
    if freeze.get("status") != "ready":
        raise ScienceRevisionRequired("evidence freeze is not ready")
    allowed = {"selected"}
    if demonstration:
        allowed.add("demo_fixture")
    if selected.get("status") not in allowed:
        raise ScienceRevisionRequired("selected result is not fixed for publication")
    if bool(selected.get("demonstration", False)) != demonstration:
        raise PublicationError("request and selected-result demonstration labels disagree")

    actual = (str(manifest.get("experiment_run_id")), sha256_file(manifest_path))
    selected_ref = _ref_key(selected.get("run_ref", {}))
    freeze_refs = {_ref_key(item) for item in freeze.get("result_refs", [])}
    if selected_ref != actual:
        raise ScienceRevisionRequired("selected result refers to a stale or different run manifest")
    if actual not in freeze_refs:
        raise ScienceRevisionRequired("evidence freeze does not contain the selected run manifest")
    if manifest.get("schema_version") != "execution-run-v1":
        raise PublicationError("unsupported execution manifest schema")
    return {"selected": selected, "freeze": freeze, "manifest": manifest, "manifest_sha256": actual[1]}
