# User Guide

MathModel Weave keeps a problem, human decisions, evidence, experiments, and a reviewed paper package together in one case.

1. Open the product directory in Codex and ask it to read `AGENTS.md` and this guide.
2. Ask it to run `uv run mmagent doctor` and explain missing local tools.
3. Provide separate PDF/XLSX paths and review the extracted question text.
4. Explicitly choose `fast`, `standard`, or `full` before managed research.

The assistant runs deterministic commands and dispatches managed tasks. It stops for choices about interpretation, tier, route/result selection, AI disclosure, and final package approval. You may answer in chat or edit case human Markdown, then tell it to read the update. There is no resident chat service or automatic file watcher.

To continue later, ask Codex to read `AGENTS.md`, this guide, and case status. Case files are the source of truth; an old conversation or session ID is not required. PDF intake reads embedded text only, XLSX formulas are not calculated, and MinerU is optional external preprocessing rather than an integrated SDK.
