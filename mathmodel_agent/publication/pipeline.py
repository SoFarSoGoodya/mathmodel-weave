"""One bounded publication pipeline from frozen inputs to reviewable PDFs."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from mathmodel_agent.contracts import read_json, sha256_file

from .ai_usage import prepare_ai_usage
from .checks import (
    body_end_page,
    compile_xelatex,
    inspect_auxiliary_pdf,
    inspect_pdf,
    scan_placeholders,
    validate_citations,
    write_build_report,
)
from .errors import PublicationError, ScienceRevisionRequired
from .figures import redraw_manifest_figures, write_figure_index
from .inputs import case_file, validate_frozen_inputs
from .manifest import generate_results_tex


MARKER = ".publication-build-root"


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


def _request(value: str | Path | dict) -> dict:
    request = read_json(value) if isinstance(value, (str, Path)) else value
    if not isinstance(request, dict) or request.get("schema_version") != "publication-request-v1":
        raise PublicationError("unsupported publication request schema")
    return request


def _output_path(case_root: Path, value: str | Path) -> Path:
    path = Path(value)
    output = path.resolve() if path.is_absolute() else (case_root / path).resolve()
    if not output.is_relative_to(case_root) or output == case_root:
        raise PublicationError("publication output must be a dedicated directory inside case root")
    return output


def _reset_output(output: Path) -> None:
    if output.exists():
        marker = output / MARKER
        if not marker.is_file():
            raise PublicationError(f"refusing to replace an unmarked directory: {output}")
        shutil.rmtree(output)
    output.mkdir(parents=True)
    (output / MARKER).write_text("managed by mathmodel_agent.publication\n", encoding="utf-8")


def _copy_material(material: Path, project: Path) -> list[str]:
    required = [
        material / "paper_plan.md",
        material / "sections/00-summary.tex",
        material / "appendix/support.tex",
        material / "references.bib",
    ]
    missing = [str(path.relative_to(material)) for path in required if not path.is_file()]
    if missing:
        raise PublicationError("paper material is missing: " + ", ".join(missing))
    shutil.copy2(material / "paper_plan.md", project / "paper_plan.md")
    shutil.copy2(material / "references.bib", project / "references.bib")
    shutil.copytree(material / "sections", project / "sections")
    shutil.copytree(material / "appendix", project / "appendix")
    sections = sorted(path for path in (project / "sections").glob("*.tex") if path.name != "00-summary.tex")
    if not sections:
        raise PublicationError("paper material has no body sections")
    generated = project / "generated"
    generated.mkdir()
    (generated / "section-inputs.tex").write_text(
        "\n".join(rf"\input{{sections/{path.name}}}" for path in sections) + "\n",
        encoding="utf-8",
    )
    return [path.name for path in sections]


def _write_meta(project: Path, request: dict) -> None:
    title = request.get("title")
    keywords = request.get("keywords")
    if not isinstance(title, str) or not title.strip():
        raise PublicationError("publication title is required")
    if not isinstance(keywords, list) or not keywords or not all(isinstance(item, str) for item in keywords):
        raise PublicationError("publication keywords must be a non-empty string list")
    demonstration = 1 if request.get("demonstration") else 0
    lines = [
        rf"\newcommand{{\PaperTitle}}{{{_tex_escape(title)}}}",
        rf"\newcommand{{\PaperKeywords}}{{{_tex_escape('；'.join(keywords))}}}",
        rf"\newcommand{{\PublicationId}}{{{_tex_escape(request['publication_id'])}}}",
        rf"\newcommand{{\IsDemonstration}}{{{demonstration}}}",
        rf"\newcommand{{\PrintFrontTitle}}{{{_tex_escape(request.get('print_front_title', '纸质提交前置页'))}}}",
        rf"\newcommand{{\PrintFrontBody}}{{{_tex_escape(request.get('print_front_body', ''))}}}",
    ]
    (project / "generated/build-meta.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _validate_rule_binding(selected: dict, freeze: dict, rules_path: Path) -> None:
    if not freeze.get("rules_sources"):
        raise ScienceRevisionRequired("evidence freeze contains no official or regional rule source")
    expected = selected.get("rules_config_sha256")
    actual = sha256_file(rules_path)
    if expected != actual:
        raise ScienceRevisionRequired("selected result refers to a stale publication rule config")


def _enforce_overfull(build: dict, rules: dict, target: str) -> None:
    limit = float(rules.get("max_overfull_pt", 6.0))
    widths = []
    for value in build.get("overfull", []):
        match = re.match(r"([0-9.]+)pt", value)
        if match:
            widths.append(float(match.group(1)))
    excessive = [value for value in widths if value > limit]
    if excessive:
        raise PublicationError(
            f"{target} has overfull boxes above {limit:g} pt: "
            + ", ".join(f"{value:g}pt" for value in excessive)
        )


def build_publication(case_root: str | Path, request: str | Path | dict) -> dict:
    """Build one electronic candidate and leave it pending actual visual review."""
    root = Path(case_root).resolve()
    spec = _request(request)
    publication_id = spec.get("publication_id")
    if not isinstance(publication_id, str) or not publication_id:
        raise PublicationError("publication_id is required")
    demonstration = bool(spec.get("demonstration", False))
    selected_path = case_file(root, spec["selected_result"])
    freeze_path = case_file(root, spec["evidence_freeze"])
    manifest_path = case_file(root, spec["run_manifest"])
    rules_path = case_file(root, spec["rules"])
    material = case_file(root, spec["paper_material"], directory=True)
    ai_facts = case_file(root, spec["ai_usage"])
    output = _output_path(root, spec["output_dir"])

    frozen = validate_frozen_inputs(
        selected_path, freeze_path, manifest_path, demonstration=demonstration
    )
    _validate_rule_binding(frozen["selected"], frozen["freeze"], rules_path)
    rules = read_json(rules_path)
    if rules.get("schema_version") != "publication-rules-v1":
        raise PublicationError("unsupported publication rules schema")
    _reset_output(output)

    project = output / "paper"
    template = Path(__file__).parents[2] / "templates/publication"
    shutil.copytree(template, project)
    sections = _copy_material(material, project)
    _write_meta(project, spec)
    metric_result = generate_results_tex(manifest_path, project / "generated/results.tex")
    ai_result = prepare_ai_usage(
        ai_facts,
        project / "ai-usage.md",
        project / "generated/ai-usage.tex",
        demonstration=demonstration,
    )

    run_directory = manifest_path.parent
    support = output / "support/run"
    shutil.copytree(run_directory, support)
    figure_records = redraw_manifest_figures(
        run_directory,
        project / "figures",
        style_path=project / "cumcm.mplstyle",
    )
    write_figure_index(figure_records, project / "figures/README.md")
    (output / "support/SUPPORT_LIST.md").write_text(
        "# Supporting Material\n\n"
        "- `run/`: immutable selected D4 run package, including source, configuration, "
        "observations, metrics, figure data/script/display config, checks, and lockfile.\n"
        "- `../paper/ai-usage.md`: validated AI-use narrative source.\n"
        "- `../AI工具使用详情.pdf`: detail PDF generated from the same source.\n",
        encoding="utf-8",
    )

    citations = validate_citations(project)
    placeholders = scan_placeholders(project)
    if placeholders:
        raise PublicationError("publication source contains placeholders: " + ", ".join(placeholders))
    review = project / "review"
    review.mkdir()
    electronic_build = compile_xelatex(project, "main.tex", "paper-electronic")
    _enforce_overfull(electronic_build, rules, "electronic paper")
    electronic = project / "paper-electronic.pdf"
    shutil.copy2(electronic, output / "paper-electronic.pdf")
    ai_build = compile_xelatex(project, "ai-details.tex", "ai-usage-details")
    _enforce_overfull(ai_build, rules, "AI details")
    shutil.copy2(project / "ai-usage-details.pdf", output / "AI工具使用详情.pdf")

    print_pdf = None
    print_build = None
    if rules.get("print", {}).get("enabled", False):
        (project / "print-main.tex").write_text(
            "\\def\\MMPrintTarget{1}\n\\input{main.tex}\n", encoding="utf-8"
        )
        print_build = compile_xelatex(project, "print-main.tex", "paper-print")
        _enforce_overfull(print_build, rules, "print paper")
        shutil.copy2(project / "paper-print.pdf", output / "paper-print.pdf")
        print_pdf = "paper-print.pdf"

    pdf_result = inspect_pdf(
        output / "paper-electronic.pdf",
        review,
        rules,
        critical_numbers=list(metric_result["macros"].values()),
    )
    body_page = body_end_page(project / "paper-electronic.aux")
    if body_page > int(rules.get("max_body_pages", 30)):
        raise PublicationError("paper body exceeds the configured page limit")
    ai_pdf_result = inspect_auxiliary_pdf(output / "AI工具使用详情.pdf", review / "ai-details")
    report = {
        "status": "visual_review_pending",
        "publication_id": publication_id,
        "demonstration": demonstration,
        "manifest_sha256": frozen["manifest_sha256"],
        "electronic_pdf": "paper-electronic.pdf",
        "ai_details_pdf": "AI工具使用详情.pdf",
        "print_pdf": print_pdf,
        "sections": sections,
        "metrics": metric_result,
        "ai_usage": ai_result,
        "figures": figure_records,
        "citations": citations,
        "pdf": pdf_result,
        "body_end_page": body_page,
        "ai_pdf": ai_pdf_result,
        "builds": {"electronic": electronic_build, "ai_details": ai_build, "print": print_build},
        "checks": [
            "selected result and evidence freeze match the exact run manifest SHA-256",
            "official/regional rule source is present and the rule config hash is selected",
            "result macros and table rows were generated deterministically from the manifest",
            "figure rows match complete saved observations; no undefined interval was drawn",
            "citation keys, placeholders, first-page rules, anonymity terms, critical numbers, PDF size, fonts, and text layer passed",
            "every electronic PDF page was rasterized for visual inspection",
        ],
        "limitations": [
            "review_ready still requires actual inspection of every rendered page; compilation alone is insufficient",
            "the included specialized redraw handles the allocation demonstration; new scientific figure schemas require a task-specific renderer or an honestly disclosed original-image adoption",
            "the rule config is a frozen project interpretation and must be updated from current official and regional sources for each competition",
            "demonstration AI adoption facts are interface fixtures and do not represent live human approval",
        ],
    }
    write_build_report(review / "BUILD_REPORT.md", report)
    return report
