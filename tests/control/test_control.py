import pytest

from mathmodel_agent import control
from mathmodel_agent.control import ControlError


def test_incremental_human_answer_binds_fixed_scope_and_fixture_never_approves(case_root):
    question = control.ask_human(
        case_root,
        scope="research_scope",
        displayed={"problem_ref": "problem/question.md", "sha256": "a" * 64},
        prompt="Choose the approved mode and stated run bound.",
        choices=["standard", "reject"],
        approval_choices=["standard"],
        limits={"bounds": {"max_runs": 2}},
    )
    answers = case_root / "human" / "HUMAN_ANSWERS.md"
    answers.open("a", encoding="utf-8").write("\n## A-001\n")
    assert control.consume_answers(case_root) == []
    answers.open("a", encoding="utf-8").write("\nFor: Q-001\n\nI select standard with max_runs 2.\n")
    consumed = control.consume_answers(case_root)
    assert consumed[0]["question_id"] == question["question_id"]
    decision = control.record_human_decision(
        case_root, question_id="Q-001", answer_id="A-001", choice="standard"
    )
    assert decision["status"] == "approved"
    assert control.approved_scope(case_root, "research_scope", {"max_runs": 2})["decision_id"] == "D-001"
    assert control.invalidate_for_object(case_root, question["displayed"], "formal problem object changed") == ["D-001"]
    assert control.approved_scope(case_root, "research_scope", {"max_runs": 2}) is None

    simulated = control.ask_human(
        case_root,
        scope="route_selection",
        displayed={"candidate": "candidate-a"},
        prompt="Select the formal route.",
        choices=["candidate-a"],
    )
    answer_id = control.append_fixture_answer(case_root, simulated["question_id"], "I select candidate-a.")
    fixture_decision = control.record_human_decision(
        case_root, question_id=simulated["question_id"], answer_id=answer_id, choice="candidate-a"
    )
    assert fixture_decision["status"] == "simulated"


def test_agent_data_cannot_create_a_human_decision(case_root):
    control.ask_human(
        case_root,
        scope="paper_package",
        displayed={"artifact_id": "bundle-1", "sha256": "b" * 64},
        prompt="Approve the exact package.",
        choices=["approve", "reject"],
        approval_choices=["approve"],
    )
    with pytest.raises(ControlError, match="unknown answer"):
        control.record_human_decision(case_root, question_id="Q-001", answer_id="A-999", choice="approve")
