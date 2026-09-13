# Contributing

Read `AGENTS.md`, `docs/dev.md`, and `docs/status.md` before changing code. Keep changes small and
case-relative paths/schema contracts stable. Python dependencies use `uv`; optional Node tooling
uses `bun`; routine shell commands use `rtk`.

Run focused tests for the module you changed and a CLI help or smoke check. Do not commit
credentials, real competition cases, session databases, runtime caches, or generated temporary
directories.
