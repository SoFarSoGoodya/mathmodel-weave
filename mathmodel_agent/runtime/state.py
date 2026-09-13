"""SQLite-backed canonical task and process-attempt state."""

from __future__ import annotations

from collections.abc import Mapping
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import time
from typing import Any
import uuid

from .config import load_case_config


TASK_STATES = {"queued", "running", "retry_wait", "paused", "succeeded", "failed", "cancelled"}
TERMINAL_STATES = {"succeeded", "failed", "cancelled"}
TASK_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,95}\Z")


class TaskValidationError(ValueError):
    pass


class TaskNotFound(KeyError):
    pass


class InvalidTaskState(RuntimeError):
    pass


class State:
    def __init__(self, case_root: str | Path, *, clock=time.time):
        self.config = load_case_config(case_root)
        self.case_root = self.config.case_root
        self.clock = clock
        self.runtime_root = self.case_root / ".runtime"
        self.runtime_root.mkdir(parents=True, exist_ok=True)
        self.database_path = self.runtime_root / "state.sqlite"
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                PRAGMA journal_mode = WAL;
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    role TEXT NOT NULL,
                    profile TEXT,
                    purpose TEXT,
                    state TEXT NOT NULL,
                    spec_json TEXT NOT NULL,
                    workspace TEXT NOT NULL,
                    session_id TEXT,
                    current_run_id TEXT,
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    followup_count INTEGER NOT NULL DEFAULT 0,
                    pending_prompt TEXT,
                    pending_mode TEXT,
                    next_run_at REAL,
                    cancel_requested INTEGER NOT NULL DEFAULT 0,
                    error_json TEXT,
                    result_json TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL REFERENCES tasks(task_id),
                    attempt_no INTEGER NOT NULL,
                    mode TEXT NOT NULL,
                    status TEXT NOT NULL,
                    supervisor_id TEXT NOT NULL,
                    pid INTEGER,
                    pgid INTEGER,
                    pid_start_ticks INTEGER,
                    started_at REAL NOT NULL,
                    ended_at REAL,
                    exit_code INTEGER,
                    events_path TEXT NOT NULL,
                    stderr_path TEXT NOT NULL,
                    command_json TEXT NOT NULL,
                    session_id TEXT,
                    diagnostics_json TEXT,
                    UNIQUE(task_id, attempt_no)
                );
                CREATE INDEX IF NOT EXISTS runs_task_idx ON runs(task_id, attempt_no);
                CREATE TABLE IF NOT EXISTS receipts (
                    submission_id TEXT PRIMARY KEY,
                    content_id TEXT NOT NULL,
                    receipt_json TEXT NOT NULL,
                    created_at REAL NOT NULL
                );
                """
            )

    def submit(self, spec: Mapping[str, object]) -> str:
        normalized, sources = self._validate_spec(spec)
        task_id = normalized["task_id"]
        with self._connect() as connection:
            if connection.execute("SELECT 1 FROM tasks WHERE task_id = ?", (task_id,)).fetchone():
                raise TaskValidationError(f"task already exists: {task_id}")
            dependencies = normalized.get("depends_on", [])
            if dependencies:
                found = {
                    row[0]
                    for row in connection.execute(
                        f"SELECT task_id FROM tasks WHERE task_id IN ({','.join('?' for _ in dependencies)})",
                        dependencies,
                    )
                }
                missing = sorted(set(dependencies) - found)
                if missing:
                    raise TaskValidationError(f"unknown dependencies: {', '.join(missing)}")

        task_root = self.case_root / "tasks" / task_id
        if task_root.exists():
            raise TaskValidationError(f"task directory already exists: {task_root}")
        input_root = task_root / "input"
        workspace = task_root / "workspace"
        runs = task_root / "runtime-runs"
        input_root.mkdir(parents=True)
        workspace.mkdir()
        runs.mkdir()
        try:
            copied = []
            for category, source, relative in sources:
                destination = input_root / category / relative
                self._copy_selected(source, destination)
                copied.append(
                    {
                        "category": category,
                        "source": source.relative_to(self.case_root).as_posix(),
                        "path": destination.relative_to(task_root).as_posix(),
                    }
                )
            if normalized["kind"] == "agent":
                prompt_path = input_root / "prompt.md"
                prompt_path.write_text(normalized["prompt"], encoding="utf-8")
                normalized["prompt_ref"] = "input/prompt.md"
            normalized["selected_material"] = copied
            now = self.clock()
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO tasks(
                        task_id, kind, role, profile, purpose, state, spec_json, workspace,
                        pending_prompt, pending_mode, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, 'queued', ?, ?, ?, 'initial', ?, ?)
                    """,
                    (
                        task_id,
                        normalized["kind"],
                        normalized["role"],
                        normalized.get("profile"),
                        normalized.get("purpose"),
                        json.dumps(normalized, ensure_ascii=False, sort_keys=True),
                        str(workspace),
                        normalized.get("prompt"),
                        now,
                        now,
                    ),
                )
        except BaseException:
            shutil.rmtree(task_root, ignore_errors=True)
            raise
        return task_id

    def get_task(self, task_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
            if row is None:
                raise TaskNotFound(task_id)
            run_rows = connection.execute(
                "SELECT * FROM runs WHERE task_id = ? ORDER BY attempt_no", (task_id,)
            ).fetchall()
        task = self._task_dict(row)
        task["runs"] = [self._run_dict(item) for item in run_rows]
        return task

    def list_tasks(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM tasks ORDER BY created_at, task_id").fetchall()
        return [self._task_dict(row) for row in rows]

    def ai_usage_records(self) -> list[dict[str, Any]]:
        """Export recorded AI-use facts without reading user provider/auth configuration."""
        from .provider import parse_event_file

        records = []
        for task in self.list_tasks():
            if task["kind"] != "agent":
                continue
            full = self.get_task(task["task_id"])
            snapshot = task["spec"]["profile_snapshot"]
            runs = []
            for run in full["runs"]:
                summary = parse_event_file(run["events_path"])
                runs.append(
                    {
                        "run_id": run["run_id"],
                        "mode": run["mode"],
                        "status": run["status"],
                        "started_at": run["started_at"],
                        "ended_at": run["ended_at"],
                        "exit_code": run["exit_code"],
                        "events_ref": Path(run["events_path"]).relative_to(self.case_root).as_posix(),
                        "stderr_ref": Path(run["stderr_path"]).relative_to(self.case_root).as_posix(),
                        "usage": summary.usage,
                    }
                )
            result_path = Path(task["workspace"]) / "RESULT.json"
            records.append(
                {
                    "task_id": task["task_id"],
                    "tool": "Codex CLI",
                    "model": snapshot["model"],
                    "effort": snapshot["effort"],
                    "codex_profile": snapshot["codex_profile"],
                    "role": task["role"],
                    "purpose": task["purpose"],
                    "prompt_ref": f"tasks/{task['task_id']}/{task['spec']['prompt_ref']}",
                    "workspace_ref": Path(task["workspace"]).relative_to(self.case_root).as_posix(),
                    "session_id": task["session_id"],
                    "result_ref": result_path.relative_to(self.case_root).as_posix() if result_path.exists() else None,
                    "runs": runs,
                    "human_adoption": None,
                }
            )
        return records

    def resume(self, task_id: str, followup: str | None = None) -> None:
        now = self.clock()
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
            if row is None:
                raise TaskNotFound(task_id)
            if row["state"] == "running":
                raise InvalidTaskState("cannot resume a running task")
            if row["state"] == "queued":
                raise InvalidTaskState("task is already queued")
            if row["state"] == "cancelled":
                raise InvalidTaskState("cancelled tasks cannot be resumed")
            if row["kind"] == "agent":
                if not row["session_id"] and row["state"] != "queued":
                    raise InvalidTaskState("agent task has no provider session to resume")
                if followup is not None:
                    if not isinstance(followup, str) or not followup.strip():
                        raise TaskValidationError("followup must be non-empty text")
                    count = row["followup_count"] + 1
                    prompt_path = self.case_root / "tasks" / task_id / "input" / f"followup-{count}.md"
                    prompt_path.write_text(followup, encoding="utf-8")
                    mode = "followup"
                else:
                    count = row["followup_count"]
                    followup = (
                        "Continue the interrupted task in this original session using saved work. "
                        "Do not restart completed work; finish the requested deliverables and verification."
                    )
                    mode = "manual_resume"
                connection.execute(
                    """
                    UPDATE tasks SET state='queued', pending_prompt=?, pending_mode=?, next_run_at=NULL,
                        retry_count=0, followup_count=?, cancel_requested=0, error_json=NULL,
                        updated_at=? WHERE task_id=?
                    """,
                    (followup, mode, count, now, task_id),
                )
            else:
                if followup is not None:
                    raise TaskValidationError("command tasks do not accept followup text")
                connection.execute(
                    """
                    UPDATE tasks SET state='queued', pending_mode='manual_resume', next_run_at=NULL,
                        retry_count=0, cancel_requested=0, error_json=NULL, updated_at=?
                    WHERE task_id=?
                    """,
                    (now, task_id),
                )

    def cancel(self, task_id: str) -> None:
        now = self.clock()
        with self._connect() as connection:
            row = connection.execute("SELECT state FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
            if row is None:
                raise TaskNotFound(task_id)
            if row["state"] in TERMINAL_STATES:
                return
            if row["state"] == "running":
                connection.execute(
                    "UPDATE tasks SET cancel_requested=1, updated_at=? WHERE task_id=?",
                    (now, task_id),
                )
            else:
                connection.execute(
                    """
                    UPDATE tasks SET state='cancelled', cancel_requested=1, next_run_at=NULL,
                        error_json=?, updated_at=? WHERE task_id=?
                    """,
                    (json.dumps({"type": "cancelled", "message": "cancelled by user"}), now, task_id),
                )

    def ready_tasks(self, now: float) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM tasks
                WHERE state IN ('queued', 'retry_wait') AND cancel_requested=0
                  AND (next_run_at IS NULL OR next_run_at <= ?)
                ORDER BY created_at, task_id
                """,
                (now,),
            ).fetchall()
            states = {row["task_id"]: row["state"] for row in connection.execute("SELECT task_id, state FROM tasks")}
        ready = []
        for row in rows:
            task = self._task_dict(row)
            dependencies = task["spec"].get("depends_on", [])
            if all(states.get(item) == "succeeded" for item in dependencies):
                ready.append(task)
        return ready

    def mark_blocked_dependencies(self) -> None:
        now = self.clock()
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT task_id, spec_json FROM tasks WHERE state IN ('queued', 'retry_wait')"
            ).fetchall()
            states = {row["task_id"]: row["state"] for row in connection.execute("SELECT task_id, state FROM tasks")}
            for row in rows:
                dependencies = json.loads(row["spec_json"]).get("depends_on", [])
                blocked = [item for item in dependencies if states.get(item) in {"failed", "cancelled", "paused"}]
                if blocked:
                    error = {"type": "dependency_blocked", "dependencies": blocked}
                    connection.execute(
                        "UPDATE tasks SET state='paused', error_json=?, updated_at=? WHERE task_id=?",
                        (json.dumps(error, sort_keys=True), now, row["task_id"]),
                    )

    def start_run(
        self,
        task_id: str,
        run_id: str,
        supervisor_id: str,
        command: list[str],
        events_path: Path,
        stderr_path: Path,
        now: float,
    ) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
            if row is None:
                raise TaskNotFound(task_id)
            if row["state"] not in {"queued", "retry_wait"} or row["cancel_requested"]:
                raise InvalidTaskState(f"task is not startable: {row['state']}")
            attempt_no = connection.execute(
                "SELECT COALESCE(MAX(attempt_no), 0) + 1 FROM runs WHERE task_id=?", (task_id,)
            ).fetchone()[0]
            mode = row["pending_mode"] or "initial"
            connection.execute(
                """
                INSERT INTO runs(
                    run_id, task_id, attempt_no, mode, status, supervisor_id, started_at,
                    events_path, stderr_path, command_json
                ) VALUES (?, ?, ?, ?, 'starting', ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    task_id,
                    attempt_no,
                    mode,
                    supervisor_id,
                    now,
                    str(events_path),
                    str(stderr_path),
                    json.dumps(command),
                ),
            )
            connection.execute(
                """
                UPDATE tasks SET state='running', current_run_id=?, next_run_at=NULL,
                    updated_at=? WHERE task_id=?
                """,
                (run_id, now, task_id),
            )
        return {"attempt_no": attempt_no, "mode": mode, "prompt": row["pending_prompt"]}

    def set_run_process(self, run_id: str, pid: int, pgid: int, start_ticks: int | None) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE runs SET status='running', pid=?, pgid=?, pid_start_ticks=? WHERE run_id=?",
                (pid, pgid, start_ticks, run_id),
            )

    def set_session(self, task_id: str, run_id: str, session_id: str) -> None:
        with self._connect() as connection:
            connection.execute("UPDATE tasks SET session_id=?, updated_at=? WHERE task_id=?", (session_id, self.clock(), task_id))
            connection.execute("UPDATE runs SET session_id=? WHERE run_id=?", (session_id, run_id))

    def finish_run(
        self,
        task_id: str,
        run_id: str,
        *,
        task_state: str,
        run_status: str,
        exit_code: int | None,
        diagnostics: dict[str, Any] | None,
        result: dict[str, Any] | None = None,
        next_run_at: float | None = None,
        retry_count: int | None = None,
    ) -> None:
        if task_state not in TASK_STATES:
            raise ValueError(task_state)
        now = self.clock()
        error_json = json.dumps(diagnostics, ensure_ascii=False, sort_keys=True) if diagnostics else None
        result_json = json.dumps(result, ensure_ascii=False, sort_keys=True) if result is not None else None
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE runs SET status=?, ended_at=?, exit_code=?, diagnostics_json=?
                WHERE run_id=?
                """,
                (run_status, now, exit_code, error_json, run_id),
            )
            fields = [
                "state=?",
                "current_run_id=NULL",
                "error_json=?",
                "next_run_at=?",
                "pending_prompt=NULL",
                "pending_mode=NULL",
                "updated_at=?",
            ]
            values: list[Any] = [task_state, error_json, next_run_at, now]
            if result_json is not None:
                fields.append("result_json=?")
                values.append(result_json)
            if retry_count is not None:
                fields.append("retry_count=?")
                values.append(retry_count)
            values.append(task_id)
            connection.execute(f"UPDATE tasks SET {', '.join(fields)} WHERE task_id=?", values)

    def schedule_retry(
        self,
        task_id: str,
        run_id: str,
        *,
        exit_code: int | None,
        diagnostics: dict[str, Any],
        next_run_at: float,
        retry_count: int,
    ) -> None:
        now = self.clock()
        error_json = json.dumps(diagnostics, ensure_ascii=False, sort_keys=True)
        prompt = (
            "Continue the interrupted task using this original conversation and saved work. "
            "Do not restart exploration. Finish the agreed deliverables and verification."
        )
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE runs SET status='failed', ended_at=?, exit_code=?, diagnostics_json=?
                WHERE run_id=?
                """,
                (now, exit_code, error_json, run_id),
            )
            connection.execute(
                """
                UPDATE tasks SET state='retry_wait', current_run_id=NULL, error_json=?,
                    next_run_at=?, retry_count=?, pending_prompt=?, pending_mode='failure_resume',
                    updated_at=? WHERE task_id=?
                """,
                (error_json, next_run_at, retry_count, prompt, now, task_id),
            )

    def running_records(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT r.*, t.kind, t.role, t.retry_count, t.session_id AS task_session_id,
                       t.cancel_requested, t.workspace, t.spec_json, t.updated_at AS task_updated_at
                FROM runs r JOIN tasks t ON t.task_id=r.task_id
                WHERE r.status IN ('starting', 'running') AND t.state='running'
                ORDER BY r.started_at
                """
            ).fetchall()
        return [self._run_dict(row) | {"kind": row["kind"], "role": row["role"], "retry_count": row["retry_count"], "task_session_id": row["task_session_id"], "cancel_requested": bool(row["cancel_requested"]), "workspace": row["workspace"], "spec": json.loads(row["spec_json"]), "task_updated_at": row["task_updated_at"]} for row in rows]

    def receipt(self, submission_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT receipt_json FROM receipts WHERE submission_id=?", (submission_id,)
            ).fetchone()
        return json.loads(row[0]) if row else None

    def record_receipt(self, submission_id: str, content_id: str, receipt: dict[str, Any]) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO receipts VALUES (?, ?, ?, ?)",
                (submission_id, content_id, json.dumps(receipt, ensure_ascii=False, sort_keys=True), self.clock()),
            )

    def _validate_spec(self, spec: Mapping[str, object]) -> tuple[dict[str, Any], list[tuple[str, Path, Path]]]:
        if not isinstance(spec, Mapping):
            raise TaskValidationError("task spec must be a mapping")
        normalized = dict(spec)
        unsupported_limits = sorted(
            set(normalized)
            & {"deadline", "deadline_at", "deadline_seconds", "token_limit", "cost_limit"}
        )
        if unsupported_limits:
            raise TaskValidationError(
                "unsupported task limits: " + ", ".join(unsupported_limits)
            )
        kind = normalized.get("kind")
        if kind not in {"agent", "command"}:
            raise TaskValidationError("kind must be 'agent' or 'command'")
        task_id = normalized.get("task_id") or uuid.uuid4().hex
        if not isinstance(task_id, str) or not TASK_ID_PATTERN.fullmatch(task_id):
            raise TaskValidationError("task_id contains unsupported characters")
        normalized["task_id"] = task_id
        role = normalized.get("role", "child")
        if role not in {"child", "main"}:
            raise TaskValidationError("role must be 'child' or 'main'")
        normalized["role"] = role
        timeout = normalized.get("timeout_seconds", 7200)
        if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or timeout <= 0:
            raise TaskValidationError("timeout_seconds must be positive")
        normalized["timeout_seconds"] = float(timeout)
        depends_on = normalized.get("depends_on", [])
        if not isinstance(depends_on, list) or not all(isinstance(item, str) for item in depends_on):
            raise TaskValidationError("depends_on must be a task ID list")
        if task_id in depends_on or len(depends_on) != len(set(depends_on)):
            raise TaskValidationError("depends_on contains a cycle or duplicate")
        normalized["depends_on"] = depends_on
        env = normalized.get("env", {})
        if not isinstance(env, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in env.items()):
            raise TaskValidationError("env must map strings to strings")
        secret_names = [
            key for key in env
            if re.search(r"(?:KEY|TOKEN|SECRET|PASSWORD|AUTH|CREDENTIAL)", key, re.IGNORECASE)
        ]
        if secret_names:
            raise TaskValidationError(
                "task env may not persist credential-like values; use inherited provider auth: "
                + ", ".join(sorted(secret_names))
            )
        normalized["env"] = env
        purpose = normalized.get("purpose")
        if purpose is not None and not isinstance(purpose, str):
            raise TaskValidationError("purpose must be text")

        if kind == "agent":
            inline_model = normalized.get("model")
            inline_effort = normalized.get("effort")
            if inline_model is not None or inline_effort is not None:
                if "profile" in normalized:
                    raise TaskValidationError("provide profile or model/effort, not both")
                if not isinstance(inline_model, str) or not inline_model:
                    raise TaskValidationError("model must be a non-empty string")
                if not isinstance(inline_effort, str) or not inline_effort:
                    raise TaskValidationError("effort must be a non-empty string")
                profile_name = None
                model = inline_model
                effort = inline_effort
                codex_profile = None
            else:
                profile_name = normalized.get("profile", "default")
                if not isinstance(profile_name, str):
                    raise TaskValidationError("profile must be a string")
                profile = self.config.profile(profile_name)
                model = profile.model
                effort = profile.effort
                codex_profile = profile.codex_profile
            normalized["profile"] = profile_name
            normalized["profile_snapshot"] = {
                "model": model,
                "effort": effort,
                "codex_profile": codex_profile,
                "sandbox": self.config.sandbox,
                "allow_network": self.config.allow_network,
                "extra_write_paths": [str(path) for path in self.config.allowed_extra_write_paths],
            }
            prompt = normalized.get("prompt")
            prompt_file = normalized.get("prompt_file")
            if prompt is not None and prompt_file is not None:
                raise TaskValidationError("provide prompt or prompt_file, not both")
            if prompt_file is not None:
                source = self._selected_source(prompt_file)
                if not source.is_file():
                    raise TaskValidationError("prompt_file must be a regular file")
                prompt = source.read_text(encoding="utf-8")
            if not isinstance(prompt, str) or not prompt.strip():
                raise TaskValidationError("agent prompt must be non-empty text")
            normalized["prompt"] = prompt
            normalized.pop("prompt_file", None)
        else:
            argv = normalized.get("argv")
            if not isinstance(argv, list) or not argv or not all(isinstance(item, str) and item for item in argv):
                raise TaskValidationError("command argv must be a non-empty string list")

        sources: list[tuple[str, Path, Path]] = []
        destinations: set[tuple[str, Path]] = set()
        for category in ("inputs", "instructions", "skills"):
            entries = normalized.get(category, [])
            if not isinstance(entries, list):
                raise TaskValidationError(f"{category} must be a list")
            for entry in entries:
                if isinstance(entry, str):
                    value = entry
                    destination = Path(value)
                elif isinstance(entry, dict) and isinstance(entry.get("source"), str):
                    value = entry["source"]
                    destination_value = entry.get("destination", value)
                    if not isinstance(destination_value, str):
                        raise TaskValidationError(f"{category} destination must be a string")
                    destination = Path(destination_value)
                else:
                    raise TaskValidationError(f"invalid {category} entry")
                if destination.is_absolute() or ".." in destination.parts:
                    raise TaskValidationError(f"{category} destination escapes task input")
                if not destination.parts or destination == Path("."):
                    raise TaskValidationError(f"{category} destination must name a path")
                destination_key = (category, destination)
                if destination_key in destinations:
                    raise TaskValidationError(f"duplicate {category} destination: {destination}")
                destinations.add(destination_key)
                source = self._selected_source(value)
                sources.append((category, source, destination))
        return normalized, sources

    def _selected_source(self, value: object) -> Path:
        if not isinstance(value, str) or not value:
            raise TaskValidationError("selected source must be a non-empty case-relative path")
        relative = Path(value)
        if relative.is_absolute():
            raise TaskValidationError("selected source must be case-relative")
        source = self.case_root / relative
        if source.is_symlink() or not source.exists():
            raise TaskValidationError(f"selected source is missing or a symlink: {value}")
        resolved = source.resolve()
        if not resolved.is_relative_to(self.case_root):
            raise TaskValidationError(f"selected source escapes case root: {value}")
        return resolved

    def _copy_selected(self, source: Path, destination: Path) -> None:
        if source.is_file():
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            return
        destination.mkdir(parents=True, exist_ok=True)
        for root, directories, files in os.walk(source, followlinks=False):
            root_path = Path(root)
            for name in directories + files:
                if (root_path / name).is_symlink():
                    raise TaskValidationError(f"selected directory contains symlink: {root_path / name}")
            relative = root_path.relative_to(source)
            (destination / relative).mkdir(parents=True, exist_ok=True)
            for name in files:
                shutil.copy2(root_path / name, destination / relative / name)

    @staticmethod
    def _task_dict(row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        result["spec"] = json.loads(result.pop("spec_json"))
        result["error"] = json.loads(result.pop("error_json")) if result.get("error_json") else None
        result.pop("error_json", None)
        result["result"] = json.loads(result.pop("result_json")) if result.get("result_json") else None
        result.pop("result_json", None)
        result["cancel_requested"] = bool(result["cancel_requested"])
        return result

    @staticmethod
    def _run_dict(row: sqlite3.Row) -> dict[str, Any]:
        available = set(row.keys())
        keys = (
            "run_id", "task_id", "attempt_no", "mode", "status", "supervisor_id",
            "pid", "pgid", "pid_start_ticks", "started_at", "ended_at", "exit_code",
            "events_path", "stderr_path", "session_id",
        )
        result = {key: row[key] for key in keys if key in available}
        if "command_json" in available:
            result["command"] = json.loads(row["command_json"])
        if "diagnostics_json" in available:
            result["diagnostics"] = json.loads(row["diagnostics_json"]) if row["diagnostics_json"] else None
        return result


def process_start_ticks(pid: int) -> int | None:
    try:
        fields = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8").split()
        return int(fields[21])
    except (FileNotFoundError, IndexError, ValueError, PermissionError):
        return None


def process_identity_matches(pid: int | None, start_ticks: int | None) -> bool:
    if pid is None or start_ticks is None:
        return False
    return process_start_ticks(pid) == start_ticks
