"""Create and execute a self-contained synthetic formal experiment case."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys

from mathmodel_agent.execution import run_experiment
from mathmodel_agent.runtime.config import init_case


def main(argv: list[str] | None = None) -> int:
    destination = Path((argv or sys.argv[1:])[0] if (argv or sys.argv[1:]) else "synthetic-allocation-case").resolve()
    init_case(destination)
    source = Path(__file__).parent
    demo = destination / "demo"
    shutil.copytree(source, demo)
    request = {
        "class": "formal", "task_id": "synthetic-allocation", "experiment_run_id": "XR-synthetic-allocation",
        "purpose": "Synthetic allocation baseline-versus-optimum demonstration; not competition output.",
        "code": "demo/allocation.py", "config": "demo/allocation_config.json", "inputs": [],
        "comparison_contract": "demo/comparison_contract.json",
        "command": [sys.executable, "{code}", "--config", "{config}", "--output", "{output_dir}"],
        "timeout_seconds": 30,
    }
    result = run_experiment(destination, request)
    (destination / "demo-result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
