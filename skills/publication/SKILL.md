---
name: publication
description: Build and review a Chinese XeLaTeX mathematical-modeling paper from a fixed selected result, evidence freeze, and formal execution manifest. Use for final paper narrative, result-backed figures, submission PDFs, or publication checks; do not use to change algorithms, samples, metrics, units, or human approval.
---

# Publication

Read the selected-result record, evidence freeze, formal run manifest, current rule config,
and available human adoption facts before drafting. Stop with a science revision when the
run identity, metric value/definition/unit, sample set, aggregation, adopted claim, or rule
binding conflicts. Display-only changes such as final size, typography, color, marker,
linestyle, hatch, legend, and caption may proceed without recomputing a Metric.

Create a short `paper_plan.md` that states what each section answers, the frozen evidence it
uses, the mathematical or visual role, and the conclusion boundary. Write one coherent TeX
source rather than concatenating agent fragments. Repeated result values must come from
`generated/results.tex`, not manual transcription.

Use execution-owned data and scripts for data figures. Match final insertion width, provide a
non-color encoding, and draw intervals only when the run defines them. When only an original
real image exists without data or a script, disclose that it cannot be redrawn. Never present
a conceptual illustration as measured data.

Build the electronic target with XeLaTeX, then check citations, placeholders, anonymity,
critical numbers, page/size rules, metadata, embedded fonts, and the text layer. Rasterize
every page and inspect all of them. Compilation alone leaves `visual_review_pending`;
`review_ready` requires explicit page-complete visual notes and is not human approval.

Use `mathmodel_agent.publication.build_publication(case_root, request)` for the deterministic
pipeline. See `docs/modules/publication.md` for the request fields, rule configuration, CLI hook, and
exact commands.
