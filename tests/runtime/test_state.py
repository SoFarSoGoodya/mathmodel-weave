import os
from pathlib import Path

import pytest

from mathmodel_agent.runtime.state import InvalidTaskState, State, TaskValidationError


def test_submit_creates_fixed_workspace_and_selected_inputs_only(case_root: Path):
    (case_root / "datasets" / "chosen.csv").write_text("x\n1\n", encoding="utf-8")
    (case_root / "datasets" / "not-chosen.csv").write_text("secret\n", encoding="utf-8")
    state = State(case_root)

    task_id = state.submit(
        {
            "task_id": "agent-one",
            "kind": "agent",
            "prompt": "Analyze the selected data.",
            "purpose": "candidate analysis",
            "inputs": ["datasets/chosen.csv"],
        }
    )

    task_root = case_root / "tasks" / task_id
    assert (task_root / "workspace").is_dir()
    assert (task_root / "runtime-runs").is_dir()
    assert (task_root / "input" / "inputs" / "datasets" / "chosen.csv").is_file()
    assert not list((task_root / "input").rglob("not-chosen.csv"))
    task = state.get_task(task_id)
    assert task["state"] == "queued"
    assert task["spec"]["prompt_ref"] == "input/prompt.md"


def test_submit_rejects_escape_symlink_and_secret_env(case_root: Path):
    outside = case_root.parent / "outside.txt"
    outside.write_text("outside", encoding="utf-8")
    os.symlink(outside, case_root / "datasets" / "link.txt")
    state = State(case_root)

    with pytest.raises(TaskValidationError, match="escapes"):
        state.submit({"kind": "command", "argv": ["true"], "inputs": [str(outside)]})
    with pytest.raises(TaskValidationError, match="symlink"):
        state.submit({"kind": "command", "argv": ["true"], "inputs": ["datasets/link.txt"]})
    with pytest.raises(TaskValidationError, match="credential-like"):
        state.submit({"kind": "command", "argv": ["true"], "env": {"API_TOKEN": "nope"}})


def test_dependencies_and_normal_followup_are_explicit(case_root: Path):
    state = State(case_root)
    first = state.submit({"task_id": "first", "kind": "command", "argv": ["true"]})
    second = state.submit(
        {"task_id": "second", "kind": "command", "argv": ["true"], "depends_on": [first]}
    )
    assert [task["task_id"] for task in state.ready_tasks(state.clock())] == [first]
    with pytest.raises(TaskValidationError, match="unknown dependencies"):
        state.submit({"kind": "command", "argv": ["true"], "depends_on": ["missing"]})

    agent = state.submit({"task_id": "agent", "kind": "agent", "prompt": "work"})
    with pytest.raises(InvalidTaskState, match="already queued"):
        state.resume(agent, "continue")
    assert state.get_task(second)["state"] == "queued"


def test_agent_profile_and_policy_are_snapshotted(case_root: Path):
    state = State(case_root)
    task_id = state.submit({"kind": "agent", "prompt": "work"})
    case_toml = case_root / "case.toml"
    case_toml.write_text(
        case_toml.read_text(encoding="utf-8").replace("gpt-5.6-sol", "changed-model"),
        encoding="utf-8",
    )
    snapshot = state.get_task(task_id)["spec"]["profile_snapshot"]
    assert snapshot["model"] == "gpt-5.6-sol"
    assert snapshot["effort"] == "high"
    assert snapshot["sandbox"] == "workspace-write"

    inline = state.submit(
        {"task_id": "inline", "kind": "agent", "prompt": "work", "model": "gpt-inline", "effort": "medium"}
    )
    inline_task = state.get_task(inline)
    assert inline_task["profile"] is None
    assert inline_task["spec"]["profile_snapshot"]["model"] == "gpt-inline"
    with pytest.raises(TaskValidationError, match="not both"):
        state.submit(
            {"kind": "agent", "prompt": "work", "profile": "default", "model": "x", "effort": "low"}
        )
