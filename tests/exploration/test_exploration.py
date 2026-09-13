from pathlib import Path

from mathmodel_agent.evidence import register_source
from mathmodel_agent.execution import prepare_experiment
from mathmodel_agent.exploration import (
    create_comparison_contract,
    write_candidate,
    write_comparison_pack,
    write_variant,
)


def _candidate(case_root, candidate_id, *, parents=None):
    return write_candidate(
        case_root,
        candidate_id,
        name=f"Route {candidate_id}",
        subproblem="Allocate a bounded resource.",
        origin="independent author draft",
        mathematical_structure="Let x_i be allocation variables with sum_i x_i <= B.",
        derivation="The feasible set is finite, so enumerate the small synthetic instance.",
        pseudocode="for feasible x: retain the best objective",
        sources=["source-theory"],
        assumptions="All input units are compatible.",
        limitations="This is a synthetic finite instance, not a competition result.",
        structural_difference="Uses exhaustive search rather than a greedy construction.",
        parents=parents,
    )


def test_candidates_contract_and_d4_preparation_use_real_case_files(case_root):
    source = register_source(case_root, "Synthetic theory note", text="A bounded finite optimization note.", source_id="source-theory")
    assert source["source_id"] == "source-theory"
    first = _candidate(case_root, "route-a")
    second = _candidate(case_root, "route-b")
    variant = write_variant(
        case_root,
        "route-a",
        "fast-config",
        implementation_difference="Use a memoized enumeration order.",
        configuration_difference="Set a deterministic tie-break order.",
        purpose="Measure implementation sensitivity without claiming a new mathematical route.",
    )
    assert variant["candidate_id"] == "route-a"
    fusion = _candidate(case_root, "route-fusion", parents=["route-a", "route-b"])
    assert fusion["validity"] == "unreviewed"

    contract = create_comparison_contract(
        case_root,
        "allocation-contract",
        candidates=["route-a", "route-b"],
        data={"dataset": "datasets/instances.json", "unit": "items"},
        split={"kind": "fixed synthetic instance"},
        planned_instances=[{"id": "case-a", "seed": None}],
        metrics=[{"name": "value", "field": "value", "unit": "points", "aggregation": "mean"}],
        constraints=[],
        baseline="A reproducible greedy baseline.",
        budget={"max_runs": 2, "timeout_seconds": 30},
        failure_denominator="All planned instances and failed attempts are reported.",
        stopping_condition="Stop after both routes have one bounded run.",
    )
    pack = write_comparison_pack(
        case_root,
        "allocation-compare",
        contract_id="allocation-contract",
        evidence=[
            {"candidate_id": "route-a", "status": "unknown", "evidence": "No formal run yet.", "uncertainty": "No empirical value is claimed.", "tradeoffs": "Simple but potentially slow."},
            {"candidate_id": "route-b", "status": "not_run", "evidence": "Awaiting a bounded run.", "uncertainty": "Relative quality is unknown.", "tradeoffs": "May scale better but needs checking."},
        ],
        recommendation="No formal route is selected; ask the human after evidence is available.",
        decision_readiness="Enough to decide the next experiment, not enough for formal selection.",
    )
    assert "No formal route is selected" in (case_root / pack["path"]).read_text(encoding="utf-8")

    (case_root / "code.py").write_text("print('unused in preparation')", encoding="utf-8")
    (case_root / "config.json").write_text("{}", encoding="utf-8")
    (case_root / "datasets" / "instances.json").write_text("[]", encoding="utf-8")
    prepared = prepare_experiment(
        case_root,
        {
            "class": "formal",
            "experiment_run_id": "XR-contract-test",
            "task_id": "contract-test",
            "purpose": "Verify D3 contract is consumable by D4 preparation.",
            "code": "code.py",
            "config": "config.json",
            "inputs": [{"id": "instances", "path": "datasets/instances.json"}],
            "comparison_contract": contract["path"],
            "instances": [{"id": "case-a", "seed": None}],
            "command": ["true"],
        },
    )
    assert prepared["comparison_contract"]["path"] == contract["path"]
