# D6 Acceptance

Status: `accepted_basic_flow`

Main acceptance follows the user's final scope: basic framework and flow only, reusing the
existing evidence. No additional tests, model calls, PDF builds, or layout review were requested.

## Delivered

- Shared CLI now exposes init/config, evidence intake and correction, explicit tier choice,
  coordinator start/poll, runtime status/resume/cancel, human answer files and decisions,
  experiment prepare/submit/run/finalize, literature pin/refresh/freeze, publication build and
  AI facts, immutable package staging, exact-package approval, and verified export.
- Codex resume overrides are placed after `resume`; model, effort, cwd, session ID, selected
  material, and policy snapshot remain fixed. The development launcher persists a newly
  observed session ID before process exit.
- AI disclosure facts may be human-reviewed during draft review. Only stage-map-selected,
  relevant adopted tasks enter the disclosure source; missing selected facts remain visible in
  a draft record and block final publication.
- Unsupported case keys and unsupported deadline/token/cost task limits fail explicitly.
- Product tests no longer import the development-only `../dev/launch_next.py`.

## Inherited Evidence

D5 recorded the completed pre-D6 product verification:

- Full product tests: `58 passed`.
- Publication tests: `18 passed`.
- Real XeLaTeX/BibTeX/Poppler demonstration build: 8-page A4 Chinese paper and 1-page AI
  details PDF.
- All paper pages and the AI-details page were visually inspected; fonts were embedded,
  searchable text was present, body-page accounting passed, and no overfull box exceeded the
  configured 1 pt threshold.

Reviewed example:

- [paper-electronic.pdf](examples/publication/synthetic-paper/build/paper/paper-electronic.pdf)
- [ai-usage-details.pdf](examples/publication/synthetic-paper/build/paper/ai-usage-details.pdf)
- [BUILD_REPORT.md](examples/publication/synthetic-paper/build/paper/review/BUILD_REPORT.md)

This evidence was reused. D6 did not rerun the full suite, rebuild PDFs, or reinspect pages.
The former product-side development-launcher test file was removed as requested, so `58`
describes the inherited recorded suite, not a new post-removal test count.

## D6 Smoke

One portability/startup smoke ran from
`dev/.runtime/d6-smoke/product`, a product copy excluding `.git`, hidden agent metadata,
venv, development runtime, test caches, and Python bytecode.

Observed:

- `uv sync --locked` created a fresh environment successfully.
- Top-level CLI help loaded all domain command groups.
- `init` created runtime and human-control files.
- A synthetic standard-tier question, human-format answer, decision, authorized `start`, and
  pre-run `cancel` completed without a provider call.
- A local command task ran through `serve --stop-when-idle` and reached `succeeded`.
- The existing reviewed demonstration PDFs were staged into an immutable ArtifactRef, approved
  through synthetic smoke human records, hash-verified, and exported.

Smoke ArtifactRef:

`bundle-03d50c56d169e333a6c490f74a099acbcb35b59a2f742048565833517e9a8ff7`

The smoke decision is synthetic integration data under `dev/.runtime`; it is not a real
competition approval or live-provider proof.

## Remaining Limits

- No live provider, MCP, Exa, zvec-grep, rate-limit recovery, or provider-specific resume call
  was run for D6. The user requested basic-flow acceptance.
- Linux/WSL is required. Target machines must install or explicitly configure uv, Bun, rtk,
  Codex CLI, XeLaTeX/latexmk/BibTeX, CTeX/xeCJK/zhnumber, Noto CJK fonts, and Poppler.
- The accepted environment requires a working CTeX/xeCJK/zhnumber supplement and CJK fonts. Any
  TeX tree is a host dependency, not a disposable build cache; configure an equivalent tree on
  the target machine. The clean-copy smoke did not rebuild PDFs.
- PDF intake has no OCR, XLSX formulas are not calculated, and new scientific figure schemas
  need task-specific renderers.
- Competition and regional rules must be refreshed and frozen for each real case. No real human
  route/result/package approval is claimed.
