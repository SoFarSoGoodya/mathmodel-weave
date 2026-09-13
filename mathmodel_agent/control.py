"""Append-only human decisions bound to the exact objects that were displayed."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping

from .contracts import read_json, write_json


_ANSWER = re.compile(r"^## (A-\d{3,})\s*$", re.MULTILINE)
_FOR = re.compile(r"(?:^|\n)(?:\*\*)?For:(?:\*\*)?\s*(Q-\d{3,})\s*$", re.MULTILINE | re.IGNORECASE)


class ControlError(ValueError):
    pass


def initialize(case_root: str | Path) -> None:
    root = Path(case_root).resolve()
    human = root / "human"
    human.mkdir(parents=True, exist_ok=True)
    questions = human / "AI_QUESTIONS.md"
    answers = human / "HUMAN_ANSWERS.md"
    if not questions.exists():
        questions.write_text(
            "# Questions For The Human\n\n"
            "The system appends fixed-object questions here. Reply in HUMAN_ANSWERS.md using an A-### heading and `For: Q-###`.\n",
            encoding="utf-8",
        )
    if not answers.exists():
        answers.write_text(
            "# Human Answers\n\n"
            "Append answers only. Each answer needs `## A-###` and `For: Q-###`; ordinary language after that is preserved as evidence.\n",
            encoding="utf-8",
        )
    state_path = _state_path(root)
    if not state_path.exists():
        write_json(state_path, _initial_state())


def ask_human(
    case_root: str | Path,
    *,
    scope: str,
    displayed: object,
    prompt: str,
    choices: list[str],
    limits: Mapping[str, Any] | None = None,
    approval_choices: list[str] | None = None,
) -> dict[str, Any]:
    """Append a question whose displayed objects cannot be silently replaced later."""
    root = Path(case_root).resolve()
    initialize(root)
    if not isinstance(scope, str) or not scope:
        raise ControlError("scope must be non-empty text")
    if not isinstance(prompt, str) or not prompt.strip():
        raise ControlError("prompt must be non-empty text")
    if not choices or not all(isinstance(choice, str) and choice for choice in choices):
        raise ControlError("choices must be a non-empty text list")
    if len(set(choices)) != len(choices):
        raise ControlError("choices must be unique")
    limits_dict = dict(limits or {})
    approved = list(approval_choices if approval_choices is not None else choices)
    if not set(approved).issubset(choices):
        raise ControlError("approval_choices must be drawn from choices")
    state = _load(root)
    question_id = f"Q-{state['next_question']:03d}"
    state["next_question"] += 1
    shown = _json_value(displayed, "displayed")
    question = {
        "question_id": question_id,
        "scope": scope,
        "displayed": shown,
        "display_hash": _digest(shown),
        "prompt": prompt.strip(),
        "choices": choices,
        "approval_choices": approved,
        "limits": limits_dict,
        "status": "waiting_human",
    }
    state["questions"][question_id] = question
    _save(root, state)
    rendered = (
        f"\n## {question_id}\n\n"
        f"**Scope:** {scope}\n\n"
        f"**Displayed object (fixed):** `{json.dumps(shown, ensure_ascii=False, sort_keys=True)}`\n\n"
        f"**Choices:** {', '.join(choices)}\n\n"
        f"{prompt.strip()}\n"
    )
    with _questions_path(root).open("a", encoding="utf-8") as stream:
        stream.write(rendered)
    return question


def capture_human_answer(case_root: str | Path, question_id: str, text: str) -> str:
    """CLI-facing helper: append an explicitly human-entered answer with provenance."""
    return _append_answer(case_root, question_id, text, provenance="human_cli")


def append_fixture_answer(case_root: str | Path, question_id: str, text: str) -> str:
    """Testing helper. Fixture answers remain simulated and never authorize a real action."""
    return _append_answer(case_root, question_id, text, provenance="fixture")


def consume_answers(case_root: str | Path) -> list[dict[str, Any]]:
    """Consume complete new answer sections once, retaining partial trailing edits for later."""
    root = Path(case_root).resolve()
    initialize(root)
    state = _load(root)
    raw = _answers_path(root).read_text(encoding="utf-8")
    cursor = state["answer_cursor_bytes"]
    consumed: list[dict[str, Any]] = []
    sections = list(_ANSWER.finditer(raw))
    for index, match in enumerate(sections):
        start = _byte_offset(raw, match.start())
        if start < cursor:
            continue
        end_char = sections[index + 1].start() if index + 1 < len(sections) else len(raw)
        body = raw[match.end():end_char].strip()
        if not body:
            break
        answer_id = match.group(1)
        end = _byte_offset(raw, end_char)
        if answer_id in state["answers"]:
            state["answer_cursor_bytes"] = max(state["answer_cursor_bytes"], end)
            continue
        target = _FOR.search(body)
        question_id = target.group(1) if target else None
        if "fixture: simulated human answer" in body.lower():
            provenance = "fixture"
        elif "provenance: human_cli" in body.lower():
            provenance = "human_cli"
        else:
            provenance = "human_file"
        question = state["questions"].get(question_id) if question_id else None
        status = "eligible" if question and question["status"] == "waiting_human" else "stale_or_unbound"
        answer = {
            "answer_id": answer_id,
            "question_id": question_id,
            "text": body,
            "text_hash": _digest(body),
            "provenance": provenance,
            "status": status,
        }
        state["answers"][answer_id] = answer
        state["answer_cursor_bytes"] = end
        consumed.append(answer)
    _save(root, state)
    return consumed


def record_human_decision(
    case_root: str | Path,
    *,
    question_id: str,
    answer_id: str,
    choice: str,
) -> dict[str, Any]:
    """Turn one explicit, bound answer into a decision; never infer approval automatically."""
    root = Path(case_root).resolve()
    consume_answers(root)
    state = _load(root)
    question = _required(state["questions"], question_id, "question")
    answer = _required(state["answers"], answer_id, "answer")
    if question["status"] != "waiting_human":
        raise ControlError("question is no longer waiting for a decision")
    if answer["status"] != "eligible" or answer["question_id"] != question_id:
        raise ControlError("answer is not a current response to this question")
    if choice not in question["choices"]:
        raise ControlError("choice was not displayed to the human")
    if not _mentions_choice(answer["text"], choice):
        raise ControlError("answer does not explicitly state the selected choice")
    decision_id = f"D-{state['next_decision']:03d}"
    state["next_decision"] += 1
    simulated = answer["provenance"] == "fixture"
    is_approved = choice in question["approval_choices"] and not simulated
    decision = {
        "decision_id": decision_id,
        "scope": question["scope"],
        "displayed": question["displayed"],
        "display_hash": question["display_hash"],
        "choice": choice,
        "limits": question["limits"],
        "answer_id": answer_id,
        "answer_hash": answer["text_hash"],
        "provenance": answer["provenance"],
        "status": "approved" if is_approved else ("simulated" if simulated else "rejected"),
    }
    state["decisions"][decision_id] = decision
    question["status"] = "approved" if is_approved else "rejected"
    answer["status"] = "recorded"
    _save(root, state)
    return decision


def approved_scope(case_root: str | Path, scope: str, bounds: Mapping[str, Any]) -> dict[str, Any] | None:
    """Return a real current authorization only when requested bounds fit its displayed limits."""
    root = Path(case_root).resolve()
    requested = dict(bounds)
    if not scope or not requested:
        return None
    for decision in _load(root)["decisions"].values():
        allowed = decision.get("limits", {}).get("bounds", {})
        if decision["scope"] == scope and decision["status"] == "approved" and _within(requested, allowed):
            return decision
    return None


def decision(case_root: str | Path, decision_id: str) -> dict[str, Any]:
    return _required(_load(Path(case_root).resolve())["decisions"], decision_id, "decision")


def invalidate_for_object(case_root: str | Path, displayed: object, reason: str) -> list[str]:
    """Invalidate only decisions bound to a materially changed formal object."""
    if not isinstance(reason, str) or not reason.strip():
        raise ControlError("invalidation reason must be non-empty")
    root = Path(case_root).resolve()
    digest = _digest(_json_value(displayed, "displayed"))
    state = _load(root)
    invalidated = []
    for record in state["decisions"].values():
        if record["status"] == "approved" and record["display_hash"] == digest:
            record["status"] = "superseded"
            record["invalidation_reason"] = reason.strip()
            invalidated.append(record["decision_id"])
    _save(root, state)
    return invalidated


def record_ai_adoption(
    case_root: str | Path,
    *,
    disclosure_decision_id: str | None = None,
    paper_decision_id: str | None = None,
    task_id: str,
    adoption: str,
    modification: str,
    human_verification: str,
) -> dict[str, Any]:
    """Record exact human-reviewed disclosure facts before or after package approval."""
    root = Path(case_root).resolve()
    state = _load(root)
    decision_id = disclosure_decision_id or paper_decision_id
    if not decision_id or (disclosure_decision_id and paper_decision_id):
        raise ControlError("provide exactly one disclosure or paper decision")
    approved = _required(state["decisions"], decision_id, "decision")
    if approved["scope"] not in {"ai_disclosure", "paper_package"} or approved["status"] != "approved":
        raise ControlError("AI adoption needs an approved disclosure review or final paper package")
    if not all(isinstance(value, str) and value.strip() for value in (task_id, adoption, modification, human_verification)):
        raise ControlError("AI adoption fields must be non-empty text")
    disclosed = {
        "task_id": task_id.strip(),
        "adoption": adoption.strip(),
        "modification": modification.strip(),
        "human_verification": human_verification.strip(),
    }
    if approved["scope"] == "ai_disclosure" and approved["displayed"] != disclosed:
        raise ControlError("AI adoption facts differ from the disclosure reviewed by the human")
    record = {
        **disclosed,
        "adoption_decision_id": decision_id,
        "paper_decision_id": paper_decision_id,
        "answer_id": approved["answer_id"],
    }
    state["ai_adoptions"].append(record)
    _save(root, state)
    return record


def pending_questions(case_root: str | Path) -> list[dict[str, Any]]:
    return [item for item in _load(Path(case_root).resolve())["questions"].values() if item["status"] == "waiting_human"]


def _append_answer(case_root: str | Path, question_id: str, text: str, *, provenance: str) -> str:
    root = Path(case_root).resolve()
    initialize(root)
    if question_id not in _load(root)["questions"]:
        raise ControlError("unknown question")
    if not isinstance(text, str) or not text.strip():
        raise ControlError("answer text must be non-empty")
    raw = _answers_path(root).read_text(encoding="utf-8")
    numbers = [int(match.group(1)) for match in re.finditer(r"^## A-(\d{3,})\s*$", raw, re.MULTILINE)]
    answer_id = f"A-{(max(numbers) + 1 if numbers else 1):03d}"
    marker = (
        "<!-- fixture: simulated human answer; not a competition approval -->\n"
        if provenance == "fixture"
        else "<!-- provenance: human_cli -->\n"
    )
    with _answers_path(root).open("a", encoding="utf-8") as stream:
        stream.write(f"\n## {answer_id}\n\n{marker}For: {question_id}\n\n{text.strip()}\n")
    return answer_id


def _initial_state() -> dict[str, Any]:
    return {"schema_version": "control-v1", "next_question": 1, "next_decision": 1, "answer_cursor_bytes": 0, "questions": {}, "answers": {}, "decisions": {}, "ai_adoptions": []}


def _load(root: Path) -> dict[str, Any]:
    initialize_if_needed = _state_path(root)
    if not initialize_if_needed.exists():
        initialize(root)
    state = read_json(_state_path(root))
    if state.get("schema_version") != "control-v1":
        raise ControlError("unsupported control state")
    return state


def _save(root: Path, state: dict[str, Any]) -> None:
    write_json(_state_path(root), state)


def _state_path(root: Path) -> Path:
    return root / "human" / "control.json"


def _questions_path(root: Path) -> Path:
    return root / "human" / "AI_QUESTIONS.md"


def _answers_path(root: Path) -> Path:
    return root / "human" / "HUMAN_ANSWERS.md"


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _json_value(value: object, label: str) -> object:
    try:
        json.dumps(value, ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise ControlError(f"{label} must be JSON-compatible") from exc
    return value


def _byte_offset(text: str, char_offset: int) -> int:
    return len(text[:char_offset].encode("utf-8"))


def _required(records: Mapping[str, Any], identifier: str, label: str) -> dict[str, Any]:
    value = records.get(identifier)
    if not isinstance(value, dict):
        raise ControlError(f"unknown {label}: {identifier}")
    return value


def _mentions_choice(text: str, choice: str) -> bool:
    if re.fullmatch(r"[A-Za-z0-9_.-]+", choice):
        return re.search(rf"(?<![A-Za-z0-9_-]){re.escape(choice)}(?![A-Za-z0-9_-])", text, re.IGNORECASE) is not None
    return choice.lower() in text.lower()


def _within(requested: Mapping[str, Any], allowed: object) -> bool:
    if not isinstance(allowed, Mapping):
        return False
    return all(key in allowed and allowed[key] == value for key, value in requested.items())
