"""Single-path immutable bundle publication and verified ArtifactRef resolution."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import uuid

from mathmodel_agent.contracts import sha256_file, write_json

from .state import State
from .platform import is_link, publication_lock


SUBMISSION_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
RESERVED_NAMES = {"bundle.json"}


class ArtifactError(RuntimeError):
    pass


class SubmissionConflict(ArtifactError):
    pass


def publish_bundle(
    case_root: str | Path,
    staging: str | Path,
    submission_id: str,
    *,
    task_id: str | None = None,
    runtime_run_id: str | None = None,
) -> dict:
    state = State(case_root)
    root = state.case_root
    if not isinstance(submission_id, str) or not SUBMISSION_PATTERN.fullmatch(submission_id):
        raise ArtifactError("submission_id contains unsupported characters")
    source = _inside_existing(root, staging)
    if not source.is_dir() or is_link(source):
        raise ArtifactError("staging must be a real directory")

    artifacts_root = root / "artifacts"
    artifacts_root.mkdir(parents=True, exist_ok=True)
    lock_path = state.runtime_root / "publish.lock"
    with publication_lock(lock_path):
        existing = state.receipt(submission_id)
        snapshot, source_stats = _snapshot(source)
        content_id = _content_id(snapshot)
        if existing:
            if existing["content_id"] != content_id:
                raise SubmissionConflict(
                    f"submission {submission_id!r} already names different content"
                )
            resolve_bundle(root, existing["artifact_ref"], verify=True)
            return existing

        artifact_id = f"bundle-{content_id}"
        final = artifacts_root / artifact_id
        temporary = artifacts_root / f".publish-{uuid.uuid4().hex}"
        temporary.mkdir()
        try:
            copied = _copy_snapshot(source, temporary, snapshot, source_stats)
            if copied != snapshot:
                raise ArtifactError("staging changed while it was being published")
            manifest = {
                "schema_version": 1,
                "artifact_id": artifact_id,
                "content_id": content_id,
                "files": snapshot,
            }
            write_json(temporary / "bundle.json", manifest)
            manifest_hash = sha256_file(temporary / "bundle.json")
            if final.exists():
                _verify_directory(final, {"artifact_id": artifact_id, "sha256": manifest_hash})
                shutil.rmtree(temporary)
            else:
                os.replace(temporary, final)
            artifact_ref = {"artifact_id": artifact_id, "sha256": manifest_hash}
            receipt_seed = {
                "submission_id": submission_id,
                "content_id": content_id,
                "artifact_ref": artifact_ref,
                "task_id": task_id,
                "runtime_run_id": runtime_run_id,
            }
            receipt_id = hashlib.sha256(_canonical(receipt_seed)).hexdigest()
            receipt = receipt_seed | {"receipt_id": receipt_id}
            receipt_path = state.runtime_root / "receipts" / f"{submission_id}.json"
            write_json(receipt_path, receipt)
            state.record_receipt(submission_id, content_id, receipt)
            return receipt
        except BaseException:
            if temporary.exists():
                shutil.rmtree(temporary)
            raise


def resolve_bundle(case_root: str | Path, ref: dict, verify: bool = True) -> Path:
    root = Path(case_root).resolve()
    if not isinstance(ref, dict) or set(ref) != {"artifact_id", "sha256"}:
        raise ArtifactError("ArtifactRef must contain artifact_id and sha256")
    artifact_id = ref.get("artifact_id")
    expected_hash = ref.get("sha256")
    if not isinstance(artifact_id, str) or not artifact_id.startswith("bundle-"):
        raise ArtifactError("invalid artifact_id")
    if not isinstance(expected_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_hash):
        raise ArtifactError("invalid ArtifactRef sha256")
    path = (root / "artifacts" / artifact_id).resolve()
    artifacts = (root / "artifacts").resolve()
    if not path.is_relative_to(artifacts) or not path.is_dir() or is_link(path):
        raise ArtifactError("artifact does not exist inside this case")
    if verify:
        _verify_directory(path, ref)
    return path


def _snapshot(source: Path) -> tuple[list[dict], dict[Path, tuple[int, int, int]]]:
    before = _tree_stats(source)
    files = []
    for relative, metadata in before.items():
        if relative.name in RESERVED_NAMES or relative.name.endswith((".tmp", ".partial")):
            raise ArtifactError(f"reserved or incomplete staging file: {relative.as_posix()}")
        path = source / relative
        files.append(
            {
                "path": relative.as_posix(),
                "size": metadata[0],
                "sha256": sha256_file(path),
            }
        )
    after = _tree_stats(source)
    if before != after:
        raise ArtifactError("staging changed while it was being inspected")
    return sorted(files, key=lambda item: item["path"]), before


def _copy_snapshot(
    source: Path,
    destination: Path,
    expected: list[dict],
    expected_stats: dict[Path, tuple[int, int, int]],
) -> list[dict]:
    copied = []
    for item in expected:
        relative = Path(item["path"])
        source_file = source / relative
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        before = source_file.stat()
        digest = hashlib.sha256()
        size = 0
        with source_file.open("rb") as incoming, target.open("xb") as outgoing:
            for block in iter(lambda: incoming.read(1024 * 1024), b""):
                outgoing.write(block)
                digest.update(block)
                size += len(block)
            outgoing.flush()
            os.fsync(outgoing.fileno())
        after = source_file.stat()
        if _stat_identity(before) != _stat_identity(after):
            raise ArtifactError(f"staging file changed during copy: {relative.as_posix()}")
        copied.append({"path": relative.as_posix(), "size": size, "sha256": digest.hexdigest()})
    if _tree_stats(source) != expected_stats:
        raise ArtifactError("staging changed during copy")
    return copied


def _tree_stats(root: Path) -> dict[Path, tuple[int, int, int]]:
    result = {}
    for directory, names, filenames in os.walk(root, followlinks=False):
        directory_path = Path(directory)
        for name in names:
            path = directory_path / name
            if is_link(path):
                raise ArtifactError(f"staging contains symlink: {path.relative_to(root)}")
        for name in filenames:
            path = directory_path / name
            relative = path.relative_to(root)
            info = path.lstat()
            if stat.S_ISLNK(info.st_mode):
                raise ArtifactError(f"staging contains symlink: {relative}")
            if not stat.S_ISREG(info.st_mode):
                raise ArtifactError(f"staging contains non-regular file: {relative}")
            result[relative] = (info.st_size, info.st_mtime_ns, info.st_ino)
    return result


def _verify_directory(path: Path, ref: dict) -> None:
    manifest_path = path / "bundle.json"
    if not manifest_path.is_file() or is_link(manifest_path):
        raise ArtifactError("artifact manifest is missing or unsafe")
    if sha256_file(manifest_path) != ref["sha256"]:
        raise ArtifactError("artifact manifest hash does not match ArtifactRef")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise ArtifactError("artifact manifest is invalid JSON") from exc
    if manifest.get("artifact_id") != ref["artifact_id"]:
        raise ArtifactError("artifact manifest identity mismatch")
    files = manifest.get("files")
    if not isinstance(files, list) or not all(isinstance(item, dict) for item in files):
        raise ArtifactError("artifact manifest file list is invalid")
    for item in files:
        if (
            not isinstance(item.get("path"), str)
            or not isinstance(item.get("size"), int)
            or isinstance(item.get("size"), bool)
            or item["size"] < 0
            or not isinstance(item.get("sha256"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", item["sha256"])
        ):
            raise ArtifactError("artifact manifest contains an invalid file entry")
    if _content_id(files) != manifest.get("content_id"):
        raise ArtifactError("artifact content identity mismatch")
    if f"bundle-{manifest['content_id']}" != manifest["artifact_id"]:
        raise ArtifactError("artifact ID does not match content identity")
    expected_paths = set()
    for item in files:
        relative = Path(item.get("path", ""))
        if relative.is_absolute() or not relative.parts or ".." in relative.parts:
            raise ArtifactError("artifact manifest contains unsafe path")
        if relative.as_posix() in expected_paths:
            raise ArtifactError("artifact manifest contains duplicate paths")
        file_path = path / relative
        if not file_path.is_file() or is_link(file_path):
            raise ArtifactError(f"artifact file is missing or unsafe: {relative}")
        if file_path.stat().st_size != item.get("size") or sha256_file(file_path) != item.get("sha256"):
            raise ArtifactError(f"artifact file verification failed: {relative}")
        expected_paths.add(relative.as_posix())
    actual_paths = {
        relative.as_posix()
        for relative in _tree_stats(path)
        if relative.as_posix() != "bundle.json"
    }
    if actual_paths != expected_paths:
        raise ArtifactError("artifact contains files not declared by its manifest")


def _inside_existing(root: Path, value: str | Path) -> Path:
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = root / candidate
    if is_link(candidate) or not candidate.exists():
        raise ArtifactError("staging path is missing or a symlink")
    resolved = candidate.resolve()
    if not resolved.is_relative_to(root):
        raise ArtifactError("staging path escapes case root")
    return resolved


def _content_id(files: list[dict]) -> str:
    return hashlib.sha256(_canonical({"schema_version": 1, "files": files})).hexdigest()


def _canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _stat_identity(info: os.stat_result) -> tuple[int, int, int]:
    return info.st_size, info.st_mtime_ns, info.st_ino
