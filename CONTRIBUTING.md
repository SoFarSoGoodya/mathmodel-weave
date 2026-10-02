# Contributing

Read `AGENTS.md`, [developer handoff](docs/dev.md) / [中文开发交接](docs/zh/dev.md), and [status](docs/status.md) / [中文状态](docs/zh/status.md) before changing code. Keep changes small and
case-relative paths/schema contracts stable. Python dependencies use `uv`; optional Node tooling
uses `bun`; routine shell commands use `rtk`.

Run focused tests for the module you changed and a CLI help or smoke check. Do not commit
credentials, real competition cases, session databases, runtime caches, or generated temporary
directories.

For behavior changes, update the corresponding English and Chinese guide/module documentation with equal detail. Record actual checks and unresolved limits; inherited acceptance is not a new test run. Product maintenance does not require starting a research case or recovering old Codex conversations.
