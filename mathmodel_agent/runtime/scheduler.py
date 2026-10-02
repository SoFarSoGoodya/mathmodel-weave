"""Two-slot local process supervisor with persistent attempts and same-session retry."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
import threading
import time
from typing import BinaryIO, Callable
import uuid

from .artifacts import publish_bundle
from .config import Profile
from .platform import executable_command, own_process, process_group, process_options, signal_process_group
from .provider import (
    attempt_succeeded,
    build_codex_command,
    diagnostic_text,
    parse_event_file,
    retry_decision,
)
from .state import State, process_identity_matches, process_start_ticks


@dataclass
class ActiveRun:
    task: dict
    run_id: str
    process: subprocess.Popen
    threads: tuple[threading.Thread, threading.Thread]
    events_path: Path
    stderr_path: Path
    started_at: float
    job: object | None = None
    termination_reason: str | None = None
    signal_stage: int = 0
    signal_deadline: float | None = None


class Supervisor:
    def __init__(
        self,
        case_root: str | Path,
        *,
        clock=time.time,
        sleeper=time.sleep,
        process_factory: Callable[..., subprocess.Popen] | None = None,
    ):
        self.clock = clock
        self.sleeper = sleeper
        self.state = State(case_root, clock=clock)
        self.config = self.state.config
        self.process_factory = process_factory or subprocess.Popen
        self.supervisor_id = uuid.uuid4().hex
        self.active: dict[str, ActiveRun] = {}
        self._stopping = False

    def run_once(self) -> int:
        now = self.clock()
        self.state.mark_blocked_dependencies()
        stale_slots = self._reconcile_stale(now)
        self._poll_active(now)
        available = max(0, self.config.local_slots - len(self.active) - stale_slots)
        if not self._stopping:
            for task in self.state.ready_tasks(now)[:available]:
                self._start(task, now)
        return self._work_count()

    def serve(self, *, poll_interval: float | None = None, stop_when_idle: bool = False) -> None:
        interval = self.config.poll_interval if poll_interval is None else poll_interval
        if interval <= 0:
            raise ValueError("poll_interval must be positive")
        try:
            while not self._stopping:
                work = self.run_once()
                if stop_when_idle and work == 0:
                    return
                self.sleeper(interval)
        finally:
            if self._stopping or self.active:
                self.shutdown()

    def shutdown(self) -> None:
        self._stopping = True
        now = self.clock()
        for active in self.active.values():
            if active.process.poll() is None:
                self._begin_termination(active, "supervisor_shutdown", now)
        deadline = time.monotonic() + 5
        while self.active and time.monotonic() < deadline:
            self._poll_active(self.clock())
            time.sleep(0.05)
        for active in list(self.active.values()):
            if active.process.poll() is None:
                self._signal(active, 3)
            try:
                active.process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                pass
            self._finish(active, active.process.poll(), self.clock())

    def request_stop(self) -> None:
        """Ask `serve` to stop and clean up its owned process groups."""
        self._stopping = True

    def _start(self, task: dict, now: float) -> None:
        run_id = uuid.uuid4().hex
        run_root = self.state.case_root / "tasks" / task["task_id"] / "runtime-runs" / run_id
        run_root.mkdir(parents=True)
        events_path = run_root / "events.jsonl"
        stderr_path = run_root / "stderr.log"
        events_path.touch()
        stderr_path.touch()
        workspace = Path(task["workspace"])
        if task["kind"] == "agent":
            snapshot = task["spec"]["profile_snapshot"]
            profile = Profile(
                task["profile"] or "inline",
                snapshot["model"],
                snapshot["effort"],
                snapshot["codex_profile"],
            )
            command = build_codex_command(
                self.config,
                profile,
                workspace,
                session_id=task["session_id"],
                sandbox=snapshot["sandbox"],
                allow_network=snapshot["allow_network"],
                extra_write_paths=(Path(item) for item in snapshot["extra_write_paths"]),
            )
        else:
            command = task["spec"]["argv"]
        run_record = self.state.start_run(
            task["task_id"], run_id, self.supervisor_id, command, events_path, stderr_path, now
        )
        prompt = run_record["prompt"]
        stdin = subprocess.PIPE if task["kind"] == "agent" else subprocess.DEVNULL
        environment = os.environ.copy()
        environment.update(task["spec"].get("env", {}))
        try:
            process = self.process_factory(
                executable_command(command, cwd=workspace, env=environment),
                cwd=workspace,
                env=environment,
                stdin=stdin,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                **process_options(),
            )
            job = own_process(process, run_id)
        except (OSError, RuntimeError) as exc:
            stderr_path.write_text(str(exc), encoding="utf-8")
            error = {"type": "process_start", "message": str(exc)}
            self.state.finish_run(
                task["task_id"], run_id, task_state="failed", run_status="failed",
                exit_code=None, diagnostics=error,
            )
            return
        self.state.set_run_process(
            run_id, process.pid, process_group(process.pid), process_start_ticks(process.pid)
        )
        stdout_thread = threading.Thread(
            target=self._capture_stdout,
            args=(process.stdout, events_path, task["kind"]),
            daemon=True,
        )
        stderr_thread = threading.Thread(
            target=self._capture_raw,
            args=(process.stderr, stderr_path),
            daemon=True,
        )
        stdout_thread.start()
        stderr_thread.start()
        if task["kind"] == "agent" and process.stdin is not None:
            managed_prompt = self._managed_prompt(task, prompt or task["spec"]["prompt"])
            try:
                process.stdin.write(managed_prompt.encode("utf-8"))
                process.stdin.close()
            except BrokenPipeError:
                pass
        self.active[run_id] = ActiveRun(
            task=task,
            run_id=run_id,
            process=process,
            threads=(stdout_thread, stderr_thread),
            events_path=events_path,
            stderr_path=stderr_path,
            started_at=now,
            job=job,
        )

    def _poll_active(self, now: float) -> None:
        for run_id, active in list(self.active.items()):
            summary = parse_event_file(active.events_path)
            if summary.session_id and summary.session_id != active.task.get("session_id"):
                active.task["session_id"] = summary.session_id
                self.state.set_session(active.task["task_id"], run_id, summary.session_id)
            current = self.state.get_task(active.task["task_id"])
            if current["cancel_requested"] and active.termination_reason is None:
                self._begin_termination(active, "cancelled", now)
            timeout = active.task["spec"]["timeout_seconds"]
            if now - active.started_at >= timeout and active.termination_reason is None:
                self._begin_termination(active, "timeout", now)
            if active.termination_reason and active.process.poll() is None:
                self._advance_termination(active, now)
            code = active.process.poll()
            if code is not None:
                self._finish(active, code, now)

    def _finish(self, active: ActiveRun, exit_code: int | None, now: float) -> None:
        if active.job is not None:
            active.job.Close()
            active.job = None
        for thread in active.threads:
            thread.join(timeout=2)
        summary = parse_event_file(active.events_path)
        if summary.session_id:
            active.task["session_id"] = summary.session_id
            self.state.set_session(active.task["task_id"], active.run_id, summary.session_id)
        stderr = active.stderr_path.read_text(encoding="utf-8", errors="replace") if active.stderr_path.exists() else ""
        text = diagnostic_text(summary, stderr)
        if active.termination_reason:
            if active.termination_reason == "cancelled":
                state = "cancelled"
            elif active.termination_reason == "supervisor_shutdown":
                state = "paused"
            else:
                state = "failed"
            error = {"type": active.termination_reason, "message": active.termination_reason.replace("_", " ")}
            self.state.finish_run(
                active.task["task_id"], active.run_id, task_state=state, run_status=state,
                exit_code=exit_code, diagnostics=error,
            )
        elif active.task["kind"] == "command":
            if exit_code == 0:
                try:
                    result = self._load_result(active)
                except (ValueError, OSError) as exc:
                    error = {"type": "invalid_result", "message": str(exc)}
                    self.state.finish_run(
                        active.task["task_id"], active.run_id, task_state="failed",
                        run_status="failed", exit_code=exit_code, diagnostics=error,
                    )
                else:
                    self.state.finish_run(
                        active.task["task_id"], active.run_id, task_state="succeeded",
                        run_status="succeeded", exit_code=exit_code, diagnostics=None, result=result,
                    )
            else:
                error = {"type": "command_failed", "message": text or f"exit code {exit_code}"}
                self.state.finish_run(
                    active.task["task_id"], active.run_id, task_state="failed",
                    run_status="failed", exit_code=exit_code, diagnostics=error,
                )
        elif attempt_succeeded(exit_code, summary):
            try:
                result = self._load_result(active)
            except (ValueError, OSError) as exc:
                error = {"type": "invalid_result", "message": str(exc)}
                self.state.finish_run(
                    active.task["task_id"], active.run_id, task_state="failed",
                    run_status="failed", exit_code=exit_code, diagnostics=error,
                )
            else:
                self.state.finish_run(
                    active.task["task_id"], active.run_id, task_state="succeeded",
                    run_status="succeeded", exit_code=exit_code, diagnostics=None, result=result,
                )
        else:
            self._finish_agent_failure(active, exit_code, text, now)
        self.active.pop(active.run_id, None)

    def _finish_agent_failure(self, active: ActiveRun, exit_code: int | None, text: str, now: float) -> None:
        task = self.state.get_task(active.task["task_id"])
        error = {
            "type": "provider_failure",
            "message": text or f"Codex exited {exit_code} without a completed turn",
        }
        can_retry, delay = retry_decision(task["role"], task["retry_count"], error["message"], now)
        if can_retry and task["session_id"]:
            self.state.schedule_retry(
                task["task_id"], active.run_id, exit_code=exit_code, diagnostics=error,
                next_run_at=now + delay, retry_count=task["retry_count"] + 1,
            )
        else:
            if can_retry and not task["session_id"]:
                error["reason"] = "provider session ID was not observed; same-session retry is impossible"
            elif not can_retry:
                error["reason"] = "failure is terminal or automatic retry policy is exhausted"
            self.state.finish_run(
                task["task_id"], active.run_id, task_state="paused", run_status="failed",
                exit_code=exit_code, diagnostics=error,
            )

    def _load_result(self, active: ActiveRun) -> dict | None:
        return self._load_result_for(active.task, active.run_id)

    def _load_result_for(self, task: dict, run_id: str) -> dict | None:
        result_path = Path(task["workspace"]) / "RESULT.json"
        if not result_path.exists():
            return None
        raw = json.loads(result_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("RESULT.json must contain an object")
        requests = raw.get("requests", [])
        wait_for = raw.get("wait_for", [])
        deliverables = raw.get("deliverables", [])
        if not isinstance(requests, list) or not all(isinstance(item, dict) and item.get("kind") in {"agent", "command"} for item in requests):
            raise ValueError("RESULT.json requests must be task spec objects")
        if not isinstance(wait_for, list) or not all(isinstance(item, str) for item in wait_for):
            raise ValueError("RESULT.json wait_for must be a task ID list")
        if not isinstance(deliverables, list):
            raise ValueError("RESULT.json deliverables must be a list")
        receipts = []
        workspace = Path(task["workspace"]).resolve()
        for item in deliverables:
            if not isinstance(item, dict) or not isinstance(item.get("staging"), str) or not isinstance(item.get("submission_id"), str):
                raise ValueError("each deliverable needs staging and submission_id strings")
            staging = (workspace / item["staging"]).resolve()
            if not staging.is_relative_to(workspace):
                raise ValueError("deliverable staging escapes task workspace")
            receipts.append(
                publish_bundle(
                    self.state.case_root, staging, item["submission_id"],
                    task_id=task["task_id"], runtime_run_id=run_id,
                )
            )
        if receipts:
            raw["receipts"] = receipts
        return raw

    def _reconcile_stale(self, now: float) -> int:
        occupied = 0
        for run in self.state.running_records():
            if run["run_id"] in self.active:
                continue
            alive = process_identity_matches(run["pid"], run["pid_start_ticks"])
            timed_out = now - run["started_at"] >= run["spec"].get("timeout_seconds", 7200)
            summary = parse_event_file(run["events_path"])
            if summary.session_id and summary.session_id != run["task_session_id"]:
                self.state.set_session(run["task_id"], run["run_id"], summary.session_id)
                run["task_session_id"] = summary.session_id
            if alive:
                occupied += 1
                if (run["cancel_requested"] or timed_out) and run["pgid"]:
                    reference = run["task_updated_at"] if run["cancel_requested"] else run["started_at"] + run["spec"].get("timeout_seconds", 7200)
                    stage = 3 if now - reference >= 4 else 2
                    signal_process_group(run["pgid"], stage, run_id=run["run_id"])
                continue
            stderr_path = Path(run["stderr_path"])
            stderr = stderr_path.read_text(encoding="utf-8", errors="replace") if stderr_path.exists() else ""
            message = diagnostic_text(summary, stderr)
            if run["cancel_requested"]:
                self.state.finish_run(
                    run["task_id"], run["run_id"], task_state="cancelled", run_status="cancelled",
                    exit_code=None, diagnostics={"type": "cancelled", "message": "cancelled during restart reconciliation"},
                )
            elif run["kind"] == "agent" and summary.completed:
                try:
                    result = self._load_result_for(run, run["run_id"])
                except (ValueError, OSError) as exc:
                    self.state.finish_run(
                        run["task_id"], run["run_id"], task_state="failed", run_status="failed",
                        exit_code=None, diagnostics={"type": "invalid_result", "message": str(exc)},
                    )
                else:
                    self.state.finish_run(
                        run["task_id"], run["run_id"], task_state="succeeded", run_status="succeeded",
                        exit_code=None, diagnostics=None, result=result,
                    )
            elif timed_out:
                self.state.finish_run(
                    run["task_id"], run["run_id"], task_state="failed", run_status="failed",
                    exit_code=None, diagnostics={"type": "timeout", "message": "task timeout elapsed during restart reconciliation"},
                )
            elif run["kind"] == "agent":
                error = {"type": "stale_provider_run", "message": message or "provider process ended before reconciliation"}
                can_retry, delay = retry_decision(run["role"], run["retry_count"], error["message"], now)
                if can_retry and run["task_session_id"]:
                    self.state.schedule_retry(
                        run["task_id"], run["run_id"], exit_code=None, diagnostics=error,
                        next_run_at=now + delay, retry_count=run["retry_count"] + 1,
                    )
                else:
                    self.state.finish_run(
                        run["task_id"], run["run_id"], task_state="paused", run_status="unknown",
                        exit_code=None, diagnostics=error,
                    )
            else:
                self.state.finish_run(
                    run["task_id"], run["run_id"], task_state="paused", run_status="unknown",
                    exit_code=None,
                    diagnostics={"type": "stale_command_run", "message": "command exit status was lost on supervisor restart"},
                )
        return occupied

    def _begin_termination(self, active: ActiveRun, reason: str, now: float) -> None:
        active.termination_reason = reason
        active.signal_stage = 1
        active.signal_deadline = now + 2
        self._signal(active, 1)

    def _advance_termination(self, active: ActiveRun, now: float) -> None:
        if active.signal_deadline is None or now < active.signal_deadline:
            return
        if active.signal_stage == 1:
            self._signal(active, 2)
            active.signal_stage = 2
            active.signal_deadline = now + 2
        elif active.signal_stage == 2:
            self._signal(active, 3)
            active.signal_stage = 3
            active.signal_deadline = None

    @staticmethod
    def _signal(active: ActiveRun, stage: int) -> None:
        signal_process_group(active.process.pid, stage, job=active.job)

    @staticmethod
    def _capture_raw(source: BinaryIO | None, destination: Path) -> None:
        if source is None:
            destination.touch()
            return
        with destination.open("ab", buffering=0) as output:
            while True:
                block = source.read(65536)
                if not block:
                    return
                output.write(block)

    @staticmethod
    def _capture_stdout(source: BinaryIO | None, destination: Path, kind: str) -> None:
        if source is None:
            destination.touch()
            return
        with destination.open("ab", buffering=0) as output:
            if kind == "agent":
                while True:
                    block = source.read(65536)
                    if not block:
                        return
                    output.write(block)
            else:
                for line in iter(source.readline, b""):
                    event = {
                        "type": "command.stdout",
                        "text": line.decode("utf-8", errors="replace").rstrip("\r\n"),
                    }
                    output.write(json.dumps(event, ensure_ascii=False).encode("utf-8") + b"\n")

    @staticmethod
    def _managed_prompt(task: dict, prompt: str) -> str:
        selected = task["spec"].get("selected_material", [])
        paths = "\n".join(f"- ../{item['path']}" for item in selected) or "- none"
        purpose = task.get("purpose") or task["spec"].get("purpose") or "Complete the submitted task."
        return (
            "Managed MathModel Agent task. Work only in the current task workspace. "
            "Use only the explicitly selected material listed below; do not scan parent research directories.\n\n"
            "Tool rules: prefix shell commands with rtk; use uv/uv add for Python and bun for Node. "
            "Do not invent human decisions. Authorized ordinary internal work may proceed without repeated gates; "
            "formal route, result, fusion, and final package choices require the recorded exact-object decision.\n\n"
            f"Purpose: {purpose}\nSelected material:\n{paths}\n\nTask prompt:\n{prompt}\n"
        )

    def _work_count(self) -> int:
        return sum(
            task["state"] in {"queued", "running", "retry_wait"}
            for task in self.state.list_tasks()
        )
