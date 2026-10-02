# Runtime

`mmagent` is a Windows 11 and Linux/WSL process supervisor, not a socket service. Each case has one SQLite
state store, immutable attempt logs, fixed task workspaces, and a single publication path.
Task success records process completion only; it does not assert scientific validity or human
approval.

## Automatic host selection

There is one codebase and CLI, not separately selected product versions. Whether an operator
Codex conversation invokes the CLI or an advanced user runs `uv run mmagent` directly,
`runtime/platform.py` chooses host primitives deterministically using the running Python
interpreter's `os.name`. Native Windows Python selects `"nt"`; Python inside Linux/WSL
selects the POSIX branch. The Windows location of a WSL host does not change that choice.
The `sys_platform == 'win32'` dependency marker in `pyproject.toml` makes `uv sync --locked`
install `pywin32` only on Windows, and its imports occur only in Windows branches.
SQLite state, task schemas, CLI commands and human-decision contracts remain shared.
Codex need not choose a source version or make a model call to select the platform.

| Primitive / owning function | Windows (`os.name == "nt"`) | Linux/WSL (current non-Windows implementation) |
| --- | --- | --- |
| Publication lock / `publication_lock` | Single-byte `msvcrt` lock with blocking retry | `fcntl.flock` |
| PID identity / `process_start_ticks` | Process wait state and creation time through Win32 | Start ticks from `/proc/<pid>/stat` |
| Launch / `process_options`, `own_process` | Suspended process group, named Job Object, resume primary thread | New session / process group |
| Cancel / `signal_process_group` | Console break, then whole-job termination | SIGINT, SIGTERM, SIGKILL to the process group |
| Executable / `executable_command` | Resolve PATH/PATHEXT, task PATH and explicit relative paths | Pass argv to the existing subprocess path |
| Links / `is_link` | Reject symlinks and junctions | Reject symlinks |
| Fonts / `cli._font_check` | Fontconfig, then Windows font registry | Existing fontconfig check |

Host selection does not translate arbitrary task argv or shell syntax, install host tools,
change provider configuration, or migrate saved absolute paths. Use commands and tool builds
appropriate to the interpreter's host; [setup](../setup.md) documents both shells.

## Platform troubleshooting and maintenance

Start with `rtk uv run mmagent doctor [CASE]` and `rtk uv run mmagent status CASE TASK`.
Inspect the task's `error` and attempt records, then the corresponding
`CASE/tasks/<id>/runtime-runs/<run-id>/stderr.log` and `events.jsonl`; do not infer success
from a live PID alone. `.runtime/state.sqlite` owns task/attempt state and
`.runtime/publish.lock` owns publication serialization; do not hand-edit the database.

- `process_start`: check executable resolution and, on Windows, the logged Job Object or
  primary-thread error. The adapter cleans up a child when establishing ownership fails.
- `stale_command_run`: the exit status was lost; inspect saved outputs before explicit
  continuation. A PID alone is not a safe process identity.
- Link/path rejection: inspect symlinks, junctions and resolved case boundaries. Do not
  disable validation or require administrator access merely to bypass it.
- Missing fonts/TeX/Poppler: install the appropriate host dependency when publication is
  needed; `doctor` does not prove a PDF build or live provider session.

Source ownership and the focused test command are in [developer handoff](../dev.md);
actual Windows evidence and the Linux retest boundary are in [status](../status.md).
`tests/runtime/test_platform.py` covers native primitives and recovery, while the scheduler,
CLI, artifact and input tests cover their callers. These are local tests, not a modeling run.

## macOS boundary

Non-Windows does not mean that every Unix host is supported. macOS would currently enter
the POSIX branch, but `process_start_ticks` still reads Linux `/proc/<pid>/stat`, which
standard macOS does not provide. Returning no identity can make restart reconciliation
misclassify a surviving run. Working locks and signals alone do not establish full support.

A future port must add an explicit Darwin process-identity implementation (for example,
Apple's [libproc APIs](https://github.com/apple-oss-distributions/xnu/blob/main/libsyscall/wrappers/libproc/libproc.h)),
verify identity against PID reuse, surviving-run cancellation and restart recovery, and
check macOS tool/font discovery. No macOS adapter or hardware test is supplied by this
documentation update, and Windows/Linux absolute case paths are not automatically portable.

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

`mmagent cancel` persists intent. On Linux/WSL, the active supervisor sends SIGINT, then
SIGTERM, then SIGKILL to the process group. On Windows, it starts a new process group
suspended, assigns it to a named Job Object, then resumes the primary thread; descendants
cannot launch before ownership is established. It tries CTRL_BREAK_EVENT, then terminates
the whole job after a two-second grace period. Without a usable console, the break may be
unavailable and forced job termination still applies. Closing the job also ends descendants
when the root exits or the supervisor is killed. Ownership failures are recorded as
`process_start` errors and the suspended child is reaped.

Restart reconciliation checks Linux `/proc` start ticks or Windows process creation time
before signaling a surviving process; these saved identities are host-specific. Windows
reconciliation opens the job named by the run ID rather than killing unrelated processes.
It adopts no arbitrary process, accepts a complete agent event log as success, and pauses
a dead command whose exit status was lost. There is still one supervisor per case, and
no cross-system absolute-path migration is implied.

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
The publication lock serializes both CLI and domain callers using `fcntl.flock` on Linux/WSL
and a blocking retry of a one-byte `msvcrt` lock on Windows. The OS releases the lock when
its owning process exits. Windows junctions are rejected alongside symlinks in staging and
selected input trees. Replaying the same submission ID
with identical content returns the original receipt; changed content raises
`SubmissionConflict`. `resolve_bundle` verifies the ArtifactRef, manifest, declared file set,
sizes, and hashes by default.

## Diagnostics

`uv run mmagent doctor [CASE]` performs local checks for Codex, uv, bun, rtk, XeLaTeX,
latexmk, BibTeX, CTeX/xeCJK/zhnumber, Noto CJK fonts, and Poppler tools, plus configured case
tools. Windows executable lookup honors `PATH`/`PATHEXT`, including task-specific `PATH`
and explicit executable paths relative to the task workspace. Command output is decoded as
UTF-8 with replacement for undecodable bytes, and font checks can fall back to the Windows
font registry when fontconfig cannot find the requested family. It performs no live provider
request and does not inspect or print credentials.
