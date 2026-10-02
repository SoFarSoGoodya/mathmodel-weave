import json
import os
from pathlib import Path
import subprocess
import sys
import time

from mathmodel_agent.runtime.scheduler import Supervisor
from mathmodel_agent.runtime.state import State, process_start_ticks



def pump(supervisor, task_ids, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        supervisor.run_once()
        states = [supervisor.state.get_task(task_id)["state"] for task_id in task_ids]
        if all(state in {"succeeded", "failed", "paused", "cancelled"} for state in states):
            return states
        time.sleep(0.02)
    raise AssertionError(f"tasks did not finish: {states}")


def test_real_commands_run_in_parallel_with_truthful_logs(case_root: Path):
    state = State(case_root)
    script = (
        "import pathlib,time,sys; "
        "print('started', flush=True); print('diagnostic', file=sys.stderr, flush=True); "
        "time.sleep(.45); pathlib.Path('done.txt').write_text('done')"
    )
    ids = [
        state.submit({"task_id": f"parallel-{index}", "kind": "command", "argv": [sys.executable, "-c", script]})
        for index in range(2)
    ]
    supervisor = Supervisor(case_root)
    started = time.monotonic()
    assert pump(supervisor, ids) == ["succeeded", "succeeded"]
    elapsed = time.monotonic() - started
    assert elapsed < 0.85
    tasks = [state.get_task(task_id) for task_id in ids]
    assert abs(tasks[0]["runs"][0]["started_at"] - tasks[1]["runs"][0]["started_at"]) < 0.2
    for task in tasks:
        run = task["runs"][0]
        events = Path(run["events_path"]).read_text(encoding="utf-8")
        assert json.loads(events.splitlines()[0]) == {"type": "command.stdout", "text": "started"}
        assert "diagnostic" in Path(run["stderr_path"]).read_text(encoding="utf-8")
        assert Path(task["workspace"], "done.txt").is_file()


def test_agent_success_after_transient_diagnostic_does_not_retry(case_root: Path):
    state = State(case_root)
    task_id = state.submit({"task_id": "recovered", "kind": "agent", "prompt": "work"})

    def factory(_command, **kwargs):
        script = (
            "import sys; print('{\"type\":\"thread.started\",\"thread_id\":\"session-x\"}'); "
            "print('{\"type\":\"error\",\"message\":\"Reconnecting after stream disconnected\"}'); "
            "print('{\"type\":\"turn.completed\"}'); sys.stdout.flush()"
        )
        return subprocess.Popen([sys.executable, "-c", script], **kwargs)

    supervisor = Supervisor(case_root, process_factory=factory)
    assert pump(supervisor, [task_id]) == ["succeeded"]
    task = state.get_task(task_id)
    assert task["session_id"] == "session-x"
    assert len(task["runs"]) == 1
    assert "Reconnecting" in Path(task["runs"][0]["events_path"]).read_text(encoding="utf-8")


def test_child_retry_uses_injected_clock_and_releases_slot(case_root: Path):
    class Clock:
        value = 100.0

        def __call__(self):
            return self.value

    clock = Clock()
    state = State(case_root, clock=clock)
    task_id = state.submit({"task_id": "retry", "kind": "agent", "prompt": "work"})
    calls = 0

    def factory(_command, **kwargs):
        nonlocal calls
        calls += 1
        retry_after = "" if calls == 1 else " Retry-After: 360"
        script = (
            "import sys; print('{\"type\":\"thread.started\",\"thread_id\":\"session-r\"}'); "
            f"print('{{\"type\":\"error\",\"message\":\"stream disconnected{retry_after}\"}}'); "
            "sys.stdout.flush(); raise SystemExit(1)"
        )
        return subprocess.Popen([sys.executable, "-c", script], **kwargs)

    supervisor = Supervisor(case_root, clock=clock, sleeper=lambda _: None, process_factory=factory)
    deadline = time.monotonic() + 3
    while calls < 2 and time.monotonic() < deadline:
        supervisor.run_once()
        time.sleep(0.02)
    while state.get_task(task_id)["state"] == "running" and time.monotonic() < deadline:
        supervisor.run_once()
        time.sleep(0.02)
    task = state.get_task(task_id)
    assert calls == 2
    assert task["state"] == "retry_wait"
    assert task["next_run_at"] == 460.0
    assert not supervisor.active

    clock.value = 460.0
    assert pump(supervisor, [task_id]) == ["paused"]
    assert len(state.get_task(task_id)["runs"]) == 3


def test_cancel_terminates_real_process_group(case_root: Path):
    state = State(case_root)
    script = (
        "import pathlib,subprocess,sys,time; "
        "p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)']); pathlib.Path('child.pid').write_text(str(p.pid)); "
        "pathlib.Path('ready').write_text('yes'); time.sleep(30)"
    )
    task_id = state.submit(
        {"task_id": "cancel-me", "kind": "command", "argv": [sys.executable, "-c", script]}
    )
    supervisor = Supervisor(case_root)
    deadline = time.monotonic() + 3
    ready = case_root / "tasks" / task_id / "workspace" / "ready"
    while not ready.exists() and time.monotonic() < deadline:
        supervisor.run_once()
        time.sleep(0.02)
    assert ready.exists()
    child_pid = int((ready.parent / "child.pid").read_text())
    state.cancel(task_id)
    assert pump(supervisor, [task_id]) == ["cancelled"]
    deadline = time.monotonic() + 2
    while process_start_ticks(child_pid) is not None and time.monotonic() < deadline:
        time.sleep(0.02)
    assert process_start_ticks(child_pid) is None


def test_same_session_followup_is_not_failure_retry(case_root: Path):
    state = State(case_root)
    task_id = state.submit({"task_id": "followup", "kind": "agent", "prompt": "first"})
    commands = []
    calls = 0

    def factory(command, **kwargs):
        nonlocal calls
        calls += 1
        commands.append(command)
        session = "print('{\"type\":\"thread.started\",\"thread_id\":\"same-session\"}');" if calls == 1 else ""
        script = (
            "import pathlib,sys; data=sys.stdin.read(); "
            f"pathlib.Path('prompt-{calls}.txt').write_text(data); {session} "
            "print('{\"type\":\"turn.completed\"}'); sys.stdout.flush()"
        )
        return subprocess.Popen([sys.executable, "-c", script], **kwargs)

    supervisor = Supervisor(case_root, process_factory=factory)
    assert pump(supervisor, [task_id]) == ["succeeded"]
    state.resume(task_id, followup="use delivered child results")
    assert pump(supervisor, [task_id]) == ["succeeded"]
    task = state.get_task(task_id)
    assert task["retry_count"] == 0
    assert [run["mode"] for run in task["runs"]] == ["initial", "followup"]
    assert commands[1].index('sandbox_mode="workspace-write"') > commands[1].index("resume")
    assert commands[1][-2:] == ["same-session", "-"]
    assert "use delivered child results" in Path(task["workspace"], "prompt-2.txt").read_text()


def test_result_contract_publishes_deliverable(case_root: Path):
    state = State(case_root)
    payload = {
        "requests": [{"kind": "command", "argv": ["true"]}],
        "wait_for": ["future-task"],
        "deliverables": [{"staging": "ready", "submission_id": "coordinator-result"}],
    }
    script = (
        "import json,pathlib; pathlib.Path('ready').mkdir(); "
        "pathlib.Path('ready/result.txt').write_text('answer'); "
        f"pathlib.Path('RESULT.json').write_text(json.dumps({payload!r}))"
    )
    task_id = state.submit(
        {"task_id": "coordinator", "kind": "command", "argv": [sys.executable, "-c", script]}
    )
    supervisor = Supervisor(case_root)
    assert pump(supervisor, [task_id]) == ["succeeded"]
    result = state.get_task(task_id)["result"]
    assert result["requests"][0]["kind"] == "command"
    assert result["wait_for"] == ["future-task"]
    assert result["receipts"][0]["submission_id"] == "coordinator-result"


def test_restart_reconciliation_accepts_completed_agent_log(case_root: Path):
    state = State(case_root)
    task_id = state.submit({"task_id": "stale", "kind": "agent", "prompt": "work"})
    run_root = case_root / "tasks" / task_id / "runtime-runs" / "stale-run"
    run_root.mkdir()
    events = run_root / "events.jsonl"
    stderr = run_root / "stderr.log"
    events.write_text(
        '{"type":"thread.started","thread_id":"stale-session"}\n'
        '{"type":"error","message":"Reconnecting"}\n'
        '{"type":"turn.completed"}\n',
        encoding="utf-8",
    )
    stderr.write_text("", encoding="utf-8")
    state.start_run(task_id, "stale-run", "dead-supervisor", ["codex"], events, stderr, state.clock())
    state.set_run_process("stale-run", 999999, 999999, 1)

    Supervisor(case_root).run_once()
    task = state.get_task(task_id)
    assert task["state"] == "succeeded"
    assert task["session_id"] == "stale-session"


def test_timeout_is_state_not_automatic_retry(case_root: Path):
    class Clock:
        value = 0.0

        def __call__(self):
            return self.value

    clock = Clock()
    state = State(case_root, clock=clock)
    task_id = state.submit(
        {"task_id": "timeout", "kind": "command", "argv": [sys.executable, "-c", "import time; time.sleep(30)"], "timeout_seconds": 5}
    )
    supervisor = Supervisor(case_root, clock=clock)
    supervisor.run_once()
    assert state.get_task(task_id)["state"] == "running"
    clock.value = 6
    deadline = time.monotonic() + 3
    while state.get_task(task_id)["state"] == "running" and time.monotonic() < deadline:
        supervisor.run_once()
        time.sleep(0.02)
    task = state.get_task(task_id)
    assert task["state"] == "failed"
    assert task["error"]["type"] == "timeout"


def test_ai_usage_export_uses_persisted_refs_and_usage(case_root: Path):
    state = State(case_root)
    task_id = state.submit(
        {"task_id": "usage", "kind": "agent", "prompt": "work", "purpose": "draft candidate"}
    )

    def factory(_command, **kwargs):
        script = (
            "print('{\"type\":\"thread.started\",\"thread_id\":\"usage-session\"}'); "
            "print('{\"type\":\"turn.completed\",\"usage\":{\"input_tokens\":12,\"output_tokens\":3}}')"
        )
        return subprocess.Popen([sys.executable, "-c", script], **kwargs)

    supervisor = Supervisor(case_root, process_factory=factory)
    assert pump(supervisor, [task_id]) == ["succeeded"]
    record = state.ai_usage_records()[0]
    assert record["purpose"] == "draft candidate"
    assert record["prompt_ref"] == "tasks/usage/input/prompt.md"
    assert record["runs"][0]["usage"] == {"input_tokens": 12, "output_tokens": 3}
    assert record["human_adoption"] is None
