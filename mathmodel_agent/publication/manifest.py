"""Deterministic publication views of an execution run manifest."""

from __future__ import annotations

import json
import re
from pathlib import Path

from mathmodel_agent.contracts import read_json, sha256_file

from .errors import PublicationError


def _load(value: str | Path | dict) -> dict:
    manifest = read_json(value) if isinstance(value, (str, Path)) else value
    if not isinstance(manifest, dict):
        raise PublicationError("run manifest must be a JSON object")
    return manifest


def _metric_macro(name: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", name)
    if not words:
        raise PublicationError(f"metric name cannot form a TeX macro: {name!r}")
    macro = "".join(word[:1].upper() + word[1:] for word in words)
    if macro[0].isdigit():
        macro = "Metric" + macro
    return macro


def _tex_escape(value: object) -> str:
    text = str(value)
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
    }
    return "".join(replacements.get(character, character) for character in text)


def _format_number(value: object) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PublicationError(f"metric value must be numeric, got {value!r}")
    return f"{value:.10g}"


def generate_results_tex(run_manifest: str | Path | dict, output_path: str | Path) -> dict:
    """Write stable metric macros and a table from one formal execution manifest."""
    manifest = _load(run_manifest)
    if manifest.get("schema_version") != "execution-run-v1":
        raise PublicationError("unsupported execution manifest schema")
    metrics = manifest.get("metrics")
    if not isinstance(metrics, list) or not metrics:
        raise PublicationError("run manifest has no metrics")

    lines = ["% Generated from run_manifest.json; do not edit by hand."]
    macro_values: dict[str, str] = {}
    table_rows: list[str] = []
    for metric in metrics:
        if not isinstance(metric, dict):
            raise PublicationError("metric entries must be objects")
        name = metric.get("name")
        unit = metric.get("unit")
        denominator = metric.get("denominator")
        definition = metric.get("definition")
        if not isinstance(name, str) or not isinstance(unit, str):
            raise PublicationError("metric name and unit must be text")
        if not isinstance(definition, dict) or definition.get("unit") != unit:
            raise PublicationError(f"metric definition/unit mismatch: {name}")
        if definition.get("name") != name:
            raise PublicationError(f"metric definition/name mismatch: {name}")
        if not isinstance(denominator, dict):
            raise PublicationError(f"metric denominator is missing: {name}")
        macro = _metric_macro(name)
        value = _format_number(metric.get("value"))
        macro_values[macro] = value
        lines.extend(
            [
                rf"\newcommand{{\{macro}}}{{{value}}}",
                rf"\newcommand{{\{macro}Unit}}{{{_tex_escape(unit)}}}",
                rf"\newcommand{{\{macro}Completed}}{{{int(denominator.get('completed', 0))}}}",
                rf"\newcommand{{\{macro}Failed}}{{{int(denominator.get('failed', 0))}}}",
                rf"\newcommand{{\{macro}Planned}}{{{int(denominator.get('planned', 0))}}}",
            ]
        )
        aggregation = _tex_escape(definition.get("aggregation", ""))
        table_rows.append(
            f"{_tex_escape(name)} & {value} & {_tex_escape(unit)} & {aggregation} & "
            f"{int(denominator.get('completed', 0))}/"
            f"{int(denominator.get('failed', 0))}/"
            f"{int(denominator.get('planned', 0))} \\\\"
        )

    outcome = str(manifest.get("outcome", "unknown"))
    completed = sum(item.get("status") == "completed" for item in manifest.get("instances", []))
    failed = sum(item.get("status") == "failed" for item in manifest.get("instances", []))
    planned = len(manifest.get("instances", []))
    lines.extend(
        [
            rf"\newcommand{{\ExperimentRunId}}{{{_tex_escape(manifest.get('experiment_run_id', ''))}}}",
            rf"\newcommand{{\RunOutcome}}{{{_tex_escape(outcome)}}}",
            rf"\newcommand{{\RunCompleted}}{{{completed}}}",
            rf"\newcommand{{\RunFailed}}{{{failed}}}",
            rf"\newcommand{{\RunPlanned}}{{{planned}}}",
            r"\newcommand{\GeneratedMetricRows}{%",
            *table_rows,
            "}",
        ]
    )
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "experiment_run_id": manifest.get("experiment_run_id"),
        "manifest_sha256": sha256_file(run_manifest) if isinstance(run_manifest, (str, Path)) else None,
        "macros": macro_values,
        "outcome": outcome,
        "coverage": {"completed": completed, "failed": failed, "planned": planned},
    }


def _science_projection(manifest: dict) -> dict:
    figures = []
    for figure in manifest.get("figures", []):
        figures.append(
            {
                "name": figure.get("name"),
                "data": figure.get("data"),
                "plot_code": figure.get("plot_code"),
            }
        )
    return {
        key: manifest.get(key)
        for key in (
            "schema_version",
            "class",
            "experiment_run_id",
            "comparison_contract",
            "code",
            "config",
            "inputs",
            "instances",
            "observations",
            "metrics",
            "checks",
            "outcome",
            "issues",
        )
    } | {"figures": figures}


def classify_manifest_change(original: str | Path | dict, candidate: str | Path | dict) -> str:
    """Classify a manifest edit without treating figure display metadata as science."""
    left = _science_projection(_load(original))
    right = _science_projection(_load(candidate))
    return "display_only" if left == right else "science_revision"


def canonical_manifest_json(run_manifest: str | Path | dict) -> str:
    """Return a stable representation useful in tests and build reports."""
    return json.dumps(_load(run_manifest), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
