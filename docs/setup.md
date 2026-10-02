# Setup and system replacement

## Restore product development

Clone or restore this product repository and enter its root. The source requires Python 3.12 or newer; the runtime supervisor targets Linux/WSL. Python dependencies are managed by `uv` and the tracked `uv.lock`. Use `bun` for optional Node tools and `rtk` for routine shell commands. Do not copy an old virtual environment as the dependency installation method.

```text
rtk uv sync --locked
rtk uv run mmagent --help
rtk uv run mmagent doctor
```

Doctor checks local Codex, uv, bun, rtk, XeLaTeX/latexmk/BibTeX, CTeX/xeCJK/zhnumber, Noto CJK fonts and Poppler. `rtk uv run mmagent doctor CASE_DIR` also checks case configuration and configured tool executables. It does not log in, inspect credentials, contact a live provider, exercise MCP, verify model availability, or prove resume works. Missing publication dependencies can be addressed when publication work is needed; an inherited successful PDF does not establish that this host can rebuild it.

Codex/provider configuration, profiles, credentials and MCP login belong in the user's trusted local environment. The product does not install or rewrite global authentication/configuration. Recreate or securely restore them yourself; do not send secrets through chat or put them in Git, case TOML/JSON/Markdown, or human answers. Restore system fonts and TeX packages separately. A custom TeX tree containing required packages is a host dependency, not necessarily a disposable cache.

## Configure a new case

Use a separate case directory outside the release repository:

```text
rtk uv run mmagent init CASE_DIR
rtk uv run mmagent doctor CASE_DIR
```

Review `CASE_DIR/case.toml` against `config/case.example.toml`. Its current sections are runtime, policy, profiles and tools; unsupported keys fail. The example and initializer contain historical `gpt-5.6-terra`, `gpt-5.6-luna` and `gpt-5.6-sol` names, which do not guarantee availability on a new account. Set actual available model/effort values deliberately before managed work. Case profile names select settings; `codex_profile`, if used, names an existing user-level profile. Research tiers are human choices, not automatic model discovery or hard-budget enforcement.

Network access is false in the example/initializer. Do not silently enable it to repair missing tools or credentials; explain and confirm any important authorization/permission change. `doctor` is diagnostic and does not authorize research. Use the existing human tier/answer/decision flow; `start` checks the approved problem hash and profile model/effort. Changed model/effort or problem text needs a new genuine decision.

PDF intake uses `pypdf` embedded text; preprocess scanned PDFs externally with OCR/MinerU if needed and retain originals. There is no integrated MinerU SDK. XLSX intake uses `openpyxl` and does not calculate formulas. No preprocessing service token belongs in case files.

## Restore an existing modeling case

Git restores product source, tests and documentation, independently of old sessions. Personal cases require a separate consistent backup. Stop the supervisor/writers and preserve the complete case, including hidden `.runtime` SQLite state and any WAL/SHM sidecars, receipts, task inputs/workspaces/attempt logs, artifacts, human records, problem/data/source/evidence freezes, comparisons, requests, configuration, and paper/build files. Preserve external originals and exported packages too. Recreating a case from SQLite alone loses required material.

Runtime records store absolute workspace and events/stderr paths, and policy snapshots may contain absolute extra write paths. Restore the case at its original absolute path. There is no rebase CLI; a changed location is not a verified runtime migration. If the original path is unavailable, retain the old case as evidence, initialize a new case and explicitly import required material. Decisions and ArtifactRefs do not automatically transfer. Do not hand-edit the database to conceal this limit.

A saved provider session ID is not the conversation. `resume` and workflow polling need the original session to remain available to the current provider/client. If its history is lost, keep old tasks/attempts/logs/outputs and explicitly continue selected saved material in a new task with a new ID/session; do not erase or fabricate old records. In-place session replacement and dependency reassignment are not implemented. Complete procedure, state ownership, schemas and fresh-session prompts are in [developer handoff](dev.md); normal operation is in [guide](guide.md) and [CLI reference](cli.md).
