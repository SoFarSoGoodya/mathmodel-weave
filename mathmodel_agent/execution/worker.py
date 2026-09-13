"""Prepare, finalize, and publish an experiment around the existing runtime."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import shutil
import sys
import uuid
from typing import Any, Mapping

from mathmodel_agent.contracts import sha256_file, write_json
from mathmodel_agent.runtime.artifacts import publish_bundle
from mathmodel_agent.runtime.scheduler import Supervisor
from mathmodel_agent.runtime.state import State

from .checks import read_complete_observations, recompute_metrics, run_constraints
from .models import CLASSES, OUTCOMES, RUN_ID, ExperimentValidationError, file_ref, load_contract, require_case_file, validate_manifest, validate_result


PRODUCT_ROOT = Path(__file__).resolve().parents[2]


def prepare_experiment(case_root: str | Path, request: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a short request and return a JSON-compatible run specification.

    The caller may persist the returned dictionary, alter no request inputs, then pass it
    to :func:`submit_experiment`. This function never starts a process.
    """
    root = Path(case_root).resolve()
    raw = copy.deepcopy(dict(request))
    run_class = raw.get("class", "prototype")
    if run_class not in CLASSES:
        raise ExperimentValidationError("class must be prototype, formal, or recompute")
    run_id = raw.get("experiment_run_id") or f"XR-{uuid.uuid4().hex[:16]}"
    if not isinstance(run_id, str) or not RUN_ID.fullmatch(run_id):
        raise ExperimentValidationError("experiment_run_id must start with XR-")
    task_id = raw.get("task_id") or f"experiment-{run_id.lower()}"
    if not isinstance(task_id, str) or not task_id:
        raise ExperimentValidationError("task_id must be text")
    command = raw.get("command")
    if not isinstance(command, list) or not command or not all(isinstance(item, str) and item for item in command):
        raise ExperimentValidationError("command must be a non-empty argv string list")
    code = file_ref(root, raw.get("code"), "code")
    config = file_ref(root, raw.get("config"), "config")
    inputs = raw.get("inputs", [])
    if not isinstance(inputs, list):
        raise ExperimentValidationError("inputs must be a list")
    input_refs = []
    for entry in inputs:
        if not isinstance(entry, Mapping) or not isinstance(entry.get("id"), str):
            raise ExperimentValidationError("each input needs id and path")
        ref = file_ref(root, entry.get("path"), f"input {entry['id']}")
        ref["id"] = entry["id"]
        if any(item["id"] == ref["id"] for item in input_refs):
            raise ExperimentValidationError(f"duplicate input id: {ref['id']}")
        input_refs.append(ref)
    contract_ref = None
    contract = None
    if raw.get("comparison_contract") is not None:
        contract_ref = file_ref(root, raw["comparison_contract"], "comparison_contract")
        contract = load_contract(root / contract_ref["path"])
    if run_class == "formal" and contract is None:
        raise ExperimentValidationError("formal experiments require comparison_contract")
    instances = raw.get("instances", contract.get("planned_instances") if contract else [])
    if not isinstance(instances, list) or not instances:
        raise ExperimentValidationError("instances must be a non-empty list")
    normalized_instances = []
    for instance in instances:
        if not isinstance(instance, Mapping) or not isinstance(instance.get("id"), str):
            raise ExperimentValidationError("each instance needs an id")
        seed = instance.get("seed")
        if seed is not None and (not isinstance(seed, int) or isinstance(seed, bool)):
            raise ExperimentValidationError("instance seed must be an integer or null")
        normalized_instances.append({"id": instance["id"], "seed": seed})
    if len({item["id"] for item in normalized_instances}) != len(normalized_instances):
        raise ExperimentValidationError("instance ids must be unique")
    if contract is not None and "planned_instances" in contract:
        contract_ids = [item.get("id") for item in contract["planned_instances"] if isinstance(item, Mapping)]
        if contract_ids != [item["id"] for item in normalized_instances]:
            raise ExperimentValidationError("instances must exactly match comparison contract planned_instances")
    return {
        "schema_version": "execution-spec-v1", "experiment_run_id": run_id, "task_id": task_id,
        "class": run_class, "purpose": raw.get("purpose", "run mathematical experiment"),
        "command_template": command, "code": code, "config": config, "inputs": input_refs,
        "comparison_contract": contract_ref, "instances": normalized_instances,
        "timeout_seconds": raw.get("timeout_seconds", 7200), "submission_id": raw.get("submission_id", f"experiment-{run_id}"),
        "environment": {"uv_lock_sha256": sha256_file(PRODUCT_ROOT / "uv.lock"), "python": sys.version.split()[0], "platform": sys.platform},
    }


def submit_experiment(case_root: str | Path, prepared: Mapping[str, Any]) -> str:
    """Freeze the run spec and submit its one real command to ``State``."""
    root = Path(case_root).resolve()
    spec = copy.deepcopy(dict(prepared))
    if spec.get("schema_version") != "execution-spec-v1":
        raise ExperimentValidationError("prepared experiment spec is invalid")
    _verify_current_references(root, spec)
    run_id, task_id = spec["experiment_run_id"], spec["task_id"]
    source_paths = [spec["code"]["path"], spec["config"]["path"], *(item["path"] for item in spec["inputs"])]
    if spec.get("comparison_contract"):
        source_paths.append(spec["comparison_contract"]["path"])
    copies = {path: f"../input/inputs/{path}" for path in source_paths}
    command = [_expand_command_token(token, copies, spec) for token in spec["command_template"]]
    state = State(root)
    task_spec = {
        "task_id": task_id, "kind": "command", "argv": command, "purpose": spec["purpose"],
        "timeout_seconds": spec["timeout_seconds"], "inputs": source_paths, "execution": spec,
    }
    submitted = state.submit(task_spec)
    run_root = root / "tasks" / submitted / "workspace" / "experiments" / run_id
    run_root.mkdir(parents=True)
    shutil.copy2(PRODUCT_ROOT / "uv.lock", run_root / "uv.lock")
    write_json(run_root / "run_spec.json", spec | {"runtime_command": command})
    return submitted


def run_experiment(case_root: str | Path, request: Mapping[str, Any]) -> dict[str, Any]:
    """Synchronous convenience flow; execution still occurs solely under Supervisor."""
    prepared = prepare_experiment(case_root, request)
    submit_experiment(case_root, prepared)
    Supervisor(case_root).serve(stop_when_idle=True)
    return finalize_experiment(case_root, prepared["task_id"])


def finalize_experiment(case_root: str | Path, task_id: str) -> dict[str, Any]:
    """Build the one manifest from persisted process facts and publish its package."""
    root = Path(case_root).resolve()
    task = State(root).get_task(task_id)
    execution = task["spec"].get("execution")
    if not isinstance(execution, dict):
        raise ExperimentValidationError("task is not an execution task")
    run_id = execution["experiment_run_id"]
    run_root = Path(task["workspace"]) / "experiments" / run_id
    run_root.mkdir(parents=True, exist_ok=True)
    observations, issues = read_complete_observations(run_root / "observations.jsonl")
    planned = execution["instances"]
    instance_records = _instance_records(planned, observations, bool(task["runs"]))
    contract = _contract_from_task(root, task, execution)
    checks_root = run_root / "checks"
    checks_root.mkdir(exist_ok=True)
    metrics, metric_issues = recompute_metrics(observations, contract, run_root / "metrics.json") if contract else ([], [])
    issues.extend(metric_issues)
    checks = [{"kind": "input_reference", "method": "frozen task input hash", "status": "passed", "evidence": "run_spec.json"}]
    checks.append({"kind": "output_schema", "method": "complete JSONL records only", "status": "passed" if not issues else "warning", "evidence": "observations.jsonl"})
    if contract:
        metric_status = "passed" if not metric_issues else ("unknown" if not observations and task["runs"] else "not_run" if not observations else "failed")
        checks.append({"kind": "metric_recompute", "method": "deterministic recompute from observations", "status": metric_status, "evidence": "metrics.json"})
        checks.extend(run_constraints(observations, contract, checks_root))
    failed_checks = [item for item in checks if item["status"] == "failed"]
    outcome = _outcome(task, observations, planned, failed_checks)
    if failed_checks:
        issues.append("a required check failed")
    _snapshot_inputs(task, execution, run_root)
    figures = _read_figures(run_root, issues)
    runtime = _runtime_record(task)
    manifest = {
        "schema_version": "execution-run-v1", "experiment_run_id": run_id, "class": execution["class"],
        "experiment_request": {"task_id": task_id, "purpose": execution["purpose"]},
        "comparison_contract": execution.get("comparison_contract"), "runtime": runtime,
        "inputs": execution["inputs"], "code": f"code/{Path(execution['code']['path']).name}",
        "config": f"config/{Path(execution['config']['path']).name}",
        "environment": {"uv_lock": "uv.lock", **execution["environment"]}, "instances": instance_records,
        "observations": "observations.jsonl", "metrics": metrics, "figures": figures, "checks": checks,
        "usage": {"wall_seconds": _wall_seconds(runtime), "cost": "unknown", "external_calls": "unknown"},
        "outcome": outcome, "issues": issues,
    }
    validate_manifest(manifest)
    write_json(run_root / "run_manifest.json", manifest)
    receipt = publish_bundle(root, run_root, execution["submission_id"], task_id=task_id, runtime_run_id=runtime.get("runtime_run_id"))
    coverage = _coverage(instance_records)
    result = {
        "experiment_request_ref": {"task_id": task_id}, "run_manifest_refs": [receipt["artifact_ref"]],
        "receipt_refs": [receipt["receipt_id"]], "coverage": coverage, "outcome": outcome, "issues": issues,
    }
    validate_result(result)
    return result


def redraw_figure(run_directory: str | Path, display_config: Mapping[str, Any]) -> Path:
    """Render a display-only allocation redraw from saved figure data.

    This deliberately does not read or write ``metrics.json`` or the manifest. It is
    suitable for a publication-facing style variation before a package is frozen.
    """
    import csv
    import matplotlib.pyplot as plt

    run_root = Path(run_directory)
    data = run_root / "figures" / "values.csv"
    if not data.is_file():
        raise ExperimentValidationError("redraw requires figures/values.csv")
    with data.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    labels = [row["instance_id"] for row in rows]
    baseline = [float(row["baseline_value"]) for row in rows]
    alternative = [float(row["alternative_value"]) for row in rows]
    colors = display_config.get("colors", ["#4c78a8", "#f58518"])
    if not isinstance(colors, list) or len(colors) != 2 or not all(isinstance(color, str) for color in colors):
        raise ExperimentValidationError("redraw colors must contain two strings")
    output = run_root / "figures" / "display-redraw.png"
    write_json(run_root / "figures" / "display-redraw.json", dict(display_config))
    x = list(range(len(rows)))
    figure, axis = plt.subplots(figsize=(5, 3.2), layout="constrained")
    axis.bar([value - 0.2 for value in x], baseline, width=0.4, label="density-greedy", color=colors[0])
    axis.bar([value + 0.2 for value in x], alternative, width=0.4, label="exhaustive optimum", color=colors[1])
    axis.set_xticks(x, labels)
    axis.set_ylabel(str(display_config.get("ylabel", "value")))
    axis.set_title(str(display_config.get("title", "Synthetic allocation values")))
    axis.legend()
    figure.savefig(output, dpi=int(display_config.get("dpi", 160)))
    plt.close(figure)
    return output


def _verify_current_references(root: Path, spec: dict[str, Any]) -> None:
    for ref in [spec["code"], spec["config"], *spec["inputs"], *( [spec["comparison_contract"]] if spec.get("comparison_contract") else [])]:
        path = require_case_file(root, ref["path"], ref["path"])
        if sha256_file(path) != ref["sha256"]:
            raise ExperimentValidationError(f"input/reference changed after preparation: {ref['path']}")
    if sha256_file(PRODUCT_ROOT / "uv.lock") != spec["environment"]["uv_lock_sha256"]:
        raise ExperimentValidationError("uv.lock changed after preparation")


def _expand_command_token(token: str, copies: dict[str, str], spec: dict[str, Any]) -> str:
    if token == "{code}":
        return copies[spec["code"]["path"]]
    if token == "{config}":
        return copies[spec["config"]["path"]]
    if token == "{output_dir}":
        return f"experiments/{spec['experiment_run_id']}"
    if token.startswith("{input:") and token.endswith("}"):
        key = token[7:-1]
        for item in spec["inputs"]:
            if item["id"] == key:
                return copies[item["path"]]
        raise ExperimentValidationError(f"unknown command input placeholder: {key}")
    if token.startswith("{") and token.endswith("}"):
        raise ExperimentValidationError(f"unsupported command placeholder: {token}")
    return token


def _contract_from_task(root: Path, task: dict[str, Any], execution: dict[str, Any]) -> dict[str, Any] | None:
    ref = execution.get("comparison_contract")
    if not ref:
        return None
    path = root / "tasks" / task["task_id"] / "input" / "inputs" / ref["path"]
    return load_contract(path)


def _instance_records(planned: list[dict[str, Any]], observations: list[dict[str, Any]], started: bool) -> list[dict[str, Any]]:
    by_id = {item["instance_id"]: item for item in observations}
    records = []
    for item in planned:
        observed = by_id.get(item["id"])
        records.append({"id": item["id"], "seed": item["seed"], "status": observed["status"] if observed else ("unknown" if started else "not_run")})
    return records


def _outcome(task: dict[str, Any], observations: list[dict[str, Any]], planned: list[dict[str, Any]], failed_checks: list[dict[str, Any]]) -> str:
    if failed_checks:
        return "invalid"
    if not task["runs"]:
        return "not_run"
    completed = sum(item["status"] == "completed" for item in observations)
    if completed == len(planned) and task["state"] == "succeeded":
        return "complete"
    if observations:
        return "partial"
    return "unknown"


def _snapshot_inputs(task: dict[str, Any], execution: dict[str, Any], run_root: Path) -> None:
    task_root = Path(task["workspace"]).parent
    mappings = [(execution["code"], run_root / "code" / Path(execution["code"]["path"]).name), (execution["config"], run_root / "config" / Path(execution["config"]["path"]).name)]
    mappings.extend((item, run_root / "inputs" / item["id"] / Path(item["path"]).name) for item in execution["inputs"])
    if execution.get("comparison_contract"):
        mappings.append((execution["comparison_contract"], run_root / "contracts" / Path(execution["comparison_contract"]["path"]).name))
    for ref, destination in mappings:
        source = task_root / "input" / "inputs" / ref["path"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            shutil.copy2(source, destination)


def _read_figures(run_root: Path, issues: list[str]) -> list[dict[str, Any]]:
    index = run_root / "figures" / "figures.json"
    if not index.exists():
        return []
    try:
        entries = json.loads(index.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        issues.append("figure index is invalid")
        return []
    if not isinstance(entries, list):
        issues.append("figure index is not a list")
        return []
    figures = []
    for entry in entries:
        if not isinstance(entry, dict) or not all(isinstance(entry.get(key), str) for key in ("name", "image", "data", "plot_code", "display_config")):
            issues.append("ignored invalid figure entry")
            continue
        paths = [run_root / "figures" / entry[key] for key in ("image", "data", "plot_code", "display_config")]
        if not all(path.is_file() for path in paths):
            issues.append(f"ignored incomplete figure {entry['name']}")
            continue
        figures.append({"name": entry["name"], **{key: f"figures/{entry[key]}" for key in ("image", "data", "plot_code", "display_config")}})
    return figures


def _runtime_record(task: dict[str, Any]) -> dict[str, Any]:
    run = task["runs"][-1] if task["runs"] else {}
    return {"task_id": task["task_id"], "runtime_run_id": run.get("run_id"), "attempt_no": run.get("attempt_no"), "command": run.get("command", task["spec"].get("argv")), "exit_code": run.get("exit_code"), "started_at": run.get("started_at"), "ended_at": run.get("ended_at"), "task_state": task["state"]}


def _wall_seconds(runtime: dict[str, Any]) -> float | None:
    if isinstance(runtime.get("started_at"), (int, float)) and isinstance(runtime.get("ended_at"), (int, float)):
        return max(0.0, runtime["ended_at"] - runtime["started_at"])
    return None


def _coverage(instances: list[dict[str, Any]]) -> dict[str, int]:
    result: dict[str, int] = {"planned": len(instances)}
    for item in instances:
        result[item["status"]] = result.get(item["status"], 0) + 1
    return result
