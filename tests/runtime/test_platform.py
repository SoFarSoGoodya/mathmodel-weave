import json
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest

from mathmodel_agent.cli import _content_check, _font_check, _tool_check
from mathmodel_agent.publication.checks import run_checked
from mathmodel_agent.runtime.artifacts import publish_bundle
from mathmodel_agent.runtime.platform import executable_command, own_process, process_options, publication_lock
from mathmodel_agent.runtime.scheduler import Supervisor
from mathmodel_agent.runtime.state import State, process_identity_matches, process_start_ticks


def wait_for_file(path: Path, process: subprocess.Popen | None = None) -> None:
    deadline = time.monotonic() + 8
    while not path.exists() and time.monotonic() < deadline:
        if process is not None and process.poll() is not None:
            raise AssertionError(f"process exited before writing {path}: {process.returncode}")
        time.sleep(0.02)
    assert path.exists()


def wait_for_exit(pid: int) -> None:
    deadline = time.monotonic() + 5
    while process_start_ticks(pid) is not None and time.monotonic() < deadline:
        time.sleep(0.02)
    assert process_start_ticks(pid) is None


def test_process_identity_does_not_match_another_start_or_dead_process():
    process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        identity = process_start_ticks(process.pid)
        assert identity is not None
        assert process_identity_matches(process.pid, identity)
        assert not process_identity_matches(process.pid, identity + 1)
        assert not process_identity_matches(process.pid, None)
        process.terminate()
        process.wait(timeout=5)
        assert not process_identity_matches(process.pid, identity)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)


def test_publication_lock_serializes_processes_and_releases_after_crash(tmp_path: Path):
    lock_path = tmp_path / "publish.lock"
    acquired = tmp_path / "acquired"
    script = (
        "import pathlib,sys,time; "
        "from mathmodel_agent.runtime.platform import publication_lock; "
        "lock=publication_lock(pathlib.Path(sys.argv[1])); lock.__enter__(); "
        "pathlib.Path(sys.argv[2]).write_text('locked'); time.sleep(30)"
    )
    with publication_lock(lock_path):
        process = subprocess.Popen([sys.executable, "-c", script, str(lock_path), str(acquired)])
        try:
            time.sleep(0.2)
            assert process.poll() is None
            assert not acquired.exists()
        except BaseException:
            process.kill()
            process.wait(timeout=5)
            raise
    try:
        wait_for_file(acquired, process)
    finally:
        process.kill()
        process.wait(timeout=5)
    with publication_lock(lock_path):
        assert lock_path.exists()


def test_parallel_publication_returns_one_receipt(case_root: Path):
    staging = case_root / "paper" / "ready"
    staging.mkdir()
    (staging / "payload.txt").write_text("immutable", encoding="utf-8")
    script = (
        "import json,sys; from mathmodel_agent.runtime.artifacts import publish_bundle; "
        "print(json.dumps(publish_bundle(sys.argv[1],sys.argv[2],'concurrent')))"
    )
    processes = [
        subprocess.Popen([sys.executable, "-c", script, str(case_root), str(staging)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        for _ in range(3)
    ]
    try:
        receipts = []
        for process in processes:
            output, errors = process.communicate(timeout=10)
            assert process.returncode == 0, errors.decode("utf-8", errors="replace")
            receipts.append(json.loads(output))
        assert receipts[0] == receipts[1] == receipts[2]
        assert publish_bundle(case_root, staging, "concurrent") == receipts[0]
        assert len(list((case_root / "artifacts").glob("bundle-*"))) == 1
    finally:
        for process in processes:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)


def test_diagnostics_and_publication_commands_decode_utf8(tmp_path: Path):
    command = [sys.executable, "-c", "import sys; sys.stdout.buffer.write('中文诊断'.encode('utf-8'))"]
    assert _tool_check(command)["version"] == "中文诊断"
    assert _content_check(command) == {"available": True, "value": "中文诊断"}
    assert run_checked(command, cwd=tmp_path) == "中文诊断"
    assert not _tool_check([sys.executable, "-c", "raise SystemExit(1)"])["available"]


@pytest.mark.skipif(os.name != "nt", reason="Windows Job Object ownership")
def test_windows_job_closes_descendants_when_root_exits(case_root: Path):
    script = (
        "import pathlib,subprocess,sys; "
        "child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)']); "
        "pathlib.Path('child.pid').write_text(str(child.pid))"
    )
    state = State(case_root)
    task_id = state.submit({"task_id": "root-exits", "kind": "command", "argv": [sys.executable, "-c", script]})
    supervisor = Supervisor(case_root)
    try:
        supervisor.serve(stop_when_idle=True, poll_interval=0.02)
        assert state.get_task(task_id)["state"] == "succeeded"
        child_pid = int((Path(state.get_task(task_id)["workspace"]) / "child.pid").read_text())
        wait_for_exit(child_pid)
    finally:
        supervisor.shutdown()


@pytest.mark.skipif(os.name != "nt", reason="Windows Job Object ownership")
def test_windows_supervisor_crash_kills_owned_tree(case_root: Path, tmp_path: Path):
    state = State(case_root)
    child_script = (
        "import pathlib,subprocess,sys,time; "
        "child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)']); "
        "pathlib.Path('child.pid').write_text(str(child.pid)); time.sleep(30)"
    )
    task_id = state.submit({"task_id": "supervisor-crash", "kind": "command", "argv": [sys.executable, "-c", child_script]})
    ready = tmp_path / "supervisor.ready"
    owner_script = (
        "import pathlib,sys,time; from mathmodel_agent.runtime.scheduler import Supervisor; "
        "owner=Supervisor(sys.argv[1]); owner.run_once(); "
        "pathlib.Path(sys.argv[2]).write_text('ready'); time.sleep(30)"
    )
    owner = subprocess.Popen([sys.executable, "-c", owner_script, str(case_root), str(ready)])
    try:
        wait_for_file(ready, owner)
        task = state.get_task(task_id)
        assert task["state"] == "running"
        child_path = Path(task["workspace"]) / "child.pid"
        wait_for_file(child_path, owner)
        child_pid = int(child_path.read_text())
        root_pid = state.running_records()[0]["pid"]
        owner.kill()
        owner.wait(timeout=5)
        wait_for_exit(root_pid)
        wait_for_exit(child_pid)
        replacement = Supervisor(case_root)
        replacement.run_once()
        assert state.get_task(task_id)["state"] == "paused"
        assert state.get_task(task_id)["error"]["type"] == "stale_command_run"
    finally:
        if owner.poll() is None:
            owner.kill()
            owner.wait(timeout=5)


@pytest.mark.skipif(os.name != "nt", reason="Windows executable lookup")
def test_windows_resolves_executable_from_path():
    command = executable_command(["uv", "--version"])
    assert Path(command[0]).is_absolute()
    assert command[1:] == ["--version"]


@pytest.mark.skipif(os.name != "nt", reason="Windows font registry")
def test_windows_font_check_works_without_fontconfig(monkeypatch):
    monkeypatch.setattr("mathmodel_agent.cli._content_check", lambda command: {"available": False, "value": None})
    result = _font_check("Arial")
    assert result["available"]
    assert result["source"] == "windows-font-registry"


@pytest.mark.skipif(os.name != "nt", reason="Windows batch shim")
def test_windows_batch_shim_runs_from_path_with_spaces(tmp_path: Path, case_root: Path):
    shim_root = tmp_path / "tool with spaces"
    shim_root.mkdir()
    shim = shim_root / "tool.cmd"
    program = shim_root / "arguments.py"
    program.write_text("import json,sys; print(json.dumps(sys.argv[1:]))", encoding="utf-8")
    shim.write_text(f'@echo off\n"{sys.executable}" "%~dp0arguments.py" %*\n', encoding="utf-8")
    arguments = ["two words", "--version"]
    output = run_checked([str(shim), *arguments], cwd=tmp_path)
    assert json.loads(output) == arguments
    relative_output = run_checked([r".\tool.cmd", *arguments], cwd=shim_root)
    assert json.loads(relative_output) == arguments
    assert executable_command(["tool.cmd"], env={"PATH": str(shim_root)}) == [str(shim)]
    state = State(case_root)
    task_id = state.submit({"kind": "command", "argv": ["tool.cmd", *arguments], "env": {"PATH": str(shim_root)}})
    supervisor = Supervisor(case_root)
    try:
        supervisor.serve(stop_when_idle=True, poll_interval=0.02)
        assert state.get_task(task_id)["state"] == "succeeded"
    finally:
        supervisor.shutdown()


@pytest.mark.skipif(os.name != "nt", reason="Windows Job Object ownership")
def test_windows_job_assignment_failure_is_recorded_and_child_is_reaped(case_root: Path, monkeypatch):
    import win32job

    def reject_assignment(job, handle):
        raise RuntimeError("job assignment refused")

    monkeypatch.setattr(win32job, "AssignProcessToJobObject", reject_assignment)
    processes = []

    def factory(command, **kwargs):
        process = subprocess.Popen(command, **kwargs)
        processes.append(process)
        return process

    state = State(case_root)
    task_id = state.submit({"kind": "command", "argv": [sys.executable, "-c", "import time; time.sleep(30)"]})
    supervisor = Supervisor(case_root, process_factory=factory)
    supervisor.run_once()
    task = state.get_task(task_id)
    assert task["state"] == "failed"
    assert task["error"]["type"] == "process_start"
    assert "job assignment refused" in task["error"]["message"]
    assert processes[0].poll() is not None


@pytest.mark.skipif(os.name != "nt", reason="Windows termination escalation")
def test_windows_cancel_escalates_when_console_break_is_ignored(case_root: Path):
    script = (
        "import pathlib,signal,subprocess,sys,time; signal.signal(signal.SIGBREAK,signal.SIG_IGN); "
        "child=subprocess.Popen([sys.executable,'-c','import signal,time; signal.signal(signal.SIGBREAK,signal.SIG_IGN); time.sleep(30)']); "
        "pathlib.Path('child.pid').write_text(str(child.pid)); time.sleep(30)"
    )
    state = State(case_root)
    task_id = state.submit({"kind": "command", "argv": [sys.executable, "-c", script]})
    supervisor = Supervisor(case_root)
    try:
        supervisor.run_once()
        task = state.get_task(task_id)
        child_path = Path(task["workspace"]) / "child.pid"
        wait_for_file(child_path)
        child_pid = int(child_path.read_text())
        state.cancel(task_id)
        supervisor.run_once()
        active = next(iter(supervisor.active.values()))
        supervisor._poll_active(active.signal_deadline + 0.1)
        deadline = time.monotonic() + 5
        while state.get_task(task_id)["state"] == "running" and time.monotonic() < deadline:
            supervisor.run_once()
            time.sleep(0.02)
        assert state.get_task(task_id)["state"] == "cancelled"
        wait_for_exit(child_pid)
    finally:
        supervisor.shutdown()


@pytest.mark.skipif(os.name != "nt", reason="Windows reserved STILL_ACTIVE exit code")
def test_windows_exited_process_with_code_259_is_not_alive():
    process = subprocess.Popen([sys.executable, "-c", "raise SystemExit(259)"])
    assert process.wait(timeout=5) == 259
    assert process_start_ticks(process.pid) is None


@pytest.mark.skipif(os.name != "nt", reason="Windows surviving-job reconciliation")
def test_windows_reconciliation_cancels_a_verified_surviving_job(case_root: Path):
    import uuid

    state = State(case_root)
    script = (
        "import pathlib,subprocess,sys,time; "
        "child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)']); "
        "pathlib.Path('child.pid').write_text(str(child.pid)); time.sleep(30)"
    )
    command = [sys.executable, "-c", script]
    task_id = state.submit({"kind": "command", "argv": command})
    workspace = Path(state.get_task(task_id)["workspace"])
    run_id = uuid.uuid4().hex
    events, stderr = workspace / "events.jsonl", workspace / "stderr.log"
    state.start_run(task_id, run_id, "previous-owner", command, events, stderr, time.time())
    process = subprocess.Popen(command, cwd=workspace, **process_options())
    job = own_process(process, run_id)
    try:
        state.set_run_process(run_id, process.pid, process.pid, process_start_ticks(process.pid))
        child_path = workspace / "child.pid"
        wait_for_file(child_path, process)
        child_pid = int(child_path.read_text())
        state.cancel(task_id)
        replacement = Supervisor(case_root)
        replacement.run_once()
        process.wait(timeout=5)
        wait_for_exit(child_pid)
        replacement.run_once()
        assert state.get_task(task_id)["state"] == "cancelled"
    finally:
        job.Close()
        process.wait(timeout=5)
