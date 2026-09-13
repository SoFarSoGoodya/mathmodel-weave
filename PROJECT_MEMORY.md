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
