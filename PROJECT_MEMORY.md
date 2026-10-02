# Project Memory

## Scope

- This repository is the only final product and publication-document root.
- Maintain `LICENSE`, third-party notices, publication constraints, and product-level memory here.
- Personal case and runtime directories are separate from the release package. Do not add or synchronize license documents there for personal work.

## Document extraction

- Current product intake uses `pypdf` for embedded PDF text and `openpyxl` for XLSX.
- Scanned PDFs require external OCR or preprocessing. MinerU may be used externally, but this
  release has no in-product MinerU SDK adapter.
- Never store or transmit service tokens through Git, case files, Markdown, JSON, or chat.
- XLSX remains on the deterministic `openpyxl` intake and validation path.

## Session-independent maintenance

- Product development must be recoverable from tracked Markdown and source without any old Codex session. Start with `AGENTS.md`, [English developer handoff](docs/dev.md) / [中文开发交接](docs/zh/dev.md), and [English status](docs/status.md) / [中文状态](docs/zh/status.md).
- Current source ownership, focused verification, unresolved work, and new-session prompts belong in those handoff/status pages; do not use remembered chat as an implementation or approval record.
- Git source recovery and personal-case recovery are different. Complete case backups, absolute runtime path constraints, and unavailable provider-history handling are documented in `docs/setup.md` and `docs/zh/setup.md`. SQLite is not a complete provider-conversation backup.
- Maintain English and Chinese behavior documentation together. Label inherited acceptance evidence separately from checks actually run for a change.
