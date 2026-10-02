# Publication

`mathmodel_agent.publication` turns one fixed selected result, a D2-compatible evidence
freeze, and one D4 formal run package into a checked Chinese XeLaTeX candidate. It owns
writing structure, deterministic result macros/tables, final-size figures, PDF construction,
machine checks, page rendering, and visual-review evidence. It does not change algorithms,
samples, metric definitions, units, aggregation, evidence claims, or human approval.

## Python API

```python
from mathmodel_agent.publication import (
    build_publication,
    classify_manifest_change,
    collect_ai_usage,
    generate_results_tex,
    record_visual_review,
)
```

- `build_publication(case_root, request) -> dict` builds and rasterizes a candidate. A clean
  build returns `visual_review_pending`, never `review_ready`.
- `record_visual_review(build_report, inspected_pages=[...], notes=[...]) -> dict` requires
  every electronic-paper page and at least one concrete note. It records `review_ready`,
  which still does not mean human approval.
- `generate_results_tex(run_manifest, output_path) -> dict` emits stable metric macros and
  table rows from `execution-run-v1`.
- `classify_manifest_change(original, candidate) -> str` returns `display_only` only when
  the scientific projection is unchanged. Metric values/definitions/units/denominators,
  instances, observations, checks, inputs, or run identity changes return `science_revision`.
- `collect_ai_usage(case_root, output_path, stage_by_task={...}) -> dict` selects only the
  relevant adopted tasks named by the stage map, joins D1 runtime records to D3
  `ai_adoptions`, and writes the normalized input. Missing selected facts are written as an
  incomplete draft record; final publication still rejects them.

## Request

All paths are case-relative or absolute paths still contained by `case_root`.

```json
{
  "schema_version": "publication-request-v1",
  "publication_id": "PUB-example-v1",
  "title": "论文标题",
  "keywords": ["关键词一", "关键词二"],
  "demonstration": false,
  "selected_result": "decisions/selected-result.json",
  "evidence_freeze": "freezes/publication.json",
  "run_manifest": "artifacts/bundle-.../run_manifest.json",
  "rules": "config/publication-rules.json",
  "paper_material": "paper-material",
  "ai_usage": "paper-material/ai-usage.json",
  "output_dir": "publication/PUB-example-v1"
}
```

The selected-result record must bind `experiment_run_id`, `manifest_sha256`, and
`rules_config_sha256`. Its status is `selected`; `demo_fixture` is accepted only when the
request is explicitly a demonstration. The evidence freeze must be `ready`, contain the same
result ref, and include at least one current national or regional rule source. A build stops
with `ScienceRevisionRequired` on stale references or rule bindings.

`paper_material` contains `paper_plan.md`, `references.bib`, `sections/00-summary.tex`, one or
more body section files, and `appendix/support.tex`. The template creates one `main.tex` and
one generated section-input list. There is no table of contents. The electronic paper starts
with the summary; a print wrapper is built only when `rules.print.enabled` is true.

## Rule Configuration

The product does not embed an eternal competition-year policy. Create a
`publication-rules-v1` JSON file from the current national format/AI rules and actual regional
submission requirements, register those sources in evidence, freeze them, and bind the JSON
hash in the selected result. Supported checks include:

```json
{
  "schema_version": "publication-rules-v1",
  "first_page_must_contain": "摘要",
  "electronic_forbidden_first_page": ["承诺书", "编号专用页"],
  "anonymous_terms": ["学校全称", "赛区身份词"],
  "max_body_pages": 30,
  "max_pdf_mb": 20,
  "max_overfull_pt": 1.0,
  "print": {"enabled": false}
}
```

The current official research PDFs under `docs/interaction/.../candidates/official` are
reference-only and are not runtime dependencies.

## AI Usage Facts

D1 supplies `State(case_root).ai_usage_records()`, including task/model/effort/purpose,
process/log/result references, provider-session facts, and observed runs. D1 intentionally
leaves `human_adoption` unset. D3 or the approved human-control interface must add:

```json
{
  "adopted": "what was actually used",
  "modifications": "what a person changed",
  "verification": "what a person checked"
}
```

The publication adapter normalizes each record to `tool`, `model`, `purpose`, `stage`,
`process_ref`, and `human_adoption`. Missing facts raise `MissingAIFacts`; the module never
invents them. An explicitly labeled `fixture: true` file is accepted only for a demonstration
and is disclosed in the paper and `AI工具使用详情.pdf`.

`record_ai_adoption` accepts a real approved `ai_disclosure` decision whose displayed
object exactly matches the task ID and all three disclosure fields. This permits truthful facts
to enter the draft and AI-details PDF before package approval. The completed immutable package
still requires a separate `paper_package` decision bound to its exact ArtifactRef.

## Build And Review

Normal environment with CTeX installed:

```bash
MPLCONFIGDIR=.runtime/publication-mpl UV_CACHE_DIR=.runtime/uv-cache \
  uv run python -c 'from mathmodel_agent.publication import build_publication; print(build_publication(".", "request.json"))'
```

The development host had XeLaTeX/latexmk/Poppler but lacked CTeX. D5 installed only the
missing `ctex`, `xeCJK`, and `zhnumber` packages into `.runtime/d5-texmf-home`; the exact demo
command is:

```bash
MPLCONFIGDIR="$PWD/.runtime/d5-mpl-cache" \
TEXMFHOME="$PWD/.runtime/d5-texmf-home" \
TEXMFVAR="$PWD/.runtime/d5-tex-var" \
TEXMFCONFIG="$PWD/.runtime/d5-tex-config" \
UV_CACHE_DIR="$PWD/.runtime/d5-uv-cache" \
  uv run python -c 'from mathmodel_agent.publication import build_publication; print(build_publication(".", "examples/publication/synthetic-paper/request.json"))'
```

After inspecting the actual PNGs under `paper/review/pages/` and the AI detail pages:

```bash
uv run python -c 'from mathmodel_agent.publication import record_visual_review; print(record_visual_review("examples/publication/synthetic-paper/build/paper/review/BUILD_REPORT.md", inspected_pages=list(range(1, 9)), notes=["record concrete findings here"]))'
```

## Current CLI integration

`mathmodel_agent.cli.build_parser` already registers `mathmodel_agent.publication.cli.add_publication_parser(subparsers)`. The current commands are:

```text
mmagent publication build CASE_ROOT REQUEST_JSON
mmagent publication visual-review BUILD_REPORT --pages 1,2,3 --note "actual observation"
mmagent publication collect-ai CASE_ROOT OUTPUT_JSON STAGE_MAP_JSON
mmagent publication stage CASE_ROOT BUILD_DIR SUBMISSION_ID --artifact-ref-output REF_JSON
mmagent publication request-approval CASE_ROOT REF_JSON
mmagent publication export CASE_ROOT REF_JSON DEST --decision-id D-001
```

The current top-level dispatcher calls `args.handler(args)` and prints its JSON result, matching the evidence hook pattern. This records existing source wiring, not a newly executed provider or publication-build verification.

## Outputs And Limits

The managed output contains `paper-electronic.pdf`, optional `paper-print.pdf`,
`AI工具使用详情.pdf`, the complete TeX project, all page PNGs, `BUILD_REPORT.md/.json`, a
figure index, and `support/run/` with the selected source/config/observations/metrics/figure
data/script/display/checks/lockfile package.

The first renderer is deliberately scoped to the D4 allocation demonstration. A new figure
schema needs a problem-specific renderer. A genuine supplied image may be used without a
script only when the figure index discloses that it cannot be redrawn. The module does not
provide DOCX, LibreOffice, DrawIO, Plotly/Chrome, publisher profiles, or a fixed reviewer
chain. The system must provide `latexmk`, XeLaTeX, CTeX/xeCJK, a suitable CJK font, BibTeX,
and Poppler.
