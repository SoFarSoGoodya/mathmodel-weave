# Developer Handoff

On a new device, read `AGENTS.md`, `docs/status.md`, and `docs/design.md`, then the module note
for the change. Historical chat and research sessions are optional.

Run `uv sync --locked` and `uv run mmagent doctor`. Keep credentials in user-level Codex/provider
configuration. Use `bun` for optional Node tooling and `rtk` for routine shell commands.

Code navigation: `cli.py` dispatches commands; `workflow.py`, `control.py`, and `contracts.py`
define coordination and gates; `runtime/` supervises processes and recovery; `evidence/` handles
PDF/XLSX intake and freezes; `exploration.py` stores candidates; `execution/` runs contracts and
checks; `publication/` builds papers and AI-use details. Tests mirror these areas.

Change workflow: inspect the owning module and focused tests, preserve schemas and case-relative
paths, make a small change, update docs for behavior changes, then run focused tests or CLI help.
Full paper builds and live providers are explicit checks, not defaults.

Runtime recovery preserves the observed provider session where possible and pauses after bounded
failures. SQLite state and logs resume a case; exact provider chat may require local Codex history.

New Codex handoff prompt:

```text
Read AGENTS.md, docs/status.md, docs/design.md, and the relevant module note. Summarize current
behavior and limits, inspect only relevant source/tests, preserve schemas, use uv/rtk/bun rules,
implement the smallest authorized change, and run focused verification. Keep case data outside
the release repository and modify only the authorized files.
```
