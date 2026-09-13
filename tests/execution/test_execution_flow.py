import json
from pathlib import Path
import shutil
import sys
import time

import pytest

from mathmodel_agent.execution import (
    ExperimentValidationError,
    finalize_experiment,
    prepare_experiment,
    redraw_figure,
    run_experiment,
    submit_experiment,
)
from mathmodel_agent.runtime.artifacts import resolve_bundle
from mathmodel_agent.runtime.config import init_case
from mathmodel_agent.runtime.scheduler import Supervisor
from mathmodel_agent.runtime.state import State


EXAMPLE = Path(__file__).parents[2] / "examples" / "experiment" / "allocation"


def copied_demo(tmp_path: Path) -> Path:
    case = tmp_path / "case"
    init_case(case)
    shutil.copytree(EXAMPLE, case / "demo")
    return case


def request(*, task_id="allocation", run_id="XR-allocation", contract="demo/comparison_contract.json", code="demo/allocation.py", config="demo/allocation_config.json"):
    return {
        "class": "formal", "task_id": task_id, "experiment_run_id": run_id,
        "purpose": "Synthetic demonstration only; not competition output.",
        "code": code, "config": config, "inputs": [], "comparison_contract": contract,
        "command": [sys.executable, "{code}", "--config", "{config}", "--output", "{output_dir}"],
        "timeout_seconds": 10,
    }


def manifest(case: Path, result: dict) -> dict:
    bundle = resolve_bundle(case, result["run_manifest_refs"][0])
    return json.loads((bundle / "run_manifest.json").read_text(encoding="utf-8"))


def test_runtime_batch_builds_real_partial_package_with_known_metrics_and_figure(tmp_path: Path):
    case = copied_demo(tmp_path)
    result = run_experiment(case, request())
    run = manifest(case, result)

    assert result["outcome"] == "partial"
    assert result["coverage"] == {"planned": 3, "completed": 2, "failed": 1}
    assert {item["name"]: item["value"] for item in run["metrics"]} == {
        "baseline_mean_value": 16.5, "alternative_mean_value": 19.5,
    }
    assert run["runtime"]["runtime_run_id"] != run["experiment_run_id"]
    assert run["figures"][0]["name"] == "allocation-values"
    bundle = resolve_bundle(case, result["run_manifest_refs"][0])
    assert (bundle / "figures" / "value-comparison.png").stat().st_size > 0
    assert run["checks"][-1]["status"] == "passed"


def test_reference_drift_rejects_formal_before_command_is_submitted(tmp_path: Path):
    case = copied_demo(tmp_path)
    prepared = prepare_experiment(case, request())
    config = case / "demo" / "allocation_config.json"
    config.write_text(config.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(ExperimentValidationError, match="changed after preparation"):
        submit_experiment(case, prepared)
    assert State(case).list_tasks() == []


def test_constraint_failure_is_invalid_and_new_algorithm_rerun_has_new_science_identity(tmp_path: Path):
    case = copied_demo(tmp_path)
    bad = case / "demo" / "bad.py"
    bad.write_text(
        "import json,pathlib,sys; p=pathlib.Path(sys.argv[sys.argv.index('--output')+1]); p.mkdir(parents=True, exist_ok=True); "
        "(p/'observations.jsonl').write_text(json.dumps({'instance_id':'known-gap','status':'completed','baseline_value':12,'alternative_value':99,'known_optimum':18})+'\\n'+json.dumps({'instance_id':'known-tie','status':'completed','baseline_value':21,'alternative_value':21,'known_optimum':21})+'\\n'+json.dumps({'instance_id':'deliberate-failure','status':'failed'})+'\\n')",
        encoding="utf-8",
    )
    invalid = run_experiment(case, request(task_id="bad", run_id="XR-bad", code="demo/bad.py"))
    assert invalid["outcome"] == "invalid"
    assert any(item["status"] == "failed" for item in manifest(case, invalid)["checks"])

    first = run_experiment(case, request(task_id="again-one", run_id="XR-again-one"))
    second = run_experiment(case, request(task_id="again-two", run_id="XR-again-two"))
    first_run, second_run = manifest(case, first), manifest(case, second)
    assert first_run["experiment_run_id"] != second_run["experiment_run_id"]
    assert first_run["runtime"]["runtime_run_id"] != second_run["runtime"]["runtime_run_id"]
    assert first["receipt_refs"] != second["receipt_refs"]


def test_not_run_unknown_and_cancelled_half_output_preserve_process_facts(tmp_path: Path):
    case = copied_demo(tmp_path)
    silent = case / "demo" / "silent.py"
    silent.write_text("raise SystemExit(1)\n", encoding="utf-8")
    unknown_prepared = prepare_experiment(case, request(task_id="unknown", run_id="XR-unknown", code="demo/silent.py"))
    submit_experiment(case, unknown_prepared)
    Supervisor(case).serve(stop_when_idle=True)
    assert finalize_experiment(case, "unknown")["outcome"] == "unknown"

    not_run_prepared = prepare_experiment(case, request(task_id="never", run_id="XR-never", code="demo/silent.py"))
    submit_experiment(case, not_run_prepared)
    State(case).cancel("never")
    assert finalize_experiment(case, "never")["outcome"] == "not_run"

    partial = case / "demo" / "partial.py"
    partial.write_text(
        "import pathlib,sys,time; p=pathlib.Path(sys.argv[sys.argv.index('--output')+1]); p.mkdir(parents=True, exist_ok=True); "
        "(p/'observations.jsonl').write_text('{\\\"instance_id\\\": \\\"known-gap\\\", \\\"status\\\": \\\"completed\\\", \\\"baseline_value\\\": 12, \\\"alternative_value\\\": 18, \\\"known_optimum\\\": 18}\\n{'); time.sleep(4)",
        encoding="utf-8",
    )
    prepared = prepare_experiment(case, request(task_id="cancelled", run_id="XR-cancelled", code="demo/partial.py"))
    submit_experiment(case, prepared)
    supervisor = Supervisor(case)
    supervisor.run_once()
    time.sleep(0.1)
    State(case).cancel("cancelled")
    supervisor.serve(stop_when_idle=True)
    result = finalize_experiment(case, "cancelled")
    assert result["outcome"] == "partial"
    assert "ignored incomplete or invalid observation line 2" in result["issues"]


def test_style_redraw_preserves_metrics_but_changed_aggregation_is_new_science_evidence(tmp_path: Path):
    case = copied_demo(tmp_path)
    first = run_experiment(case, request())
    run_dir = case / "tasks" / "allocation" / "workspace" / "experiments" / "XR-allocation"
    original_metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
    redraw = redraw_figure(run_dir, {"title": "Restyled synthetic allocation", "ylabel": "value", "colors": ["#111111", "#cc3311"], "dpi": 120})
    assert redraw.is_file()
    assert json.loads((run_dir / "metrics.json").read_text(encoding="utf-8")) == original_metrics

    contract = json.loads((case / "demo" / "comparison_contract.json").read_text(encoding="utf-8"))
    contract["metrics"][1]["aggregation"] = "max"
    (case / "demo" / "max_contract.json").write_text(json.dumps(contract), encoding="utf-8")
    changed = run_experiment(case, request(task_id="max", run_id="XR-max", contract="demo/max_contract.json"))
    values = {item["name"]: item["value"] for item in manifest(case, changed)["metrics"]}
    assert values["alternative_mean_value"] == 21
    assert changed["run_manifest_refs"] != first["run_manifest_refs"]
