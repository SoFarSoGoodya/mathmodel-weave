import json
from pathlib import Path
import subprocess
import sys
import time

from mathmodel_agent.runtime.scheduler import Supervisor
from mathmodel_agent.runtime.state import State
from mathmodel_agent.workflow import Coordinator, submit_coordinator


def _pump(supervisor, task_ids, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        supervisor.run_once()
        if all(supervisor.state.get_task(task_id)["state"] in {"succeeded", "failed", "paused", "cancelled"} for task_id in task_ids):
            return
        time.sleep(0.02)
    raise AssertionError("runtime tasks did not settle")


def test_coordinator_dispatches_once_then_resumes_same_session(case_root):
    payloads = [
        {"requests": [{"task_id": "child-command", "kind": "command", "argv": ["true"], "purpose": "offline child"}]},
        {},
    ]
    agent_calls = 0

    def factory(command, **kwargs):
        nonlocal agent_calls
        if command == ["true"]:
            return subprocess.Popen(command, **kwargs)
        payload = payloads[agent_calls]
        agent_calls += 1
        script = (
            "import json,pathlib; "
            f"pathlib.Path('RESULT.json').write_text(json.dumps({payload!r})); "
            "print(json.dumps({'type':'thread.started','thread_id':'coordinator-session'})); "
            "print(json.dumps({'type':'turn.completed'}))"
        )
        return subprocess.Popen([sys.executable, "-c", script], **kwargs)

    coordinator_id = submit_coordinator(case_root, task_id="coordinator", prompt="Coordinate offline test.")
    supervisor = Supervisor(case_root, process_factory=factory)
    _pump(supervisor, [coordinator_id])

    coordinator = Coordinator(case_root)
    first = coordinator.poll(coordinator_id)
    assert first["action"] == "waiting"
    assert first["submitted"] == ["child-command"]
    assert coordinator.poll(coordinator_id)["submitted"] == ["child-command"]
    _pump(supervisor, ["child-command"])

    resumed = coordinator.poll(coordinator_id)
    assert resumed["action"] == "resumed"
    _pump(supervisor, [coordinator_id])
    task = State(case_root).get_task(coordinator_id)
    assert task["retry_count"] == 0
    assert [run["mode"] for run in task["runs"]] == ["initial", "followup"]
    assert coordinator.poll(coordinator_id)["action"] == "final_result"
