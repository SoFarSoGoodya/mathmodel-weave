from pathlib import Path

from mathmodel_agent.runtime.config import load_case_config
from mathmodel_agent.runtime.provider import (
    attempt_succeeded,
    build_codex_command,
    parse_event_lines,
    retry_decision,
)


def test_completed_turn_supersedes_prior_transient_error():
    summary = parse_event_lines(
        [
            b'{"type":"thread.started","thread_id":"session-1"}\n',
            b'{"type":"error","message":"Reconnecting after stream disconnected"}\n',
            b'{"type":"item.completed","item":{"type":"agent_message","text":"done"}}\n',
            b'{"type":"turn.completed"}\n',
        ]
    )
    assert summary.session_id == "session-1"
    assert summary.diagnostics
    assert attempt_succeeded(0, summary)


def test_final_turn_failed_and_invalid_tail_are_terminal_failure():
    summary = parse_event_lines(
        [
            '{"type":"turn.completed"}',
            b'not-json\xff\n',
            '{"type":"turn.failed","error":{"message":"terminal"}}',
        ]
    )
    assert summary.terminal_turn == "turn.failed"
    assert summary.invalid_lines == 1
    assert not attempt_succeeded(0, summary)


def test_retry_policy_child_main_and_retry_after():
    assert retry_decision("child", 0, "stream disconnected", 100) == (True, 0)
    assert retry_decision("child", 1, "429 Retry-After: 420", 100) == (True, 420)
    assert retry_decision("child", 2, "network error", 100) == (False, 0)
    assert retry_decision("main", 0, "503 temporarily unavailable", 100) == (True, 0)
    assert retry_decision("main", 1, "503 temporarily unavailable", 100) == (False, 0)
    assert retry_decision("child", 0, "authentication failed", 100) == (False, 0)


def test_codex_command_inherits_user_config_but_limits_project_context(case_root: Path):
    config = load_case_config(case_root)
    profile = config.profile("default")
    workspace = case_root / "tasks" / "x" / "workspace"
    command = build_codex_command(config, profile, workspace, session_id="session-1")
    assert "--ignore-user-config" not in command
    assert "project_doc_max_bytes=0" in command
    assert "workspace-write" in command
    resume_index = command.index("resume")
    assert command.index('approval_policy="never"') > resume_index
    assert command.index('sandbox_mode="workspace-write"') > resume_index
    assert command[-2:] == ["session-1", "-"]
    assert "--add-dir" not in command
