# Runtime

`mmagent` is a Linux/WSL process supervisor, not a socket service. Each case has one SQLite
state store, immutable attempt logs, fixed task workspaces, and a single publication path.
Task success records process completion only; it does not assert scientific validity or human
approval.

## Case And Tasks

Create a case with `uv run mmagent init CASE`. Edit `CASE/case.toml` to select the two-slot
limit, sandbox policy, credential-free model profiles, and configured local tools. Provider
and authentication settings remain in the user's Codex configuration. They are inherited by
agent processes and are never copied into the case database or doctor output.

Submit a JSON file with `uv run mmagent submit CASE task.json`, then run
`uv run mmagent serve CASE`. A command task contains `kind: "command"` and an `argv` string
list. An agent task contains `kind: "agent"`, a `prompt`, and either a case profile name or
an explicit `model` plus `effort`. Both may
declare case-relative `inputs`; agent tasks may separately declare selected `instructions`
and `skills`. These selections are copied into `tasks/<id>/input/`. Processes always run in
`tasks/<id>/workspace/`.

Managed Codex invocations use JSONL output, `approval_policy=never`, the case sandbox,
`project_doc_max_bytes=0`, and the selected profile's model/effort. Resume-specific
overrides are placed after `resume`, as required by the supported CLI parser. The managed
prompt still supplies the rtk/uv/bun rules and exact-object human-decision rules when project
documents are disabled. No research root is added implicitly.

## State And Recovery

Task states are `queued`, `running`, `retry_wait`, `paused`, `succeeded`, `failed`, and
`cancelled`. Every host attempt has a separate `runtime-runs/<run-id>/events.jsonl` and
`stderr.log`, plus PID/process-group identity in SQLite. A final `turn.completed` with exit
code zero is success even when earlier JSONL events recorded a recovered reconnect. A final
`turn.failed`, missing completion, or nonzero exit remains failure.

Transient child failures resume the same observed Codex session immediately once. A second
failure waits at least 300 seconds and honors a longer valid `Retry-After`; a third pauses.
Main sessions get one immediate same-session retry. Authentication, configuration, timeout,
unknown-session, and non-transient failures do not automatically switch provider or session.
Retry waiting holds neither a process slot nor a database transaction.

`mmagent cancel` persists intent. The active supervisor sends SIGINT, then SIGTERM, then
SIGKILL to the process group if required. Restart reconciliation verifies Linux PID start
identity before signaling a surviving process, adopts no arbitrary process, accepts a complete
agent event log as success, and pauses a dead command whose exit status was lost.

## Coordinator Output

An agent can leave `workspace/RESULT.json` with `requests`, `wait_for`, and `deliverables`.
Requests are returned as ordinary task specs for the coordinator to submit. `wait_for` lists
task IDs; after those results are available, `State.resume(task_id, followup=...)` continues
the same session as a normal follow-up, not a failure retry. Each deliverable names a staging
directory inside the workspace and a stable submission ID. Successful task completion sends
those bundles through `publish_bundle` and records receipts in RESULT state.

## Publication

`publish_bundle(case_root, staging, submission_id, ...)` rejects symlinks, path escape,
reserved temporary names, and files that change during inspection/copy. It hashes files in
1 MiB chunks, writes `bundle.json`, and atomically renames a same-filesystem temporary bundle.
The publication lock serializes both CLI and domain callers. Replaying the same submission ID
with identical content returns the original receipt; changed content raises
`SubmissionConflict`. `resolve_bundle` verifies the ArtifactRef, manifest, declared file set,
sizes, and hashes by default.

## Diagnostics

`uv run mmagent doctor [CASE]` performs local checks for Codex, uv, bun, rtk, XeLaTeX,
latexmk, BibTeX, CTeX/xeCJK/zhnumber, Noto CJK fonts, and Poppler tools, plus configured case
tools. It performs no live provider request and does not inspect or print credentials.
