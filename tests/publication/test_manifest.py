from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from mathmodel_agent.contracts import sha256_file
from mathmodel_agent.publication import (
    PublicationError,
    ScienceRevisionRequired,
    classify_manifest_change,
    generate_results_tex,
)
from mathmodel_agent.publication.inputs import validate_frozen_inputs


DEMO_BUNDLE = (
    Path(__file__).parents[2]
    / "examples/experiment/synthetic-case/artifacts"
    / "bundle-c1bc1228471a31baec78f4abf19faf555461edb0292db4cb955ee244f3cbcf85"
)


def load_manifest() -> dict:
    return json.loads((DEMO_BUNDLE / "run_manifest.json").read_text(encoding="utf-8"))


def test_manifest_numbers_generate_tex_macros_and_table(tmp_path):
    output = tmp_path / "results.tex"
    result = generate_results_tex(DEMO_BUNDLE / "run_manifest.json", output)

    generated = output.read_text(encoding="utf-8")
    assert r"\newcommand{\BaselineMeanValue}{16.5}" in generated
    assert r"\newcommand{\AlternativeMeanValue}{19.5}" in generated
    assert r"baseline\_mean\_value & 16.5 & value & mean & 2/1/3" in generated
    assert result["coverage"] == {"completed": 2, "failed": 1, "planned": 3}


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda metric: metric.pop("name"), "name and unit"),
        (lambda metric: metric.update(unit="kg"), "definition/unit mismatch"),
        (lambda metric: metric.update(value="16.5"), "must be numeric"),
    ],
)
def test_invalid_metric_key_value_or_unit_is_rejected(tmp_path, mutation, message):
    manifest = load_manifest()
    mutation(manifest["metrics"][0])
    with pytest.raises(PublicationError, match=message):
        generate_results_tex(manifest, tmp_path / "results.tex")


def test_display_only_changes_do_not_reopen_science():
    original = load_manifest()
    candidate = copy.deepcopy(original)
    candidate["figures"][0]["display_config"] = "figures/new-display.json"
    candidate["figures"][0]["image"] = "figures/redrawn.pdf"
    assert classify_manifest_change(original, candidate) == "display_only"


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: value["metrics"][0]["definition"].update(aggregation="median"),
        lambda value: value["metrics"][0]["denominator"].update(completed=1),
        lambda value: value["instances"].pop(),
        lambda value: value["metrics"][0].update(unit="points"),
    ],
)
def test_aggregation_sample_and_unit_changes_require_science_revision(mutation):
    original = load_manifest()
    candidate = copy.deepcopy(original)
    mutation(candidate)
    assert classify_manifest_change(original, candidate) == "science_revision"


def test_stale_selected_or_freeze_result_ref_is_rejected(tmp_path):
    manifest_path = DEMO_BUNDLE / "run_manifest.json"
    actual_ref = {
        "experiment_run_id": "XR-synthetic-allocation",
        "manifest_sha256": sha256_file(manifest_path),
    }
    selected = tmp_path / "selected.json"
    freeze = tmp_path / "freeze.json"
    selected.write_text(
        json.dumps({"status": "demo_fixture", "demonstration": True, "run_ref": actual_ref}),
        encoding="utf-8",
    )
    freeze.write_text(json.dumps({"status": "ready", "result_refs": [actual_ref]}), encoding="utf-8")
    validate_frozen_inputs(selected, freeze, manifest_path, demonstration=True)

    stale = actual_ref | {"manifest_sha256": "0" * 64}
    selected.write_text(
        json.dumps({"status": "demo_fixture", "demonstration": True, "run_ref": stale}),
        encoding="utf-8",
    )
    with pytest.raises(ScienceRevisionRequired, match="stale"):
        validate_frozen_inputs(selected, freeze, manifest_path, demonstration=True)
