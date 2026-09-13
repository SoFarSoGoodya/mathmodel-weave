"""Deterministic observation-based metrics and lightweight independent checks."""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
from typing import Any

from mathmodel_agent.contracts import write_json


def read_complete_observations(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    observations: list[dict[str, Any]] = []
    issues: list[str] = []
    if not path.exists():
        return observations, issues
    for number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            issues.append(f"ignored incomplete or invalid observation line {number}")
            continue
        if not isinstance(value, dict) or not isinstance(value.get("instance_id"), str) or value.get("status") not in {"completed", "failed", "timed_out"}:
            issues.append(f"ignored invalid observation record at line {number}")
            continue
        observations.append(value)
    return observations, issues


def recompute_metrics(observations: list[dict[str, Any]], contract: dict[str, Any], destination: Path) -> tuple[list[dict[str, Any]], list[str]]:
    metrics: list[dict[str, Any]] = []
    issues: list[str] = []
    completed = [item for item in observations if item["status"] == "completed"]
    denominator = dict(Counter(item["status"] for item in observations))
    denominator["planned"] = len(contract.get("planned_instances", []))
    for definition in contract["metrics"]:
        field = definition["field"]
        values = [item[field] for item in completed if isinstance(item.get(field), (int, float)) and not isinstance(item[field], bool)]
        if not values:
            issues.append(f"metric {definition['name']} has no completed numeric observations")
            value = None
        else:
            value = max(values) if definition.get("aggregation", "mean") == "max" else sum(values) / len(values)
        metrics.append({
            "name": definition["name"], "value": value, "unit": definition["unit"],
            "definition": definition, "source": "observations.jsonl",
            "raw_observation_count": len(values), "denominator": denominator,
        })
    write_json(destination, {"metrics": metrics, "method": "deterministic metric recompute from observations"})
    return metrics, issues


def run_constraints(observations: list[dict[str, Any]], contract: dict[str, Any], destination: Path) -> list[dict[str, Any]]:
    checks = []
    for definition in contract.get("constraints", []):
        name = definition.get("name", "constraint")
        left, operator, right = definition.get("left_field"), definition.get("operator"), definition.get("right_field")
        violations = []
        for observation in observations:
            if observation["status"] != "completed":
                continue
            left_value, right_value = observation.get(left), observation.get(right)
            valid = isinstance(left_value, (int, float)) and isinstance(right_value, (int, float)) and not isinstance(left_value, bool) and not isinstance(right_value, bool)
            passed = valid and ((operator == "<=" and left_value <= right_value) or (operator == ">=" and left_value >= right_value) or (operator == "==" and left_value == right_value))
            if not passed:
                violations.append({"instance_id": observation["instance_id"], "left": left_value, "right": right_value})
        evidence = destination / f"{name}.json"
        write_json(evidence, {"definition": definition, "violations": violations})
        checks.append({"kind": "independent_check", "method": "independent checker implementation", "name": name, "status": "passed" if not violations else "failed", "evidence": f"checks/{evidence.name}"})
    return checks
