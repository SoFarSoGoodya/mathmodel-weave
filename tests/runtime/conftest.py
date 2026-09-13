from pathlib import Path

import pytest

from mathmodel_agent.runtime.config import init_case


@pytest.fixture
def case_root(tmp_path: Path) -> Path:
    root = tmp_path / "case"
    init_case(root)
    return root


def pump(supervisor, task_ids, timeout=5):
    import time

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        supervisor.run_once()
        states = [supervisor.state.get_task(task_id)["state"] for task_id in task_ids]
        if all(state in {"succeeded", "failed", "paused", "cancelled"} for state in states):
            return states
        time.sleep(0.02)
    raise AssertionError(f"tasks did not finish: {states}")
