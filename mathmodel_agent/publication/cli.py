"""Optional publication CLI registration for the final D6 CLI owner."""

from __future__ import annotations

from pathlib import Path
import shutil

from mathmodel_agent import control
from mathmodel_agent.contracts import read_json, write_json
from mathmodel_agent.runtime.artifacts import publish_bundle, resolve_bundle

from .ai_usage import collect_ai_usage
from .checks import record_visual_review
from .pipeline import build_publication


def _pages(value: str) -> list[int]:
    try:
        pages = [int(item) for item in value.split(",") if item]
    except ValueError as exc:
        raise ValueError("pages must be comma-separated positive integers") from exc
    if not pages or any(page <= 0 for page in pages):
        raise ValueError("pages must be comma-separated positive integers")
    return pages


def add_publication_parser(subparsers) -> None:
    """Register build and explicit visual-review commands."""
    parser = subparsers.add_parser("publication", help="build and review a frozen paper package")
    commands = parser.add_subparsers(dest="publication_command", required=True)

    build = commands.add_parser("build", help="build, check, and rasterize a publication request")
    build.add_argument("case_root", type=Path)
    build.add_argument("request", type=Path)
    build.set_defaults(handler=lambda args: build_publication(args.case_root, args.request))

    review = commands.add_parser("visual-review", help="record inspection of every paper page")
    review.add_argument("build_report", type=Path)
    review.add_argument("--pages", required=True, type=_pages)
    review.add_argument("--note", action="append", required=True)
    review.set_defaults(
        handler=lambda args: record_visual_review(
            args.build_report, inspected_pages=args.pages, notes=args.note
        )
    )

    ai = commands.add_parser("collect-ai", help="join runtime use with reviewed adoption facts")
    ai.add_argument("case_root", type=Path)
    ai.add_argument("output", type=Path)
    ai.add_argument("stage_map", type=Path)
    ai.set_defaults(
        handler=lambda args: collect_ai_usage(
            args.case_root, args.output, stage_by_task=read_json(args.stage_map)
        )
    )

    stage = commands.add_parser("stage", help="publish an immutable completed package")
    stage.add_argument("case_root", type=Path)
    stage.add_argument("build_dir", type=Path)
    stage.add_argument("submission_id")
    stage.add_argument("--artifact-ref-output", type=Path)
    stage.set_defaults(handler=_stage_package)

    approval = commands.add_parser("request-approval", help="ask about an exact staged package")
    approval.add_argument("case_root", type=Path)
    approval.add_argument("artifact_ref", type=Path)
    approval.set_defaults(handler=_request_approval)

    export = commands.add_parser("export", help="export an exactly approved staged package")
    export.add_argument("case_root", type=Path)
    export.add_argument("artifact_ref", type=Path)
    export.add_argument("destination", type=Path)
    export.add_argument("--decision-id", required=True)
    export.set_defaults(handler=_export_approved)


def _request_approval(args) -> dict:
    artifact_ref = read_json(args.artifact_ref)
    resolve_bundle(args.case_root, artifact_ref)
    return control.ask_human(
        args.case_root,
        scope="paper_package",
        displayed=artifact_ref,
        prompt="请确认是否批准这个哈希完全一致的最终提交包。",
        choices=["approve", "reject"],
        approval_choices=["approve"],
    )


def _stage_package(args) -> dict:
    receipt = publish_bundle(args.case_root, args.build_dir, args.submission_id)
    if args.artifact_ref_output is not None:
        write_json(args.artifact_ref_output, receipt["artifact_ref"])
    return receipt


def _export_approved(args) -> dict:
    artifact_ref = read_json(args.artifact_ref)
    approved = control.decision(args.case_root, args.decision_id)
    if approved["scope"] != "paper_package" or approved["status"] != "approved":
        raise ValueError("decision is not an approved paper_package decision")
    if approved["displayed"] != artifact_ref:
        raise ValueError("approved package differs from the requested artifact")
    source = resolve_bundle(args.case_root, artifact_ref)
    destination = args.destination.resolve()
    if destination.exists():
        raise FileExistsError(f"export destination already exists: {destination}")
    shutil.copytree(source, destination)
    return {"artifact_ref": artifact_ref, "decision_id": args.decision_id, "exported_to": str(destination)}
