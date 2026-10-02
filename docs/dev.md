# Developer handoff without old sessions

This repository contains the product source, tests, contracts, and maintenance instructions needed to continue development without old Codex conversations. Restoring a personal modeling case is a separate operation; see [setup](setup.md).

## Maintenance entry and reading order

Read `AGENTS.md`, `PROJECT_MEMORY.md`, this file, [status](status.md), and [design](design.md), then the relevant note under `docs/modules/`. Inspect the current Git diff before editing. Current implementation takes precedence over historical milestone descriptions. Product documentation and product memory belong in this repository; personal cases remain outside it.

The tracked skill sources are `skills/*/SKILL.md`. `.codex/` and `.agents/` have no tracked product skill files. A clone must not rely on those local directories, a parent checkout, or old user-level instructions. Managed tasks receive explicitly selected materials and the runtime prompt; implicit project documents are disabled by `runtime/scheduler.py`.

## Minimum new-device development steps

1. Restore or clone the product repository, including `uv.lock`, and enter its root. Python requires 3.12 or newer; the process supervisor targets Linux/WSL.
2. Run `rtk uv sync --locked`, `rtk uv run mmagent --help`, and `rtk uv run mmagent doctor`. Doctor is a local diagnostic, not a provider login or live-model check.
3. Read the owning source, its immediate callers, and focused tests. Define the intended change and a bounded verification check before editing.
4. Use `uv`/`uv add` for Python, `bun` for optional Node tools, and `rtk` for shell commands. Missing TeX tools need resolving for publication work, not for every source edit.

## Source navigation and ownership

Source paths in the table start at `mathmodel_agent/`; test paths start at the repository root; durable state paths are relative to the case root.

| Owner | Interface and durable state | Focused checks |
| --- | --- | --- |
| CLI/config | `cli.py:build_parser/main/doctor`; `runtime/config.py:init_case/load_case_config`; `case.toml` | `tests/runtime/test_cli.py`, `tests/runtime/test_state.py`; CLI help |
| Runtime | `runtime/state.py:State`; `runtime/scheduler.py:Supervisor`; `runtime/provider.py`; `.runtime/state.sqlite`, task inputs/workspaces and attempt logs | `tests/runtime/test_state.py`, `tests/runtime/test_provider.py`, `tests/runtime/test_scheduler.py` |
| Immutable artifacts | `runtime/artifacts.py:publish_bundle/resolve_bundle`; bundles and receipts | `tests/runtime/test_artifacts.py` |
| Human control/coordination | `control.py:ask_human/record_human_decision/record_ai_adoption`; `workflow.py:Coordinator.poll`; human Markdown, `human/control.json`, `human/coordinator.json`, worker `RESULT.json` | `tests/control/test_control.py`, `tests/exploration/test_workflow.py` |
| Evidence | `evidence/intake.py`, `evidence/pool.py`, `evidence/freeze.py`; originals, extracted data, `knowledge/registry.json`, `freezes/` | `tests/evidence/test_intake.py`, `tests/evidence/test_pool_freeze.py` |
| Candidates/comparisons | `exploration.py:write_candidate/write_variant/create_comparison_contract/write_comparison_pack`; `candidates/`, `comparisons/` | `tests/exploration/test_exploration.py` |
| Numerical execution | `execution/worker.py:prepare_experiment/submit_experiment/run_experiment/finalize_experiment`; immutable run packages through runtime | `tests/execution/test_execution_flow.py` |
| Paper/export | `publication/pipeline.py:build_publication`; `publication/checks.py:record_visual_review`; `publication/ai_usage.py`, `publication/manifest.py`, `publication/cli.py`; build reports, staged packages and export | `tests/publication/test_manifest.py`, `tests/publication/test_ai_usage.py`; focused `tests/publication/test_pipeline.py` cases |

## What survives a system replacement

Git alone restores product development: source, tracked Markdown, tests, templates, examples, `pyproject.toml`, and `uv.lock`. It does not restore a personal case or local provider history. Recreate `.venv` with `uv sync --locked`; reconfigure host tools through doctor. Do not treat an old `.runtime` TeX supplement as a disposable cache if it is the only installed copy of required TeX packages.

Before replacing a system, stop its supervisor and writers, then back up the **whole case directory including hidden files**: `case.toml`, `.runtime/state.sqlite` and any SQLite WAL/SHM sidecars present, `.runtime/receipts`, `tasks/*/input`, `tasks/*/workspace`, `tasks/*/runtime-runs`, `artifacts/`, `human/`, `problem/`, `datasets/`, `sources/`, `knowledge/`, `freezes/`, `candidates/`, `comparisons/`, and paper/config/build/request files. Also preserve originals kept outside the case and exported submission packages. A lone database is neither a complete case backup nor a provider-conversation backup. Take a consistent stopped copy rather than copying an actively written database file alone.

The user separately owns Codex/provider profiles, authentication, MCP configuration/login, optional provider session history, fonts, and TeX/system tools. Restore or recreate them locally in a trusted environment. Never put secrets in Git, case TOML/JSON/Markdown, human answers, or chat. Product development remains possible even if all provider history was lost.

### Case path and session boundaries

`State` persists absolute task workspace and attempt event/stderr paths; policy snapshots can contain absolute extra write paths. There is **no case rebase/migration CLI**. Restore an existing case at its original absolute path for runtime continuation. A changed directory path can still allow reading files, but does not establish that serve, resume, AI-use collection, or commands referring to old paths work. If the original path cannot be restored, retain the old case as evidence and initialize a new case; explicitly copy/import required material through current APIs and document its origin. Decisions and ArtifactRefs do not automatically transfer to a new case. Do not rewrite SQLite paths by hand and claim a verified migration.

`mmagent resume CASE TASK` and coordinator polling use the saved provider session. They require that session to remain available to the configured provider/client. SQLite records observed IDs and attempts, not the provider's complete conversation. JSONL logs and worker outputs are useful evidence, but are not guaranteed to contain the entire original chat. A session ID alone cannot restore missing history on a fresh system; unknown-session/authentication failures must remain visible.

If history is unavailable, keep the old task, attempt records, logs, input snapshots, `RESULT.json`, artifacts, and human decisions. In the original-path case, submit a **new task with a distinct task ID**, a new provider session, explicitly selected saved inputs/results, and a prompt naming the old task and what remains unfinished. Do not erase the old session ID, fabricate successful attempts, repeatedly resume an unavailable session, or silently create a duplicate coordinator tree. The CLI has no command to replace a task's session in place. A coordinator's `wait_for` and fingerprint records continue to reference old task IDs; reassignment needs explicit coordination rather than assuming the new task satisfies those dependencies.

For an authorized coordinator, use the current `human ask-tier`/answer/decide and `start` commands. `start` checks the selected profile's model/effort and the problem hash against the approved tier object. Changed model/effort or problem text requires a new real decision; broader permission/budget changes must also be confirmed. Preserve valid existing decisions when their exact objects remain unchanged. Do not infer choices from lost chat or use a synthetic fixture as approval. A new process succeeding still does not prove scientific validity.

## Contracts and single-writer rules

`contracts.py` owns `ArtifactRef` (`artifact_id`, `sha256`) and atomic JSON replacement; it explicitly expects callers to provide single-writer ownership. Control and coordination use `control-v1` and `coordinator-v1`; exploration uses `candidate-v1`, `variant-v1`, `comparison-contract-v1`, and `comparison-pack-v1`; execution uses `execution-spec-v1` and `execution-run-v1`; publication requests/rules use `publication-request-v1` and `publication-rules-v1`. Evidence registry/freeze records are owned by the evidence module and do not share a universal versioned schema.

SQLite is the task/attempt authority, with WAL and transactions. Human/control, coordinator, and evidence JSON are separate domain records, not replacement task databases. Use one operator/writer for those file records and one supervisor per case; do not introduce parallel read-modify-write callers. The publisher serializes publication with `.runtime/publish.lock`, verifies hashes and file sets, and deduplicates submission receipts. That lock does not protect every domain JSON file. Published bundles and approved exact objects must remain fixed; a changed package needs new staging and approval.

## Make and verify a change

1. State the concrete behavior to change, its owner, and the focused test or input/output check. Preserve unrelated files and case-relative public contracts.
2. Make the smallest change. For changed contracts, document compatibility and migration limits before relying on old cases. Do not add a second scheduler, database, hidden auto-configurer, or file watcher.
3. Run the relevant checks from the table above, for example `rtk uv run pytest tests/runtime/test_state.py -q`, plus affected CLI help. Publication pipeline tests include a real XeLaTeX test: select specific unit cases when TeX/build verification is outside scope. Live provider/MCP calls, full suites, and paper rebuilds are explicit additional checks.
4. Update the corresponding English and Chinese guide/module pages, this handoff where ownership changes, and status with the actual validation performed. Separate source implementation, newly executed tests, and inherited acceptance evidence; do not relabel D5/D6 counts as a new run.
5. Record unresolved work and limitations in Markdown before ending the session. Review the diff for credentials, real case data, generated caches, and unintended changes.

Current follow-up gaps are an explicit case-path migration contract, safe fresh-session task replacement/dependency handling, target-host/provider resume verification, and task-specific renderers beyond the synthetic allocation example. None is implemented merely by documenting it. See [status](status.md) for accepted evidence and other capability limits.

## Fresh-session development prompt

```text
Read AGENTS.md, PROJECT_MEMORY.md, docs/dev.md, docs/status.md, docs/design.md and the relevant module note. Assume all previous Codex sessions are unavailable. Inspect the current Git diff and relevant source/callers/tests. Summarize current behavior, state owner, contracts and unresolved limits; make the smallest authorized change using rtk, uv/uv add and bun. Run only relevant verification and record its actual result in matching English/Chinese Markdown. Keep personal cases and credentials outside the release repository. For case recovery, retain old tasks/attempts and distinguish saved evidence from unavailable provider chat; do not invent approvals or claim unsupported path/session migration.
```
