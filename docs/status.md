# Current implementation and evidence

The current source implements the shared CLI lifecycle: case init/config and doctor; task submit/status/resume/cancel/serve; tier questions, human answers and exact-object decisions; authorized coordinator start and workflow polling; PDF/XLSX intake/correction/validation; evidence registration/pinning/refresh/freezing; candidates and comparison contracts; runtime-backed numerical execution; publication build, AI facts, immutable staging, package approval and verified export. Source navigation and focused tests are in [developer handoff](dev.md).

`fast`, `standard`, and `full` are explicit human authorization/profile choices. `start` binds the approved tier to the displayed problem hash and profile model/effort. These names do not themselves implement hard cost/token/deadline budgets or fixed route counts. Unsupported deadline/token/cost task limits fail explicitly; ordinary scoped work may continue while important scope, permission, or budget changes require a real decision.

## Recorded validation

[ACCEPTANCE.md](../ACCEPTANCE.md) records `accepted_basic_flow`, not a real competition run. Its inherited D5 evidence includes 58 product tests, 18 publication tests, and a reviewed XeLaTeX/BibTeX/Poppler synthetic demonstration. Those counts describe that recorded suite, not a newly run current suite. D6 reused it and recorded a clean-copy CLI smoke with synthetic decisions, a local command, staging and export; it did not rerun the full suite or rebuild PDFs.

This handoff documentation update does not add a pytest run, live provider/MCP/Exa/zvec-grep proof, rate-limit/resume exercise, PDF rebuild, or new visual review. Command wiring in source is an implementation fact; inherited acceptance and future target-host checks are distinct evidence.

## Recovery and capability limits

Git restores product development without historical Codex sessions. Personal cases and user-level provider/MCP/login configuration require separate backup or recreation. Back up the complete case including hidden `.runtime`, SQLite state/sidecars, receipts, tasks, logs, artifacts, human records, inputs, and publication files. SQLite does not reconstruct the provider's complete conversation.

Runtime records contain absolute workspace and event/stderr paths and possibly extra write paths. Existing-case continuation needs the original absolute path; there is no rebase CLI. `resume` uses the saved provider session and cannot recreate unavailable history. Preserve old tasks/attempts/outputs and explicitly continue selected material in a new task/session when needed. See [setup](setup.md) and [developer handoff](dev.md); do not hand-edit SQLite to claim a migration.

Linux/WSL and configured local tools are required. PDF intake uses embedded text through `pypdf`; scanned PDF OCR/MinerU is external preprocessing, without an integrated MinerU SDK. XLSX intake uses `openpyxl` and does not calculate formulas. TeX/fonts/Poppler are host dependencies. New scientific figure schemas need task-specific renderers. Each real case must obtain and freeze applicable current competition/regional rules and use real human decisions and truthful AI adoption facts.

## Unresolved work

- Define and test explicit case-path migration while preserving task/attempt/artifact provenance.
- Provide safe fresh-session task replacement and coordinator dependency handling; current CLI has no in-place session replacement.
- Verify the actual target host/provider, authentication, MCP/tools, and provider-specific resume behavior when authorized.
- Add problem-specific figure renderers and evidence checks only when a real task requires them.

Update this page, matching Chinese documentation, and the owning module note with the actual check whenever behavior changes. A documentation change is not implementation or live-system validation.
