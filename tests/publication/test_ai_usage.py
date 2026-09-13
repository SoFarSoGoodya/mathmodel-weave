from __future__ import annotations

import json

import pytest

from mathmodel_agent.publication.ai_usage import collect_ai_usage, prepare_ai_usage
from mathmodel_agent.publication.errors import MissingAIFacts, PublicationError


def record():
    return {
        "tool": "Codex",
        "model": "fixture-model",
        "purpose": "验证发布接口",
        "stage": "论文结构整理",
        "process_ref": "runtime/tasks/fixture/events.jsonl",
        "human_adoption": {
            "adopted": "采用结构提纲，不采用数值建议",
            "modifications": "人工重写论证并绑定正式结果宏",
            "verification": "人工核对 manifest、公式和最终 PDF",
        },
    }


def test_missing_human_adoption_fails_loudly(tmp_path):
    facts = tmp_path / "facts.json"
    value = record()
    value["human_adoption"] = None
    facts.write_text(json.dumps({"records": [value]}), encoding="utf-8")
    with pytest.raises(MissingAIFacts, match="adoption"):
        prepare_ai_usage(facts, tmp_path / "usage.md", tmp_path / "usage.tex", demonstration=False)


def test_fixture_is_rejected_for_non_demo(tmp_path):
    facts = tmp_path / "facts.json"
    facts.write_text(json.dumps({"fixture": True, "records": [record()]}), encoding="utf-8")
    with pytest.raises(PublicationError, match="demonstration"):
        prepare_ai_usage(facts, tmp_path / "usage.md", tmp_path / "usage.tex", demonstration=False)


def test_demo_fixture_is_disclosed_in_both_sources(tmp_path):
    facts = tmp_path / "facts.json"
    markdown = tmp_path / "usage.md"
    tex = tmp_path / "usage.tex"
    facts.write_text(json.dumps({"fixture": True, "records": [record()]}), encoding="utf-8")
    result = prepare_ai_usage(facts, markdown, tex, demonstration=True)
    assert result["fixture"] is True
    assert "不代表真实参赛论文或人工批准" in markdown.read_text(encoding="utf-8")
    assert "不代表真实参赛论文或人工批准" in tex.read_text(encoding="utf-8")


def test_actual_d1_d3_records_are_joined_by_task_id(tmp_path, monkeypatch):
    human = tmp_path / "human"
    human.mkdir()
    (human / "control.json").write_text(
        json.dumps(
            {
                "ai_adoptions": [
                    {
                        "task_id": "paper-task",
                        "paper_decision_id": "D-001",
                        "adoption": "采用结构",
                        "modification": "人工重写",
                        "human_verification": "核对运行清单和 PDF",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    class FakeState:
        def __init__(self, case_root):
            self.case_root = case_root

        def ai_usage_records(self):
            return [
                {
                    "task_id": "paper-task",
                    "tool": "Codex CLI",
                    "model": "gpt-fixture",
                    "purpose": "draft paper",
                    "prompt_ref": "tasks/paper-task/input/prompt.txt",
                    "runs": [{"events_ref": "tasks/paper-task/runtime-runs/run/events.jsonl"}],
                }
            ]

    monkeypatch.setattr("mathmodel_agent.publication.ai_usage.State", FakeState)
    output = tmp_path / "ai-usage.json"
    result = collect_ai_usage(tmp_path, output, stage_by_task={"paper-task": "论文写作"})
    assert result["fixture"] is False
    assert result["records"][0]["process_ref"].endswith("events.jsonl")
    assert result["records"][0]["human_adoption"]["verification"] == "核对运行清单和 PDF"
