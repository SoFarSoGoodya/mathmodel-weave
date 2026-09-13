"""Build-time TeX, PDF, citation, anonymity, and visual-review checks."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from mathmodel_agent.contracts import sha256_file

from .errors import PublicationError


CITE_PATTERN = re.compile(r"\\cite[a-zA-Z*]*\s*(?:\[[^]]*\]\s*){0,2}\{([^}]+)\}")
BIB_PATTERN = re.compile(r"@[A-Za-z]+\s*\{\s*([^,\s]+)")
PLACEHOLDER_PATTERN = re.compile(r"\b(?:TODO|FIXME|PLACEHOLDER|TBD)\b|待补|占位符", re.IGNORECASE)


def validate_citations(project: str | Path) -> dict:
    root = Path(project)
    tex_files = sorted(root.rglob("*.tex"))
    cited = set()
    for path in tex_files:
        for match in CITE_PATTERN.finditer(path.read_text(encoding="utf-8")):
            cited.update(key.strip() for key in match.group(1).split(",") if key.strip())
    bibliography = root / "references.bib"
    available = set(BIB_PATTERN.findall(bibliography.read_text(encoding="utf-8")))
    missing = sorted(cited - available)
    if missing:
        raise PublicationError(f"citation keys missing from references.bib: {', '.join(missing)}")
    return {"cited": sorted(cited), "available": sorted(available), "unused": sorted(available - cited)}


def scan_placeholders(project: str | Path) -> list[str]:
    findings = []
    for path in sorted(Path(project).rglob("*")):
        if path.is_file() and path.suffix in {".tex", ".md", ".bib"}:
            for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                if PLACEHOLDER_PATTERN.search(line):
                    findings.append(f"{path.relative_to(project)}:{line_no}")
    return findings


def run_checked(command: list[str], *, cwd: str | Path, log_path: str | Path | None = None) -> str:
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=False)
    combined = result.stdout + result.stderr
    if log_path is not None:
        Path(log_path).write_text(combined, encoding="utf-8")
    if result.returncode != 0:
        raise PublicationError(f"command failed ({result.returncode}): {' '.join(command)}")
    return combined


def compile_xelatex(project: str | Path, source: str, jobname: str) -> dict:
    root = Path(project)
    build_log = root / "review" / f"{jobname}-latexmk.log"
    output = run_checked(
        [
            "latexmk",
            "-xelatex",
            "-interaction=nonstopmode",
            "-halt-on-error",
            "-file-line-error",
            f"-jobname={jobname}",
            source,
        ],
        cwd=root,
        log_path=build_log,
    )
    log_text = (root / f"{jobname}.log").read_text(encoding="utf-8", errors="replace")
    undefined = sorted(
        set(re.findall(r"(?:undefined references|Citation [`'][^`']+[`'] on page .* undefined)", log_text, re.I))
    )
    overfull = re.findall(r"Overfull \\[hv]box \(([^)]+) too wide\)", log_text)
    if undefined:
        raise PublicationError(f"undefined TeX references or citations in {jobname}")
    return {
        "command": "latexmk -xelatex -interaction=nonstopmode -halt-on-error -file-line-error "
        f"-jobname={jobname} {source}",
        "log": build_log.name,
        "overfull": overfull,
        "latexmk_output_tail": output[-1200:],
    }


def _pdfinfo(path: Path) -> dict:
    text = run_checked(["pdfinfo", str(path)], cwd=path.parent)
    result = {}
    for line in text.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            result[key.strip()] = value.strip()
    return result


def _font_report(path: Path) -> dict:
    text = run_checked(["pdffonts", str(path)], cwd=path.parent)
    rows = []
    not_embedded = []
    for line in text.splitlines()[2:]:
        match = re.search(r"\s(yes|no)\s+(yes|no)\s+(yes|no)\s+\d+\s+\d+\s*$", line, re.I)
        if not match:
            continue
        rows.append(line)
        if match.group(1).lower() != "yes":
            not_embedded.append(line.split()[0])
    return {"font_count": len(rows), "not_embedded": not_embedded, "raw": text}


def inspect_pdf(
    pdf_path: str | Path,
    review_directory: str | Path,
    rules: dict,
    *,
    critical_numbers: list[str],
) -> dict:
    pdf = Path(pdf_path)
    review = Path(review_directory)
    pages = review / "pages"
    pages.mkdir(parents=True, exist_ok=True)
    info = _pdfinfo(pdf)
    fonts = _font_report(pdf)
    text_path = review / "paper-electronic.txt"
    run_checked(["pdftotext", "-layout", str(pdf), str(text_path)], cwd=pdf.parent)
    text = text_path.read_text(encoding="utf-8", errors="replace")
    first_page_path = review / "paper-electronic-page1.txt"
    run_checked(["pdftotext", "-f", "1", "-l", "1", str(pdf), str(first_page_path)], cwd=pdf.parent)
    first_page = first_page_path.read_text(encoding="utf-8", errors="replace")
    page_prefix = pages / "page"
    run_checked(["pdftoppm", "-png", "-r", "144", str(pdf), str(page_prefix)], cwd=pdf.parent)
    rendered = sorted(pages.glob("page-*.png"))

    failures = []
    required_first = rules.get("first_page_must_contain", "摘要")
    if required_first not in first_page:
        failures.append(f"first page lacks required text: {required_first}")
    for forbidden in rules.get("electronic_forbidden_first_page", []):
        if forbidden and forbidden in first_page:
            failures.append(f"first page contains forbidden text: {forbidden}")
    for term in rules.get("anonymous_terms", []):
        if term and term in text:
            failures.append(f"anonymous term found in PDF: {term}")
    for number in critical_numbers:
        if number not in text:
            failures.append(f"critical manifest number missing from PDF text layer: {number}")
    if fonts["not_embedded"]:
        failures.append("unembedded fonts: " + ", ".join(fonts["not_embedded"]))
    page_count = int(info.get("Pages", "0"))
    if page_count != len(rendered):
        failures.append(f"rendered page count {len(rendered)} differs from PDF page count {page_count}")
    max_size = float(rules.get("max_pdf_mb", 20)) * 1024 * 1024
    if pdf.stat().st_size > max_size:
        failures.append("electronic PDF exceeds configured size limit")
    if not text.strip():
        failures.append("PDF has no extractable text layer")
    if failures:
        raise PublicationError("; ".join(failures))
    return {
        "sha256": sha256_file(pdf),
        "bytes": pdf.stat().st_size,
        "pages": page_count,
        "page_size": info.get("Page size"),
        "metadata": {key: info.get(key) for key in ("Title", "Author", "Creator", "Producer")},
        "fonts": {"font_count": fonts["font_count"], "not_embedded": fonts["not_embedded"]},
        "text_characters": len(text),
        "rendered_pages": [path.name for path in rendered],
    }


def inspect_auxiliary_pdf(pdf_path: str | Path, review_directory: str | Path) -> dict:
    pdf = Path(pdf_path)
    review = Path(review_directory)
    pages = review / "pages"
    pages.mkdir(parents=True, exist_ok=True)
    info = _pdfinfo(pdf)
    fonts = _font_report(pdf)
    text_path = review / "text.txt"
    run_checked(["pdftotext", "-layout", str(pdf), str(text_path)], cwd=pdf.parent)
    text = text_path.read_text(encoding="utf-8", errors="replace")
    run_checked(["pdftoppm", "-png", "-r", "144", str(pdf), str(pages / "page")], cwd=pdf.parent)
    rendered = sorted(pages.glob("page-*.png"))
    page_count = int(info.get("Pages", "0"))
    failures = []
    if fonts["not_embedded"]:
        failures.append("unembedded fonts: " + ", ".join(fonts["not_embedded"]))
    if not text.strip():
        failures.append("auxiliary PDF has no extractable text layer")
    if page_count != len(rendered):
        failures.append("auxiliary PDF render count differs from its page count")
    if failures:
        raise PublicationError("; ".join(failures))
    return {
        "sha256": sha256_file(pdf),
        "bytes": pdf.stat().st_size,
        "pages": page_count,
        "fonts": {"font_count": fonts["font_count"], "not_embedded": fonts["not_embedded"]},
        "text_characters": len(text),
        "rendered_pages": [path.name for path in rendered],
    }


def body_end_page(aux_path: str | Path) -> int:
    text = Path(aux_path).read_text(encoding="utf-8", errors="replace")
    match = re.search(r"\\newlabel\{mmagent-body-end\}\{\{[^}]*\}\{(\d+)\}", text)
    if not match:
        raise PublicationError("body-end page label is missing from TeX auxiliary output")
    return int(match.group(1))


def write_build_report(path: str | Path, report: dict) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    json_path = target.with_suffix(".json")
    json_path.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Publication Build Report",
        "",
        f"Status: `{report['status']}`",
        "",
        f"- Publication ID: `{report['publication_id']}`",
        f"- Demonstration: `{str(report['demonstration']).lower()}`",
        f"- Manifest SHA-256: `{report['manifest_sha256']}`",
        f"- Electronic PDF: `{report['electronic_pdf']}`",
        f"- PDF SHA-256: `{report['pdf']['sha256']}`",
        f"- Pages / bytes: `{report['pdf']['pages']}` / `{report['pdf']['bytes']}`",
        f"- Embedded fonts checked: `{report['pdf']['fonts']['font_count']}`",
        f"- Text layer characters: `{report['pdf']['text_characters']}`",
        f"- Rendered pages: `{len(report['pdf']['rendered_pages'])}`",
        f"- Body end page: `{report['body_end_page']}`",
        f"- AI details pages / fonts: `{report['ai_pdf']['pages']}` / `{report['ai_pdf']['fonts']['font_count']}`",
        f"- Citation keys used: `{', '.join(report['citations']['cited']) or 'none'}`",
        f"- Print target: `{report.get('print_pdf') or 'not configured'}`",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- {item}" for item in report.get("checks", []))
    lines.extend(["", "## Visual Review", ""])
    if report["status"] == "review_ready":
        lines.append(f"Inspected all pages: `{', '.join(str(item) for item in report['visual_review']['pages'])}`.")
        lines.extend(f"- {item}" for item in report["visual_review"].get("notes", []))
    else:
        lines.append("All pages are rasterized, but actual visual inspection has not yet been recorded.")
    lines.extend(["", "## Limitations", ""])
    lines.extend(f"- {item}" for item in report.get("limitations", []))
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")


def record_visual_review(
    build_report: str | Path,
    *,
    inspected_pages: list[int],
    notes: list[str],
) -> dict:
    markdown = Path(build_report)
    json_path = markdown.with_suffix(".json")
    report = json.loads(json_path.read_text(encoding="utf-8"))
    expected = list(range(1, report["pdf"]["pages"] + 1))
    if sorted(set(inspected_pages)) != expected:
        raise PublicationError(f"visual review must explicitly cover every page: expected {expected}")
    if not notes:
        raise PublicationError("visual review must record at least one concrete observation")
    report["status"] = "review_ready"
    report["visual_review"] = {"pages": expected, "notes": notes}
    write_build_report(markdown, report)
    return report
