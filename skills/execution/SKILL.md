---
name: execution
description: Run a local mathematical experiment through the MathModel runtime and package traceable observations, metrics, checks, and figures. Use for numerical experiment requests, not for scheduling or publication-only restyling.
---

Use the runtime-backed execution API in `mathmodel_agent.execution`; do not start a
private subprocess, task queue, or per-seed worker system.

- Make every command argv explicit and case-relative inputs explicit. Use only the
  documented command placeholders from `docs/execution.md`.
- Use `formal` only after supplying a stable comparison-contract JSON. Preserve every
  planned instance, including failed or timed-out ones. Deterministic algorithms have
  `seed: null`.
- Treat a fresh algorithm launch as a new `experiment_run_id`. Do not call a receipt
  replay a scientific rerun.
- Write complete JSONL observations and figure provenance files before finalization.
  Do not infer `not_run` from missing output: only a task with no runtime attempt is
  `not_run`; otherwise preserve `unknown` or `partial` facts.
- Use metric recomputation and independent checks only where their method matches the
  recorded check type. A process rerun and an independent implementation are different
  claims.
- Keep raw input data read-only. A visual redraw does not modify a metric; a change to
  samples, aggregation, units, or numerical values needs a new experiment package.

Read [the execution contract](../../docs/modules/execution.md) before preparing a formal run.
