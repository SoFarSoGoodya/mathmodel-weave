"""Create one truthful AI-use source for the paper and detail PDF."""

from __future__ import annotations

from pathlib import Path

from mathmodel_agent.contracts import read_json, write_json
from mathmodel_agent.runtime.state import State

from .errors import MissingAIFacts, PublicationError


REQUIRED_ADOPTION = ("adopted", "modifications", "verification")


def collect_ai_usage(
    case_root: str | Path,
    output_path: str | Path,
    *,
    stage_by_task: dict[str, str],
) -> dict:
    """Join D1 runtime facts to D3 adoption facts without inferring missing fields."""
    root = Path(case_root).resolve()
    control_path = root / "human/control.json"
    if not control_path.is_file():
        raise MissingAIFacts("D3 human-control facts are missing")
    control = read_json(control_path)
    adoptions = control.get("ai_adoptions")
    if not isinstance(adoptions, list):
        raise MissingAIFacts("D3 ai_adoptions is missing")
    adoption_by_task = {item.get("task_id"): item for item in adoptions if isinstance(item, dict)}
    runtime_by_task = {
        item.get("task_id"): item
        for item in State(root).ai_usage_records()
        if isinstance(item.get("task_id"), str)
    }
    if not stage_by_task:
        raise MissingAIFacts("stage_by_task must select relevant adopted AI tasks")
    normalized = []
    missing = []
    for task_id, stage in stage_by_task.items():
        record = runtime_by_task.get(task_id)
        if not record:
            missing.append({"task_id": task_id, "reason": "runtime AI record is missing"})
            continue
        adoption = adoption_by_task.get(task_id)
        if not isinstance(stage, str) or not stage.strip():
            raise MissingAIFacts(f"AI task {task_id} lacks a publication stage description")
        if not adoption:
            missing.append({"task_id": task_id, "reason": "human adoption facts are missing"})
            continue
        runs = record.get("runs") or []
        process_refs = [item.get("events_ref") for item in runs if item.get("events_ref")]
        process_ref = ", ".join(process_refs) or record.get("prompt_ref")
        normalized.append(
            {
                "task_id": task_id,
                "tool": record.get("tool"),
                "model": record.get("model"),
                "purpose": record.get("purpose"),
                "stage": stage,
                "process_ref": process_ref,
                "human_adoption": {
                    "adopted": adoption.get("adoption"),
                    "modifications": adoption.get("modification"),
                    "verification": adoption.get("human_verification"),
                },
                "adoption_decision_id": adoption.get("adoption_decision_id") or adoption.get("paper_decision_id"),
            }
        )
    result = {
        "schema_version": "publication-ai-usage-v1",
        "fixture": False,
        "status": "incomplete" if missing else "ready",
        "records": normalized,
        "missing": missing,
    }
    write_json(output_path, result)
    return result


def _tex_escape(value: object) -> str:
    text = str(value)
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
    }
    return "".join(replacements.get(character, character) for character in text)


def prepare_ai_usage(
    facts_path: str | Path,
    markdown_path: str | Path,
    tex_path: str | Path,
    *,
    demonstration: bool,
) -> dict:
    facts = read_json(facts_path)
    missing = facts.get("missing", [])
    if missing:
        task_ids = ", ".join(item.get("task_id", "unknown") for item in missing if isinstance(item, dict))
        raise MissingAIFacts(f"AI usage facts remain incomplete for: {task_ids or 'unknown task'}")
    records = facts.get("records")
    if not isinstance(records, list) or not records:
        raise MissingAIFacts("AI usage records are missing")
    fixture = bool(facts.get("fixture", False))
    if fixture and not demonstration:
        raise PublicationError("AI fixture facts are allowed only in a demonstration build")

    markdown = ["# AI 工具使用记录", ""]
    detail_rows = []
    for index, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            raise MissingAIFacts(f"AI record {index} is not an object")
        adoption = record.get("human_adoption")
        if not isinstance(adoption, dict) or any(not adoption.get(key) for key in REQUIRED_ADOPTION):
            raise MissingAIFacts(
                f"AI record {index} lacks actual adoption, modification, or verification facts"
            )
        required = ("tool", "model", "purpose", "stage", "process_ref")
        if any(not record.get(key) for key in required):
            raise MissingAIFacts(f"AI record {index} lacks tool/model/purpose/stage/process reference")
        markdown.extend(
            [
                f"## 记录 {index}",
                "",
                f"- 工具与型号：{record['tool']} / {record['model']}",
                f"- 目的：{record['purpose']}",
                f"- 环节：{record['stage']}",
                f"- 过程记录：`{record['process_ref']}`",
                f"- 采纳情况：{adoption['adopted']}",
                f"- 人工修改：{adoption['modifications']}",
                f"- 人工核验：{adoption['verification']}",
                "",
            ]
        )
        detail_rows.append(
            " & ".join(
                _tex_escape(value)
                for value in (
                    index,
                    f"{record['tool']} / {record['model']}",
                    record["purpose"],
                    record["stage"],
                    adoption["adopted"],
                    adoption["modifications"],
                    adoption["verification"],
                )
            )
            + r" \\"
        )

    notice = ""
    if fixture:
        notice = "开发演示夹具：以下采纳与核验描述仅用于验证发布接口，不代表真实参赛论文或人工批准。"
        markdown[1:1] = ["", f"> {notice}", ""]
    Path(markdown_path).parent.mkdir(parents=True, exist_ok=True)
    Path(markdown_path).write_text("\n".join(markdown).rstrip() + "\n", encoding="utf-8")
    tex_lines = [
        rf"\newcommand{{\AIUsageFixtureNotice}}{{{_tex_escape(notice)}}}",
        rf"\newcommand{{\AIUsageRecordCount}}{{{len(records)}}}",
        r"\newcommand{\AIUsageDetailRows}{%",
        *detail_rows,
        "}",
    ]
    Path(tex_path).parent.mkdir(parents=True, exist_ok=True)
    Path(tex_path).write_text("\n".join(tex_lines) + "\n", encoding="utf-8")
    return {"record_count": len(records), "fixture": fixture, "notice": notice}
