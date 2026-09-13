"""Poll-based coordinator glue around the shared runtime state and human files."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from . import control
from .contracts import read_json, write_json
from .runtime.state import State, TaskNotFound, TaskValidationError


_TERMINAL = {"succeeded", "failed", "cancelled"}
_FORMAL_DECISIONS = {
    "route": "route_selection",
    "result": "result_selection",
    "fusion": "fusion_selection",
    "paper_package": "paper_package",
}


class WorkflowError(ValueError):
    pass


def submit_coordinator(
    case_root: str | Path,
    *,
    task_id: str,
    prompt: str,
    inputs: list[str] | None = None,
    profile: str = "default",
) -> str:
    """Submit the one agent session that may emit coordinator RESULT.json turns."""
    return State(case_root).submit(
        {
            "task_id": task_id,
            "kind": "agent",
            "role": "main",
            "purpose": "coordinate mathematical modeling exploration",
            "prompt": prompt,
            "profile": profile,
            "inputs": list(inputs or []),
        }
    )


class Coordinator:
    """Consumes completed coordinator turns; it never creates a second scheduler or task state."""

    def __init__(self, case_root: str | Path):
        self.case_root = Path(case_root).resolve()
        self.state = State(self.case_root)
        control.initialize(self.case_root)
        if not _record_path(self.case_root).exists():
            write_json(_record_path(self.case_root), {"schema_version": "coordinator-v1", "turns": {}})

    def poll(self, task_id: str) -> dict[str, Any]:
        """Submit eligible requests once, then resume the same session when all waits resolve."""
        task = self.state.get_task(task_id)
        if task["kind"] != "agent" or task["role"] != "main":
            raise WorkflowError("a coordinator must be a main agent task")
        if task["state"] != "succeeded":
            return {"task_id": task_id, "action": "not_completed", "runtime_state": task["state"]}
        result = task.get("result")
        if not isinstance(result, dict):
            return {"task_id": task_id, "action": "no_result"}
        if not _has_handoff(result):
            return {"task_id": task_id, "action": "final_result"}
        record = _load_record(self.case_root)
        turn_key = _digest(result)
        turn = record["turns"].setdefault(
            f"{task_id}:{turn_key}",
            {"task_id": task_id, "turn_hash": turn_key, "requests": {}, "questions": [], "resumed": False},
        )
        created_questions = self._create_questions(turn, result)
        submitted, blocked = self._submit_requests(turn, result)
        waits = self._wait_status(turn, result)
        _save_record(self.case_root, record)
        if waits["waiting"]:
            return {
                "task_id": task_id,
                "action": "waiting",
                "submitted": submitted,
                "blocked": blocked,
                "questions": created_questions,
                "waits": waits["items"],
            }
        if turn["resumed"]:
            return {
                "task_id": task_id,
                "action": "already_resumed",
                "submitted": submitted,
                "blocked": blocked,
                "waits": waits["items"],
            }
        followup = self._followup(waits["items"], blocked)
        self.state.resume(task_id, followup=followup)
        turn["resumed"] = True
        _save_record(self.case_root, record)
        return {
            "task_id": task_id,
            "action": "resumed",
            "submitted": submitted,
            "blocked": blocked,
            "waits": waits["items"],
        }

    def _create_questions(self, turn: dict[str, Any], result: dict[str, Any]) -> list[str]:
        requests = result.get("human_requests", [])
        if not isinstance(requests, list):
            raise WorkflowError("human_requests must be a list")
        created = []
        for index, item in enumerate(requests):
            if not isinstance(item, Mapping):
                raise WorkflowError("each human request must be an object")
            key = str(index)
            if key in turn["questions"]:
                continue
            required = ("scope", "displayed", "prompt", "choices")
            if not all(field in item for field in required):
                raise WorkflowError("human request needs scope, displayed, prompt, and choices")
            question = control.ask_human(
                self.case_root,
                scope=item["scope"],
                displayed=item["displayed"],
                prompt=item["prompt"],
                choices=item["choices"],
                limits=item.get("limits"),
                approval_choices=item.get("approval_choices"),
            )
            turn["questions"].append(key)
            turn.setdefault("question_ids", []).append(question["question_id"])
            created.append(question["question_id"])
        return created

    def _submit_requests(self, turn: dict[str, Any], result: dict[str, Any]) -> tuple[list[str], list[dict[str, str]]]:
        requests = result.get("requests", [])
        if not isinstance(requests, list):
            raise WorkflowError("RESULT.json requests must be a list")
        submitted: list[str] = []
        blocked: list[dict[str, str]] = []
        for index, request in enumerate(requests):
            if not isinstance(request, Mapping):
                raise WorkflowError("RESULT.json request must be an object")
            fingerprint = _digest(request)
            entry = turn["requests"].get(fingerprint)
            if entry is not None:
                if entry.get("task_id"):
                    submitted.append(entry["task_id"])
                elif entry.get("reason"):
                    blocked.append({"request": str(index), "reason": entry["reason"]})
                continue
            reason = self._eligibility_error(request)
            if reason:
                turn["requests"][fingerprint] = {"index": index, "reason": reason}
                blocked.append({"request": str(index), "reason": reason})
                continue
            try:
                child_id = self.state.submit(dict(request))
            except (TaskValidationError, ValueError, OSError) as exc:
                reason = f"submission failed: {exc}"
                turn["requests"][fingerprint] = {"index": index, "reason": reason}
                blocked.append({"request": str(index), "reason": reason})
            else:
                turn["requests"][fingerprint] = {"index": index, "task_id": child_id}
                submitted.append(child_id)
        return submitted, blocked

    def _eligibility_error(self, request: Mapping[str, Any]) -> str | None:
        if request.get("kind") not in {"agent", "command"}:
            return "request has no valid runtime kind"
        for category in ("inputs", "instructions", "skills"):
            entries = request.get(category, [])
            if not isinstance(entries, list):
                return f"{category} must be a list"
            for entry in entries:
                source = entry if isinstance(entry, str) else entry.get("source") if isinstance(entry, Mapping) else None
                if not isinstance(source, str) or not source or Path(source).is_absolute() or ".." in Path(source).parts:
                    return f"{category} must use case-relative selected paths"
        if _is_formal(request):
            if not request.get("inputs"):
                return "formal scientific requests require selected case-relative inputs"
            scope = request.get("research_scope")
            bounds = request.get("bounds")
            if not isinstance(scope, str) or not scope or not isinstance(bounds, Mapping) or not bounds:
                return "formal scientific requests require research_scope and non-empty bounds"
            if control.approved_scope(self.case_root, scope, bounds) is None:
                return "formal scientific request is outside current human-approved scope/bounds"
        kind = request.get("formal_decision")
        if kind is not None:
            expected_scope = _FORMAL_DECISIONS.get(kind)
            decision_id = request.get("authorization_decision_id")
            selected = request.get("selected_object")
            if expected_scope is None or not isinstance(decision_id, str) or selected is None:
                return "formal selection needs kind, selected_object, and human authorization_decision_id"
            try:
                authorization = control.decision(self.case_root, decision_id)
            except control.ControlError:
                return "formal selection names an unknown human decision"
            if authorization["status"] != "approved" or authorization["scope"] != expected_scope:
                return "formal selection lacks an approved decision for this scope"
            if authorization["display_hash"] != _digest(selected):
                return "formal selection object differs from the object the human approved"
        return None

    def _wait_status(self, turn: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
        raw_waits = result.get("wait_for", [])
        if not isinstance(raw_waits, list) or not all(isinstance(item, str) for item in raw_waits):
            raise WorkflowError("RESULT.json wait_for must be a task ID list")
        child_ids = list(raw_waits)
        child_ids.extend(entry["task_id"] for entry in turn["requests"].values() if entry.get("task_id"))
        items: list[dict[str, Any]] = []
        waiting = False
        for child_id in dict.fromkeys(child_ids):
            try:
                child = self.state.get_task(child_id)
            except TaskNotFound:
                items.append({"kind": "task", "task_id": child_id, "state": "unknown_task"})
                waiting = True
                continue
            items.append(_task_material(child))
            if child["state"] not in _TERMINAL:
                waiting = True
        requested_questions = result.get("wait_for_human", [])
        if not isinstance(requested_questions, list) or not all(isinstance(item, str) for item in requested_questions):
            raise WorkflowError("wait_for_human must be a question ID list")
        question_ids = list(requested_questions) + turn.get("question_ids", [])
        for question_id in dict.fromkeys(question_ids):
            question = next((item for item in control.pending_questions(self.case_root) if item["question_id"] == question_id), None)
            if question is not None:
                items.append({"kind": "human", "question_id": question_id, "state": "waiting_human"})
                waiting = True
                continue
            try:
                state = _human_question_state(self.case_root, question_id)
            except control.ControlError:
                items.append({"kind": "human", "question_id": question_id, "state": "unknown_question"})
                waiting = True
            else:
                items.append({"kind": "human", "question_id": question_id, "state": state})
        return {"waiting": waiting, "items": items}

    @staticmethod
    def _followup(items: list[dict[str, Any]], blocked: list[dict[str, str]]) -> str:
        material = {"completed_dependencies": items, "blocked_requests": blocked}
        return (
            "Continue the same coordinator session. The following bounded, persisted material is now available; "
            "failed, cancelled, and unknown outcomes are not success. Decide the next safe step, keep formal "
            "route/result/fusion/package choices behind explicit human authorization, and write a fresh RESULT.json.\n\n"
            + _bounded_json(material, 7000)
        )


def _is_formal(request: Mapping[str, Any]) -> bool:
    execution = request.get("execution")
    return request.get("research_class") == "formal" or request.get("class") == "formal" or (
        isinstance(execution, Mapping) and execution.get("class") == "formal"
    )


def _has_handoff(result: Mapping[str, Any]) -> bool:
    return any(result.get(field) for field in ("requests", "wait_for", "human_requests", "wait_for_human"))


def _task_material(task: Mapping[str, Any]) -> dict[str, Any]:
    material: dict[str, Any] = {"kind": "task", "task_id": task["task_id"], "state": task["state"]}
    if task.get("error"):
        material["error"] = task["error"]
    if task.get("result") is not None:
        material["result"] = _bounded_value(task["result"], 1200)
    return material


def _human_question_state(case_root: Path, question_id: str) -> str:
    state = read_json(case_root / "human" / "control.json")
    question = state.get("questions", {}).get(question_id)
    if not isinstance(question, dict):
        raise control.ControlError("unknown question")
    return question["status"]


def _record_path(case_root: Path) -> Path:
    return case_root / "human" / "coordinator.json"


def _load_record(case_root: Path) -> dict[str, Any]:
    record = read_json(_record_path(case_root))
    if record.get("schema_version") != "coordinator-v1" or not isinstance(record.get("turns"), dict):
        raise WorkflowError("unsupported coordinator record")
    return record


def _save_record(case_root: Path, record: dict[str, Any]) -> None:
    write_json(_record_path(case_root), record)


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _bounded_value(value: object, limit: int) -> object:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return json.loads(text) if len(text) <= limit else {"truncated": text[:limit] + "..."}


def _bounded_json(value: object, limit: int) -> str:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)
    return text if len(text) <= limit else text[:limit] + "\n... [truncated]"
