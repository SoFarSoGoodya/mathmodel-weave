"""Adopted evidence snapshots and deterministic, limited bibliographies."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from mathmodel_agent.contracts import read_json, write_json

from ._store import case_path, load_registry, now
from .pool import affected_references


def _version_ref(record: dict) -> dict:
    version = next(item for item in record["versions"] if item["version_id"] == record["current_version"])
    return {"id": record.get("source_id", record.get("dataset_id")), "version": version["version_id"], "sha256": version["sha256"]}


def freeze_evidence(
    case_root: str | Path,
    freeze_id: str,
    *,
    consumer_id: str | None = None,
    source_ids: Iterable[str] = (),
    dataset_ids: Iterable[str] = (),
    claim_ids: Iterable[str] = (),
    result_refs: Iterable[dict] = (),
    rules_source_ids: Iterable[str] = (),
    problem_ref: dict | None = None,
) -> dict:
    """Freeze exactly the adopted subset; live pool additions do not alter it."""
    root, registry = case_path(case_root), load_registry(case_root)
    path = root / "freezes" / f"{freeze_id}.json"
    if path.exists():
        raise FileExistsError(f"freeze already exists: {freeze_id}")
    sources = list(source_ids)
    datasets = list(dataset_ids)
    claims = list(claim_ids)
    if consumer_id:
        consumer = registry["consumers"].get(consumer_id)
        if consumer is None:
            raise KeyError(consumer_id)
        sources = sources or [item["id"] for item in consumer["sources"]]
        datasets = datasets or [item["id"] for item in consumer["datasets"]]
        claims = claims or [item["id"] for item in consumer["claims"]]
    rules = list(rules_source_ids)
    for collection, ids in (("sources", sources + rules), ("datasets", datasets), ("claims", claims)):
        missing = set(ids) - set(registry[collection])
        if missing:
            raise KeyError(", ".join(sorted(missing)))
    for claim_id in claims:
        claim = registry["claims"][claim_id]
        if claim["status"] != "supported" or not claim["locator"]:
            raise ValueError(f"claim is not ready for freeze: {claim_id}")
    freeze = {
        "freeze_id": freeze_id,
        "created_at": now(),
        "consumer_id": consumer_id,
        "problem": problem_ref,
        "sources": [_version_ref(registry["sources"][item]) for item in sources],
        "rules_sources": [_version_ref(registry["sources"][item]) for item in rules],
        "datasets": [_version_ref(registry["datasets"][item]) for item in datasets],
        "claims": [{"id": item, "locator": registry["claims"][item]["locator"]} for item in claims],
        "result_refs": list(result_refs),
        "status": "ready",
    }
    write_json(path, freeze)
    return freeze


def _bib_escape(value: object) -> str:
    return str(value).replace("\\", "\\textbackslash{}").replace("{", "\\{").replace("}", "\\}")


def bibliography_for_freeze(case_root: str | Path, freeze_id: str, *, output_path: str | Path | None = None) -> Path:
    """Create a BibTeX file for sources actually frozen for this output."""
    root, registry = case_path(case_root), load_registry(case_root)
    freeze = read_json(root / "freezes" / f"{freeze_id}.json")
    source_ids = [item["id"] for item in freeze["sources"] + freeze.get("rules_sources", [])]
    lines: list[str] = []
    for source_id in sorted(set(source_ids), key=lambda item: registry["sources"][item]["citekey"]):
        record = registry["sources"][source_id]
        citation = record.get("citation", {})
        entry_type = citation.get("entry_type", "misc")
        fields = {"title": record["title"], **{key: value for key, value in citation.items() if key != "entry_type"}}
        doi = next((identity[4:] for identity in record["identities"] if identity.startswith("doi:")), None)
        url = next((identity[4:] for identity in record["identities"] if identity.startswith("url:")), None)
        if doi:
            fields.setdefault("doi", doi)
        if url:
            fields.setdefault("url", url)
        lines.append(f"@{entry_type}{{{record['citekey']},")
        lines.extend(f"  {key} = {{{_bib_escape(value)}}}," for key, value in sorted(fields.items()))
        lines.append("}\n")
    target = Path(output_path) if output_path else root / "freezes" / f"{freeze_id}.bib"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines), encoding="utf-8")
    return target


def mark_affected_freezes(case_root: str | Path, kind: str, record_id: str) -> dict:
    """Mark only freezes that contain an erroneous source or dataset for review."""
    root = case_path(case_root)
    affected = affected_references(root, kind, record_id)
    for freeze_id in affected["freezes"]:
        path = root / "freezes" / f"{freeze_id}.json"
        freeze = read_json(path)
        freeze["status"] = "needs_review"
        freeze.setdefault("issues", []).append({"kind": kind, "record_id": record_id, "marked_at": now()})
        write_json(path, freeze)
    return affected
