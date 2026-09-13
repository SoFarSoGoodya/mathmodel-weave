"""Versioned sources, datasets, claims, navigation, and consumer pins."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
import hashlib
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from mathmodel_agent.contracts import sha256_file

from ._store import case_path, load_registry, now, relative_to_case, save_registry, slug


def _canonical_url(value: str | None) -> str | None:
    if not value:
        return None
    parts = urlsplit(value.strip())
    if not parts.scheme or not parts.netloc:
        raise ValueError("canonical_url must be an absolute URL")
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, parts.query, ""))


def _doi(value: str | None) -> str | None:
    if not value:
        return None
    return value.strip().lower().removeprefix("https://doi.org/").removeprefix("doi:")


def _content_bytes(text: str | None, document_path: str | Path | None) -> bytes:
    if text is not None and document_path is not None:
        raise ValueError("provide text or document_path, not both")
    if document_path is not None:
        return Path(document_path).read_bytes()
    if text is not None:
        return text.encode("utf-8")
    return b""


def _source_matches(record: Mapping, identities: set[str]) -> bool:
    return bool(set(record.get("identities", [])) & identities)


def _citation_key(source_id: str, citation: Mapping | None) -> str:
    citation = citation or {}
    author = str(citation.get("author") or citation.get("authors") or "source")
    author = author.split(",")[0].split()[0]
    year = str(citation.get("year") or "nd")
    stem = slug(f"{author}{year}", fallback="source")
    return f"{stem}-{source_id.rsplit('-', 1)[-1]}"


def register_source(
    case_root: str | Path,
    title: str,
    *,
    text: str | None = None,
    document_path: str | Path | None = None,
    doi: str | None = None,
    canonical_url: str | None = None,
    citation: Mapping | None = None,
    access_scope: str = "full_text",
    provenance: str | None = None,
    source_id: str | None = None,
) -> dict:
    """Add a source version, deduplicating only DOI, canonical URL, or content hash."""
    if not title.strip():
        raise ValueError("title is required")
    body = _content_bytes(text, document_path)
    body_hash = hashlib.sha256(body).hexdigest()
    normalized_doi, normalized_url = _doi(doi), _canonical_url(canonical_url)
    identities = {f"hash:{body_hash}"} if body else set()
    if normalized_doi:
        identities.add(f"doi:{normalized_doi}")
    if normalized_url:
        identities.add(f"url:{normalized_url}")
    if not identities:
        raise ValueError("source needs text, document_path, DOI, or canonical_url")

    registry = load_registry(case_root)
    matches = [record for record in registry["sources"].values() if _source_matches(record, identities)]
    if len(matches) > 1:
        raise ValueError("identities match multiple sources; curate the conflict explicitly")
    if matches:
        record = matches[0]
        source_id = record["source_id"]
    else:
        source_id = source_id or f"src-{hashlib.sha256(sorted(identities)[0].encode()).hexdigest()[:12]}"
        if source_id in registry["sources"]:
            raise ValueError(f"source_id already exists: {source_id}")
        record = {
            "source_id": source_id,
            "title": title,
            "identities": [],
            "citekey": _citation_key(source_id, citation),
            "citation": dict(citation or {}),
            "versions": [],
            "created_at": now(),
        }
        registry["sources"][source_id] = record

    record["title"] = title
    record["identities"] = sorted(set(record.get("identities", [])) | identities)
    if citation:
        record["citation"] = dict(citation)
    if body_hash and not any(v["sha256"] == body_hash for v in record["versions"]):
        version_id = f"v{len(record['versions']) + 1}"
        root = case_path(case_root)
        raw_destination = root / "sources" / "raw" / source_id / f"{version_id}.txt"
        destination = root / "sources" / "processed" / source_id / version_id / "document.md"
        raw_destination.parent.mkdir(parents=True, exist_ok=True)
        destination.parent.mkdir(parents=True, exist_ok=True)
        raw_destination.write_bytes(body)
        destination.write_bytes(body)
        record["versions"].append(
            {
                "version_id": version_id,
                "sha256": body_hash,
                "raw": relative_to_case(case_root, raw_destination),
                "document": relative_to_case(case_root, destination),
                "access_scope": access_scope,
                "provenance": provenance or (str(document_path) if document_path else "provided text"),
                "created_at": now(),
            }
        )
    if record["versions"]:
        record["current_version"] = record["versions"][-1]["version_id"]
    record["updated_at"] = now()
    save_registry(case_root, registry)
    return dict(record)


def write_source_notes(
    case_root: str | Path,
    source_id: str,
    notes: str,
    *,
    purpose: str | None = None,
    limitations: str | None = None,
) -> Path:
    registry = load_registry(case_root)
    if source_id not in registry["sources"]:
        raise KeyError(source_id)
    path = case_path(case_root) / "sources" / "notes" / f"{source_id}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"# {registry['sources'][source_id]['title']}", "", notes.strip()]
    if purpose:
        lines.extend(["", f"## Purpose\n\n{purpose.strip()}"])
    if limitations:
        lines.extend(["", f"## Limits\n\n{limitations.strip()}"])
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    registry["sources"][source_id]["notes"] = relative_to_case(case_root, path)
    save_registry(case_root, registry)
    return path


def register_dataset(
    case_root: str | Path,
    dataset_id: str,
    *,
    raw_path: str | Path,
    profile_path: str | Path,
    derived_paths: Iterable[str | Path] = (),
    kind: str = "xlsx",
) -> dict:
    registry = load_registry(case_root)
    raw, profile = Path(raw_path), Path(profile_path)
    record = registry["datasets"].setdefault(dataset_id, {"dataset_id": dataset_id, "versions": []})
    fingerprint = hashlib.sha256((sha256_file(raw) + sha256_file(profile)).encode()).hexdigest()
    if not any(version["sha256"] == fingerprint for version in record["versions"]):
        record["versions"].append(
            {
                "version_id": f"v{len(record['versions']) + 1}",
                "sha256": fingerprint,
                "kind": kind,
                "raw": relative_to_case(case_root, raw),
                "profile": relative_to_case(case_root, profile),
                "derived": [relative_to_case(case_root, item) for item in derived_paths],
                "created_at": now(),
            }
        )
    record["current_version"] = record["versions"][-1]["version_id"]
    save_registry(case_root, registry)
    return dict(record)


def curate_batch(case_root: str | Path, batch_id: str, entries: Iterable[Mapping]) -> dict:
    records = [register_source(case_root, **dict(entry)) for entry in entries]
    registry = load_registry(case_root)
    registry["batches"][batch_id] = {
        "batch_id": batch_id,
        "source_ids": [record["source_id"] for record in records],
        "created_at": now(),
    }
    save_registry(case_root, registry)
    return dict(registry["batches"][batch_id])


def register_claim(
    case_root: str | Path,
    statement: str,
    *,
    evidence_kind: str,
    evidence_id: str,
    locator: str,
    scope: str | None = None,
    status: str = "supported",
    claim_id: str | None = None,
) -> dict:
    if evidence_kind not in {"source", "dataset", "artifact"}:
        raise ValueError("evidence_kind must be source, dataset, or artifact")
    if not statement.strip() or not locator.strip():
        raise ValueError("statement and locator are required")
    registry = load_registry(case_root)
    if evidence_kind in {"source", "dataset"} and evidence_id not in registry[f"{evidence_kind}s"]:
        raise KeyError(evidence_id)
    claim_id = claim_id or f"claim-{hashlib.sha256((statement + evidence_id + locator).encode()).hexdigest()[:12]}"
    record = {
        "claim_id": claim_id,
        "statement": statement,
        "evidence_kind": evidence_kind,
        "evidence_id": evidence_id,
        "locator": locator,
        "scope": scope,
        "status": status,
        "created_at": now(),
    }
    registry["claims"][claim_id] = record
    save_registry(case_root, registry)
    return dict(record)


def write_topic(
    case_root: str | Path,
    topic: str,
    summary: str,
    *,
    source_ids: Iterable[str] = (),
    claim_ids: Iterable[str] = (),
    disagreements: str | None = None,
) -> Path:
    registry = load_registry(case_root)
    source_ids, claim_ids = list(source_ids), list(claim_ids)
    unknown = set(source_ids) - set(registry["sources"]) | set(claim_ids) - set(registry["claims"])
    if unknown:
        raise KeyError(", ".join(sorted(unknown)))
    path = case_path(case_root) / "knowledge" / "topics" / f"{slug(topic)}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"# {topic}", "", summary.strip(), "", "## Navigation"]
    lines.extend(f"- Source `{item}`" for item in source_ids)
    lines.extend(f"- Claim `{item}`" for item in claim_ids)
    if disagreements:
        lines.extend(["", "## Open disagreement", "", disagreements.strip()])
    lines.extend(["", "This page is navigation, not evidence; follow the listed fixed records."])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _version_ref(record: Mapping) -> dict:
    version = next(item for item in record["versions"] if item["version_id"] == record["current_version"])
    return {"id": record.get("source_id", record.get("dataset_id")), "version": version["version_id"], "sha256": version["sha256"]}


def pin_consumer(
    case_root: str | Path,
    consumer_id: str,
    *,
    source_ids: Iterable[str] = (),
    dataset_ids: Iterable[str] = (),
    claim_ids: Iterable[str] = (),
) -> dict:
    registry = load_registry(case_root)
    source_ids, dataset_ids, claim_ids = list(source_ids), list(dataset_ids), list(claim_ids)
    for collection, ids in (("sources", source_ids), ("datasets", dataset_ids), ("claims", claim_ids)):
        missing = set(ids) - set(registry[collection])
        if missing:
            raise KeyError(", ".join(sorted(missing)))
    pin = {
        "consumer_id": consumer_id,
        "sources": [_version_ref(registry["sources"][item]) for item in source_ids],
        "datasets": [_version_ref(registry["datasets"][item]) for item in dataset_ids],
        "claims": [{"id": item} for item in claim_ids],
        "status": "ready",
        "pinned_at": now(),
    }
    registry["consumers"][consumer_id] = pin
    save_registry(case_root, registry)
    return dict(pin)


def refresh_consumer(case_root: str | Path, consumer_id: str, *, source_ids: Iterable[str] = (), dataset_ids: Iterable[str] = ()) -> dict:
    registry = load_registry(case_root)
    if consumer_id not in registry["consumers"]:
        raise KeyError(consumer_id)
    current = registry["consumers"][consumer_id]
    selected_sources = list(source_ids) or [item["id"] for item in current["sources"]]
    selected_datasets = list(dataset_ids) or [item["id"] for item in current["datasets"]]
    return pin_consumer(case_root, consumer_id, source_ids=selected_sources, dataset_ids=selected_datasets, claim_ids=[item["id"] for item in current["claims"]])


def affected_references(case_root: str | Path, kind: str, record_id: str) -> dict:
    registry = load_registry(case_root)
    claims = [item["claim_id"] for item in registry["claims"].values() if item["evidence_kind"] == kind and item["evidence_id"] == record_id]
    consumers = [item["consumer_id"] for item in registry["consumers"].values() if any(ref["id"] == record_id for ref in item.get(f"{kind}s", [])) or any(ref["id"] in claims for ref in item["claims"])]
    freezes = []
    for path in (case_path(case_root) / "freezes").glob("*.json"):
        freeze = __import__("json").loads(path.read_text(encoding="utf-8"))
        if any(ref["id"] == record_id for ref in freeze.get(f"{kind}s", [])) or any(ref["id"] in claims for ref in freeze.get("claims", [])):
            freezes.append(freeze["freeze_id"])
    return {"claims": claims, "consumers": consumers, "freezes": freezes}


def report_error(case_root: str | Path, kind: str, record_id: str, description: str) -> dict:
    if kind not in {"source", "dataset"}:
        raise ValueError("kind must be source or dataset")
    registry = load_registry(case_root)
    if record_id not in registry[f"{kind}s"]:
        raise KeyError(record_id)
    affected = affected_references(case_root, kind, record_id)
    error_id = f"err-{hashlib.sha256((kind + record_id + description).encode()).hexdigest()[:12]}"
    registry["errors"][error_id] = {"error_id": error_id, "kind": kind, "record_id": record_id, "description": description, "affected": affected, "created_at": now()}
    for claim_id in affected["claims"]:
        registry["claims"][claim_id]["status"] = "needs_review"
    for consumer_id in affected["consumers"]:
        registry["consumers"][consumer_id]["status"] = "stale"
    save_registry(case_root, registry)
    # Import here to avoid the freeze module depending on registry mutation internals.
    from .freeze import mark_affected_freezes

    mark_affected_freezes(case_root, kind, record_id)
    return dict(registry["errors"][error_id])
