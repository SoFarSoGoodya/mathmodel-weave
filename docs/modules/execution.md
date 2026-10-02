# Execution

`mathmodel_agent.execution` turns one batch algorithm command into one immutable run
package. It is for real local numerical runs. The bundled allocation data and all
generated values are **synthetic demonstrations, not competition output**.

## Flow

1. Build an `ExperimentRequest` dictionary and call `prepare_experiment(case, request)`.
2. Call `submit_experiment(case, prepared)`. It snapshots the selected code, config,
   inputs, comparison contract, and `uv.lock`; it then submits a normal `kind="command"`
   task through `runtime.state.State`.
3. Let `runtime.scheduler.Supervisor` execute that command, or use the synchronous
   `run_experiment(case, request)` convenience function.
4. Call `finalize_experiment(case, task_id)` when using the explicit path. It reads
   persisted runtime facts and complete observations, writes one `run_manifest.json`,
   and calls `runtime.artifacts.publish_bundle` once.

There is no execution-owned process runner, database, scheduler, task-per-seed loop,
or budget ledger. A rerun uses a new `experiment_run_id` and produces a new host
runtime attempt and receipt. Recalling `finalize_experiment` for the same completed
staging directory is only publisher receipt deduplication.

## Request Contract

The request is JSON-compatible. `code`, `config`, each input `path`, and
`comparison_contract` are case-relative regular files. A formal request requires a
comparison contract. `command` is an argv list; only these placeholders are expanded:

```python
{
    "class": "formal",  # prototype | formal | recompute
    "task_id": "allocation-formal",
    "experiment_run_id": "XR-allocation-formal",
    "purpose": "What decision this run informs.",
    "code": "demo/allocation.py",
    "config": "demo/allocation_config.json",
    "inputs": [{"id": "instances", "path": "datasets/instances.json"}],
    "comparison_contract": "demo/comparison_contract.json",
    "instances": [{"id": "case-a", "seed": None}],
    "command": ["uv", "run", "python", "{code}", "--config", "{config}",
                "--input", "{input:instances}", "--output", "{output_dir}"],
    "timeout_seconds": 120,
}
```

`{code}`, `{config}`, `{input:<id>}`, and `{output_dir}` are the complete placeholder
set. Arbitrary shell strings are not accepted. Deterministic algorithms use `seed:
None`; there is no invented repeat count.

The comparison contract is a stable JSON file with ordered `planned_instances`,
metric definitions (`name`, `field`, `unit`, `aggregation` of `mean` or `max`), and
optional independent numeric constraints:

```json
{
  "planned_instances": [{"id": "case-a", "seed": null}],
  "metrics": [{"name": "score", "field": "score", "aggregation": "mean", "unit": "points"}],
  "constraints": [{"name": "bound", "left_field": "score", "operator": "<=", "right_field": "known_bound"}]
}
```

The batch command writes `observations.jsonl` to its output directory. Every complete
line needs `instance_id` and `status` (`completed`, `failed`, or `timed_out`). Figure
producers may add `figures/figures.json`; each entry names an image, source data, plot
code, and display configuration. The allocation example is a concrete reference.

## Output Semantics

The published package contains `run_manifest.json`, actual copied code/config/inputs,
the frozen `uv.lock`, observations, recomputed `metrics.json`, check evidence, and
any declared figure files. The manifest keeps a science `experiment_run_id` distinct
from `runtime.runtime_run_id`, exact argv and attempt facts, every planned instance,
failure denominator, raw-observation metric definitions, figure provenance, checks,
and `cost: "unknown"` when costs are not observable.

`complete` means every planned instance completed and required checks passed.
`partial` preserves usable observations with incomplete coverage. `invalid` means a
required metric or independent constraint check failed. `not_run` is used only where
the persisted task has no runtime attempt. A command that started but left no reliable
complete observation is `unknown`. Invalid or half-written JSONL records are excluded
and called out in `issues`; they are never promoted into a manifest fact.

`metric_recompute` means deterministic recomputation in this module from the saved
observations. `independent_check` means a separately implemented field constraint
checker. A future `new_process_rerun` must be submitted as another runtime command and
another experiment run; a fresh process alone is not an independent implementation.

`redraw_figure(run_directory, display_config)` is display-only: it regenerates a PNG
from saved figure CSV data without touching `metrics.json` or `run_manifest.json`.
It must be used before freezing a package or into a separate publication derivative.
Changing samples, units, or metric aggregation is scientific evidence and requires a
new request/run, not a redraw.

## Reproducible Synthetic Run

From the repository root, explicitly run the demo only when needed; it is not a Windows-adaptation or startup check. POSIX shell:

```bash
MPLCONFIGDIR=/tmp/mmagent-mpl uv run python examples/experiment/allocation/run_demo.py /tmp/synthetic-allocation-case
```

Windows PowerShell equivalent:

```powershell
$env:MPLCONFIGDIR = Join-Path $env:TEMP 'mmagent-mpl'
rtk uv run python examples/experiment/allocation/run_demo.py (Join-Path $env:TEMP 'synthetic-allocation-case')
```

The result is a formal package under
`/tmp/synthetic-allocation-case/artifacts/bundle-*/run_manifest.json`, plus its
`demo-result.json` (on Windows, under the selected temporary case directory). The batch intentionally records two known-answer successes and
one deliberate failure: greedy mean value `16.5`, exhaustive mean value `19.5`, and a
failure denominator of `1/3`. It is deliberately unsuitable as competition evidence.
