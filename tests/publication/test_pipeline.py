from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import pytest

from mathmodel_agent.publication import PublicationError, build_publication, record_visual_review
from mathmodel_agent.publication.checks import validate_citations
from mathmodel_agent.publication.cli import add_publication_parser


PRODUCT_ROOT = Path(__file__).parents[2]
DEMO = PRODUCT_ROOT / "examples/publication/synthetic-paper"


def test_valid_and_invalid_citation_references(tmp_path):
    (tmp_path / "main.tex").write_text(r"Evidence \cite{known}.", encoding="utf-8")
    (tmp_path / "references.bib").write_text(
        "@misc{known, title={Known source}}\n@misc{unused, title={Unused source}}\n",
        encoding="utf-8",
    )
    result = validate_citations(tmp_path)
    assert result == {"cited": ["known"], "available": ["known", "unused"], "unused": ["unused"]}

    (tmp_path / "main.tex").write_text(r"Evidence \cite{missing}.", encoding="utf-8")
    with pytest.raises(PublicationError, match="missing"):
        validate_citations(tmp_path)


def test_cli_hook_parses_build_and_visual_review():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    add_publication_parser(subparsers)
    build = parser.parse_args(["publication", "build", ".", "request.json"])
    assert build.publication_command == "build"
    review = parser.parse_args(
        ["publication", "visual-review", "BUILD_REPORT.md", "--pages", "1,2", "--note", "readable"]
    )
    assert review.pages == [1, 2]


def test_visual_review_requires_every_page(tmp_path):
    report_path = tmp_path / "BUILD_REPORT.md"
    value = {
        "status": "visual_review_pending",
        "publication_id": "fixture",
        "demonstration": True,
        "manifest_sha256": "0" * 64,
        "electronic_pdf": "paper.pdf",
        "pdf": {
            "sha256": "1" * 64,
            "pages": 2,
            "bytes": 1,
            "fonts": {"font_count": 1},
            "text_characters": 10,
            "rendered_pages": ["page-1.png", "page-2.png"],
        },
        "body_end_page": 1,
        "ai_pdf": {"pages": 1, "fonts": {"font_count": 1}},
        "citations": {"cited": []},
    }
    report_path.with_suffix(".json").write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(PublicationError, match="every page"):
        record_visual_review(report_path, inspected_pages=[1], notes=["page one checked"])


def test_real_xelatex_demo_reports_pages_fonts_and_text(monkeypatch):
    local_texmf = PRODUCT_ROOT / ".runtime/d5-texmf-home"
    if local_texmf.is_dir():
        monkeypatch.setenv("TEXMFHOME", str(local_texmf))
    monkeypatch.setenv("TEXMFVAR", str(PRODUCT_ROOT / ".runtime/d5-test-tex-var"))
    monkeypatch.setenv("TEXMFCONFIG", str(PRODUCT_ROOT / ".runtime/d5-test-tex-config"))
    monkeypatch.setenv("MPLCONFIGDIR", str(PRODUCT_ROOT / ".runtime/d5-test-mpl-cache"))
    request = json.loads((DEMO / "request.json").read_text(encoding="utf-8"))
    request["publication_id"] = "PUB-synthetic-allocation-pytest"
    request["output_dir"] = ".test-tmp/publication-real-build"

    result = build_publication(PRODUCT_ROOT, request)

    assert result["status"] == "visual_review_pending"
    assert result["pdf"]["pages"] >= 7
    assert result["pdf"]["page_size"].endswith("(A4)")
    assert result["pdf"]["fonts"]["not_embedded"] == []
    assert result["pdf"]["text_characters"] > 5000
    assert len(result["pdf"]["rendered_pages"]) == result["pdf"]["pages"]
    assert result["body_end_page"] <= 30
    assert result["ai_pdf"]["pages"] == 1
    assert result["ai_pdf"]["fonts"]["not_embedded"] == []
    assert result["ai_pdf"]["text_characters"] > 300
    assert os.path.isfile(PRODUCT_ROOT / request["output_dir"] / "paper-electronic.pdf")
