"""Readable exploration records and the small structured contracts execution actually needs."""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any, Mapping

from .contracts import sha256_file, write_json


_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}\Z")


class ExplorationError(ValueError):
    pass


def write_candidate(
    case_root: str | Path,
    candidate_id: str,
    *,
    name: str,
    subproblem: str,
    origin: str,
    mathematical_structure: str,
    derivation: str,
    pseudocode: str,
    sources: list[str],
    assumptions: str,
    limitations: str,
    structural_difference: str,
    parents: list[str] | None = None,
) -> dict[str, Any]:
    """Write one mathematical route. A fusion is deliberately another Candidate."""
    root = Path(case_root).resolve()
    _identifier(candidate_id, "candidate_id")
    fields = {
        "name": name, "subproblem": subproblem, "origin": origin,
        "mathematical_structure": mathematical_structure, "derivation": derivation,
        "pseudocode": pseudocode, "assumptions": assumptions, "limitations": limitations,
        "structural_difference": structural_difference,
    }
    if not all(isinstance(value, str) and value.strip() for value in fields.values()):
        raise ExplorationError("candidate narrative fields must be non-empty text")
    if not isinstance(sources, list) or not all(isinstance(item, str) and item for item in sources):
        raise ExplorationError("sources must be a text list")
    parent_ids = list(parents or [])
    if not all(isinstance(item, str) and _ID.fullmatch(item) for item in parent_ids):
        raise ExplorationError("parents must be candidate IDs")
    candidates = root / "candidates"
    candidates.mkdir(parents=True, exist_ok=True)
    markdown = candidates / f"{candidate_id}.md"
    if markdown.exists():
        raise ExplorationError(f"candidate already exists: {candidate_id}")
    record = {
        "schema_version": "candidate-v1", "candidate_id": candidate_id, "parents": parent_ids,
        "variants": [], "validity": "unreviewed", **fields, "sources": sources,
    }
    markdown.write_text(_render_candidate(record), encoding="utf-8")
    write_json(candidates / f"{candidate_id}.json", record | {"markdown_ref": candidate_ref(root, candidate_id)})
    return record | {"markdown_ref": candidate_ref(root, candidate_id)}


def write_variant(
    case_root: str | Path,
    candidate_id: str,
    variant_id: str,
    *,
    implementation_difference: str,
    configuration_difference: str,
    purpose: str,
) -> dict[str, Any]:
    """Record implementation/configuration variation without duplicating a Candidate schema."""
    root = Path(case_root).resolve()
    _candidate_record(root, candidate_id)
    _identifier(variant_id, "variant_id")
    values = (implementation_difference, configuration_difference, purpose)
    if not all(isinstance(value, str) and value.strip() for value in values):
        raise ExplorationError("variant fields must be non-empty text")
    path = root / "candidates" / f"{candidate_id}.{variant_id}.variant.md"
    if path.exists():
        raise ExplorationError(f"variant already exists: {variant_id}")
    record = {
        "schema_version": "variant-v1", "variant_id": variant_id, "candidate_id": candidate_id,
        "implementation_difference": implementation_difference.strip(),
        "configuration_difference": configuration_difference.strip(), "purpose": purpose.strip(),
    }
    path.write_text(
        f"# Variant {variant_id}: {candidate_id}\n\n"
        f"## Purpose\n\n{record['purpose']}\n\n"
        f"## Implementation Difference\n\n{record['implementation_difference']}\n\n"
        f"## Configuration Difference\n\n{record['configuration_difference']}\n",
        encoding="utf-8",
    )
    write_json(path.with_suffix(".json"), record)
    return record


def candidate_ref(case_root: str | Path, candidate_id: str) -> dict[str, str]:
    root = Path(case_root).resolve()
    path = root / "candidates" / f"{candidate_id}.md"
    if not path.is_file():
        raise ExplorationError(f"candidate is missing: {candidate_id}")
    return {"path": path.relative_to(root).as_posix(), "sha256": sha256_file(path)}


def create_comparison_contract(
    case_root: str | Path,
    contract_id: str,
    *,
    candidates: list[str],
    data: Mapping[str, Any],
    split: Mapping[str, Any],
    planned_instances: list[Mapping[str, Any]],
    metrics: list[Mapping[str, Any]],
    constraints: list[Mapping[str, Any]],
    baseline: str,
    budget: Mapping[str, Any],
    failure_denominator: str,
    stopping_condition: str,
) -> dict[str, Any]:
    """Freeze comparison inputs before formal scoring, including fairness and failure semantics."""
    root = Path(case_root).resolve()
    _identifier(contract_id, "contract_id")
    if not candidates or not all(isinstance(item, str) and _ID.fullmatch(item) for item in candidates):
        raise ExplorationError("candidates must be a non-empty candidate ID list")
    if len(set(candidates)) != len(candidates):
        raise ExplorationError("comparison candidates must be unique")
    candidate_refs = {item: candidate_ref(root, item) for item in candidates}
    if not isinstance(data, Mapping) or not data or not isinstance(split, Mapping) or not split:
        raise ExplorationError("data and split must be non-empty mappings")
    if not isinstance(planned_instances, list) or not planned_instances:
        raise ExplorationError("planned_instances must be non-empty")
    if not isinstance(metrics, list) or not metrics:
        raise ExplorationError("metrics must be non-empty")
    for metric in metrics:
        if not isinstance(metric, Mapping) or not all(isinstance(metric.get(key), str) and metric[key] for key in ("name", "field", "unit")):
            raise ExplorationError("each metric needs name, field, and unit")
    if not isinstance(constraints, list) or not isinstance(budget, Mapping) or not budget:
        raise ExplorationError("constraints must be a list and budget must be non-empty")
    if not all(isinstance(item, str) and item.strip() for item in (baseline, failure_denominator, stopping_condition)):
        raise ExplorationError("baseline, failure_denominator, and stopping_condition must be text")
    contract = {
        "schema_version": "comparison-contract-v1", "contract_id": contract_id,
        "candidate_refs": candidate_refs, "data": dict(data), "split": dict(split),
        "planned_instances": [dict(item) for item in planned_instances],
        "metrics": [dict(item) for item in metrics], "constraints": [dict(item) for item in constraints],
        "baseline": baseline.strip(), "budget": dict(budget),
        "failure_denominator": failure_denominator.strip(), "stopping_condition": stopping_condition.strip(),
    }
    destination = root / "comparisons" / f"{contract_id}.json"
    if destination.exists():
        raise ExplorationError(f"comparison contract already exists: {contract_id}")
    write_json(destination, contract)
    return contract | {"path": destination.relative_to(root).as_posix(), "sha256": sha256_file(destination)}


def write_comparison_pack(
    case_root: str | Path,
    pack_id: str,
    *,
    contract_id: str,
    evidence: list[Mapping[str, Any]],
    recommendation: str,
    decision_readiness: str,
) -> dict[str, Any]:
    """Create a human-readable comparison without inventing aggregate scores or benchmarks."""
    root = Path(case_root).resolve()
    _identifier(pack_id, "pack_id")
    contract = root / "comparisons" / f"{contract_id}.json"
    if not contract.is_file():
        raise ExplorationError("comparison contract is missing")
    if not isinstance(evidence, list) or not evidence:
        raise ExplorationError("comparison evidence must be non-empty")
    normalized = []
    for entry in evidence:
        required = ("candidate_id", "status", "evidence", "uncertainty", "tradeoffs")
        if not isinstance(entry, Mapping) or not all(isinstance(entry.get(key), str) and entry[key].strip() for key in required):
            raise ExplorationError("each comparison entry needs candidate_id, status, evidence, uncertainty, and tradeoffs")
        _candidate_record(root, entry["candidate_id"])
        normalized.append({key: entry[key].strip() for key in required})
    if not isinstance(recommendation, str) or not recommendation.strip() or not isinstance(decision_readiness, str) or not decision_readiness.strip():
        raise ExplorationError("recommendation and decision_readiness must be non-empty text")
    path = root / "comparisons" / f"{pack_id}.md"
    if path.exists():
        raise ExplorationError(f"comparison pack already exists: {pack_id}")
    lines = [f"# Comparison Pack {pack_id}", "", f"**Contract:** `{contract.relative_to(root).as_posix()}`", ""]
    for entry in normalized:
        candidate = _candidate_record(root, entry["candidate_id"])
        lines.extend([
            f"## {entry['candidate_id']}: {candidate['name']}", "", f"**Outcome:** {entry['status']}", "",
            f"**Evidence:** {entry['evidence']}", "", f"**Uncertainty:** {entry['uncertainty']}", "",
            f"**Tradeoffs:** {entry['tradeoffs']}", "",
        ])
    lines.extend(["## Recommendation", "", recommendation.strip(), "", "## Decision Readiness", "", decision_readiness.strip(), ""])
    path.write_text("\n".join(lines), encoding="utf-8")
    record = {
        "schema_version": "comparison-pack-v1", "pack_id": pack_id,
        "contract_ref": {"path": contract.relative_to(root).as_posix(), "sha256": sha256_file(contract)},
        "evidence": normalized, "recommendation": recommendation.strip(), "decision_readiness": decision_readiness.strip(),
        "path": path.relative_to(root).as_posix(), "sha256": sha256_file(path),
    }
    write_json(root / "comparisons" / f"{pack_id}.json", record)
    return record


def _candidate_record(root: Path, candidate_id: str) -> dict[str, Any]:
    path = root / "candidates" / f"{candidate_id}.json"
    if not path.is_file():
        raise ExplorationError(f"candidate is missing: {candidate_id}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != "candidate-v1":
        raise ExplorationError(f"candidate metadata is invalid: {candidate_id}")
    return value


def _identifier(value: object, label: str) -> None:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ExplorationError(f"{label} is invalid")


def _render_candidate(record: Mapping[str, Any]) -> str:
    sources = "\n".join(f"- {item}" for item in record["sources"]) or "- No source registered yet."
    parents = ", ".join(record["parents"]) or "None"
    return (
        f"# Candidate {record['candidate_id']}: {record['name']}\n\n"
        f"**Origin:** {record['origin']}  \n**Subproblem:** {record['subproblem']}  \n**Parent candidates:** {parents}\n\n"
        f"## Mathematical Structure\n\n{record['mathematical_structure']}\n\n"
        f"## Derivation\n\n{record['derivation']}\n\n"
        f"## Pseudocode\n\n```text\n{record['pseudocode']}\n```\n\n"
        f"## Sources\n\n{sources}\n\n"
        f"## Assumptions\n\n{record['assumptions']}\n\n"
        f"## Limitations And Uncertainty\n\n{record['limitations']}\n\n"
        f"## Structural Difference\n\n{record['structural_difference']}\n"
    )
