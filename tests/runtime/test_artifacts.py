import os
from pathlib import Path

import pytest

from mathmodel_agent.runtime.artifacts import (
    ArtifactError,
    SubmissionConflict,
    publish_bundle,
    resolve_bundle,
)


def test_publish_deduplicates_conflicts_and_verifies_large_file(case_root: Path):
    staging = case_root / "tasks" / "manual" / "workspace" / "staging"
    staging.mkdir(parents=True)
    (staging / "result.txt").write_text("result\n", encoding="utf-8")
    (staging / "large.bin").write_bytes(b"abc123" * 500_000)

    first = publish_bundle(case_root, staging, "submission-1", task_id="manual")
    second = publish_bundle(case_root, staging, "submission-1", task_id="manual")
    assert first == second
    bundle = resolve_bundle(case_root, first["artifact_ref"])
    assert (bundle / "bundle.json").is_file()

    (staging / "result.txt").write_text("changed\n", encoding="utf-8")
    with pytest.raises(SubmissionConflict):
        publish_bundle(case_root, staging, "submission-1")


def test_publish_rejects_escape_symlink_and_partial_files(case_root: Path):
    outside = case_root.parent / "outside"
    outside.mkdir()
    (outside / "x").write_text("x", encoding="utf-8")
    with pytest.raises(ArtifactError, match="escapes"):
        publish_bundle(case_root, outside, "escape")

    staging = case_root / "paper" / "staging"
    staging.mkdir()
    os.symlink(outside / "x", staging / "link")
    with pytest.raises(ArtifactError, match="symlink"):
        publish_bundle(case_root, staging, "symlink")
    (staging / "link").unlink()
    (staging / "still.partial").write_text("half", encoding="utf-8")
    with pytest.raises(ArtifactError, match="incomplete"):
        publish_bundle(case_root, staging, "partial")


def test_resolve_detects_tampering(case_root: Path):
    staging = case_root / "paper" / "ready"
    staging.mkdir()
    (staging / "paper.pdf").write_bytes(b"pdf")
    receipt = publish_bundle(case_root, staging, "paper")
    bundle = resolve_bundle(case_root, receipt["artifact_ref"])
    (bundle / "paper.pdf").write_bytes(b"tampered")
    with pytest.raises(ArtifactError, match="verification failed"):
        resolve_bundle(case_root, receipt["artifact_ref"])
