"""File-backed evidence intake, source curation, pins, and freezes."""

from .freeze import bibliography_for_freeze, freeze_evidence
from .intake import correct_pdf_text, intake_pdf, intake_xlsx, request_visual_review, validate_xlsx_export
from .pool import (
    affected_references,
    curate_batch,
    pin_consumer,
    refresh_consumer,
    register_claim,
    register_dataset,
    register_source,
    report_error,
    write_source_notes,
    write_topic,
)

__all__ = [
    "affected_references",
    "bibliography_for_freeze",
    "correct_pdf_text",
    "curate_batch",
    "freeze_evidence",
    "intake_pdf",
    "intake_xlsx",
    "pin_consumer",
    "refresh_consumer",
    "register_claim",
    "register_dataset",
    "register_source",
    "report_error",
    "request_visual_review",
    "validate_xlsx_export",
    "write_source_notes",
    "write_topic",
]
