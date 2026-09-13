"""Codex CLI command construction and JSONL terminal interpretation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import json
from pathlib import Path
import re
from typing import Iterable

from .config import CaseConfig, Profile


TRANSIENT_TERMS = (
    "stream disconnected",
    "reconnecting",
    "network error",
    "transport error",
    "rate limit",
    "concurrency limit",
    "temporarily unavailable",
    "connection reset",
    "connection refused",
    "timed out",
    "timeout",
    "http 429",
    "http 502",
    "http 503",
    "http 504",
)


@dataclass
class EventSummary:
    session_id: str | None = None
    terminal_turn: str | None = None
    final_message: str | None = None
    diagnostics: list[dict] = field(default_factory=list)
    usage: dict | None = None
    invalid_lines: int = 0

    @property
    def completed(self) -> bool:
        return self.terminal_turn == "turn.completed"


def parse_event_lines(lines: Iterable[str | bytes]) -> EventSummary:
    summary = EventSummary()
    for raw_line in lines:
        if isinstance(raw_line, bytes):
            line = raw_line.decode("utf-8", errors="replace").strip()
        else:
            line = raw_line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except (json.JSONDecodeError, TypeError):
            summary.invalid_lines += 1
            continue
        if not isinstance(event, dict):
            summary.invalid_lines += 1
            continue
        event_type = event.get("type")
        if event_type == "thread.started" and isinstance(event.get("thread_id"), str):
            summary.session_id = event["thread_id"]
        elif event_type in {"turn.completed", "turn.failed"}:
            summary.terminal_turn = event_type
            if event_type == "turn.completed" and isinstance(event.get("usage"), dict):
                summary.usage = event["usage"]
            if event_type == "turn.failed":
                summary.diagnostics.append(event)
        elif event_type == "error":
            summary.diagnostics.append(event)
        elif event_type == "item.completed":
            item = event.get("item")
            if isinstance(item, dict) and item.get("type") == "agent_message":
                text = item.get("text")
                if isinstance(text, str):
                    summary.final_message = text
    return summary


def parse_event_file(path: str | Path) -> EventSummary:
    event_path = Path(path)
    if not event_path.exists():
        return EventSummary()
    with event_path.open("rb") as stream:
        return parse_event_lines(stream)


def attempt_succeeded(exit_code: int | None, summary: EventSummary) -> bool:
    """A recovered transient diagnostic does not override a final completed turn."""
    return exit_code == 0 and summary.completed


def diagnostic_text(summary: EventSummary, stderr_text: str) -> str:
    parts = [json.dumps(item, ensure_ascii=False) for item in summary.diagnostics]
    if stderr_text.strip():
        parts.append(stderr_text.strip())
    if summary.invalid_lines:
        parts.append(f"invalid JSONL lines: {summary.invalid_lines}")
    return "\n".join(parts)[-16000:]


def is_transient_failure(message: str) -> bool:
    lowered = message.lower()
    if any(term in lowered for term in TRANSIENT_TERMS):
        return True
    return bool(re.search(r"(?:^|\D)(429|502|503|504)(?:\D|$)", lowered))


def retry_after_seconds(message: str, now: float) -> int:
    match = re.search(
        r"retry[-_ ]after(?:\s*(?:header)?\s*)?[\s\"':=]+(\d+)",
        message,
        re.IGNORECASE,
    )
    if match:
        return int(match.group(1))
    date_match = re.search(
        r"retry[-_ ]after(?:\s*(?:header)?\s*)?[\s\"':=]+([^\r\n,]+(?:,[^\r\n]+)?)",
        message,
        re.IGNORECASE,
    )
    if not date_match:
        return 0
    try:
        parsed = parsedate_to_datetime(date_match.group(1).strip())
    except (TypeError, ValueError, OverflowError):
        return 0
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return max(0, int(parsed.timestamp() - now + 0.999))


def retry_decision(role: str, retries_used: int, message: str, now: float) -> tuple[bool, int]:
    if not is_transient_failure(message):
        return False, 0
    if role == "main":
        allowed = retries_used < 1
        floor = 0
    else:
        allowed = retries_used < 2
        floor = 0 if retries_used == 0 else 300
    if not allowed:
        return False, 0
    return True, max(floor, retry_after_seconds(message, now))


def build_codex_command(
    config: CaseConfig,
    profile: Profile,
    workspace: Path,
    *,
    session_id: str | None,
    sandbox: str | None = None,
    allow_network: bool | None = None,
    extra_write_paths: Iterable[Path] | None = None,
) -> list[str]:
    selected_sandbox = sandbox or config.sandbox
    selected_network = config.allow_network if allow_network is None else allow_network
    selected_extras = config.allowed_extra_write_paths if extra_write_paths is None else tuple(extra_write_paths)
    if session_id:
        writable_roots = json.dumps([str(path) for path in selected_extras])
        command = [
            "codex", "-C", str(workspace), "exec", "--json", "--skip-git-repo-check",
            "resume",
            "-c", 'approval_policy="never"',
            "-c", f'sandbox_mode="{selected_sandbox}"',
            "-c", "project_doc_max_bytes=0",
            "-c", f"sandbox_workspace_write.network_access={str(selected_network).lower()}",
            "-c", f"sandbox_workspace_write.writable_roots={writable_roots}",
            "-c", f'model_reasoning_effort="{profile.effort}"',
            "-m", profile.model,
        ]
        if profile.codex_profile:
            command += ["-p", profile.codex_profile]
        return command + [session_id, "-"]

    command = [
        "codex", "-a", "never", "-s", selected_sandbox, "-C", str(workspace),
        "-c", "project_doc_max_bytes=0",
        "-c", f"sandbox_workspace_write.network_access={str(selected_network).lower()}",
        "-c", f'model_reasoning_effort="{profile.effort}"',
    ]
    if profile.codex_profile:
        command += ["-p", profile.codex_profile]
    for extra in selected_extras:
        command += ["--add-dir", str(extra)]
    return command + ["exec", "--json", "--skip-git-repo-check", "-m", profile.model, "-"]


def utc_iso(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()
