# Setup

From the product root:

```text
uv sync --locked
uv run mmagent doctor
```

Python dependencies are managed by `uv` and `uv.lock`. Use `bun` for optional Node tooling and
`rtk` for routine shell commands. The doctor checks Codex, uv, bun, rtk, XeLaTeX/latexmk/BibTeX,
CTeX/xeCJK, CJK fonts, Poppler, and configured case tools.

PDF intake uses `pypdf`; XLSX intake uses `openpyxl`. For scanned PDFs, preprocess externally
(OCR or MinerU if desired) and retain the original. This release has no in-product MinerU adapter.
Provider credentials and model profiles stay in the user's Codex configuration; case TOML never
stores secrets. See `config/case.example.toml`.
