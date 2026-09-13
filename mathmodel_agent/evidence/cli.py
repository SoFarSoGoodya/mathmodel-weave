"""Optional CLI registration hook for the final product CLI owner."""

from __future__ import annotations

from pathlib import Path

from mathmodel_agent.contracts import read_json

from .freeze import bibliography_for_freeze, freeze_evidence
from .intake import correct_pdf_text, intake_pdf, intake_xlsx, validate_xlsx_export
from .pool import pin_consumer, refresh_consumer, register_source, write_source_notes


def add_evidence_parser(subparsers) -> None:
    """Register small intake commands on an argparse subparser collection."""
    parser = subparsers.add_parser("evidence", help="intake evidence files")
    commands = parser.add_subparsers(dest="evidence_command", required=True)
    pdf = commands.add_parser("pdf", help="extract a local PDF")
    pdf.add_argument("case_root", type=Path)
    pdf.add_argument("pdf_path", type=Path)
    pdf.add_argument("--problem-id")
    pdf.set_defaults(handler=lambda args: intake_pdf(args.case_root, args.pdf_path, problem_id=args.problem_id))
    xlsx = commands.add_parser("xlsx", help="export all XLSX sheets to CSV")
    xlsx.add_argument("case_root", type=Path)
    xlsx.add_argument("xlsx_path", type=Path)
    xlsx.add_argument("--dataset-id")
    xlsx.set_defaults(handler=lambda args: intake_xlsx(args.case_root, args.xlsx_path, dataset_id=args.dataset_id))

    correction = commands.add_parser("pdf-correct", help="record reviewed statement text")
    correction.add_argument("case_root", type=Path)
    correction.add_argument("problem_id")
    correction.add_argument("corrected_markdown", type=Path)
    correction.add_argument("--reviewer")
    correction.set_defaults(
        handler=lambda args: correct_pdf_text(
            args.case_root,
            args.problem_id,
            args.corrected_markdown.read_text(encoding="utf-8"),
            reviewer=args.reviewer,
        )
    )

    validate = commands.add_parser("xlsx-validate", help="validate exported workbook data")
    validate.add_argument("case_root", type=Path)
    validate.add_argument("dataset_id")
    validate.set_defaults(handler=lambda args: validate_xlsx_export(args.case_root, args.dataset_id))

    source = commands.add_parser("source", help="register a literature source from JSON")
    source.add_argument("case_root", type=Path)
    source.add_argument("request", type=Path)
    source.set_defaults(handler=lambda args: register_source(args.case_root, **read_json(args.request)))

    notes = commands.add_parser("notes", help="write notes for a registered source")
    notes.add_argument("case_root", type=Path)
    notes.add_argument("source_id")
    notes.add_argument("notes", type=Path)
    notes.add_argument("--purpose")
    notes.add_argument("--limitations")
    notes.set_defaults(
        handler=lambda args: {
            "path": str(
                write_source_notes(
                    args.case_root,
                    args.source_id,
                    args.notes.read_text(encoding="utf-8"),
                    purpose=args.purpose,
                    limitations=args.limitations,
                )
            )
        }
    )

    pin = commands.add_parser("pin", help="pin adopted evidence from JSON")
    pin.add_argument("case_root", type=Path)
    pin.add_argument("request", type=Path)
    pin.set_defaults(handler=lambda args: pin_consumer(args.case_root, **read_json(args.request)))

    refresh = commands.add_parser("refresh", help="refresh selected pinned versions")
    refresh.add_argument("case_root", type=Path)
    refresh.add_argument("consumer_id")
    refresh.add_argument("--source", action="append", default=[])
    refresh.add_argument("--dataset", action="append", default=[])
    refresh.set_defaults(
        handler=lambda args: refresh_consumer(
            args.case_root, args.consumer_id, source_ids=args.source, dataset_ids=args.dataset
        )
    )

    freeze = commands.add_parser("freeze", help="freeze adopted evidence from JSON")
    freeze.add_argument("case_root", type=Path)
    freeze.add_argument("request", type=Path)
    freeze.set_defaults(handler=lambda args: freeze_evidence(args.case_root, **read_json(args.request)))

    bibliography = commands.add_parser("bibliography", help="build BibTeX for one freeze")
    bibliography.add_argument("case_root", type=Path)
    bibliography.add_argument("freeze_id")
    bibliography.add_argument("--output", type=Path)
    bibliography.set_defaults(
        handler=lambda args: {
            "path": str(
                bibliography_for_freeze(
                    args.case_root, args.freeze_id, output_path=args.output
                )
            )
        }
    )
