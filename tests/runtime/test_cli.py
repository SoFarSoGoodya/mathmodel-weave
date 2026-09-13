import json
from pathlib import Path

from mathmodel_agent.cli import main


def test_cli_init_submit_status_and_doctor(tmp_path: Path, capsys):
    case = tmp_path / "cli-case"
    assert main(["init", str(case)]) == 0
    spec = tmp_path / "task.json"
    spec.write_text(json.dumps({"task_id": "cli-task", "kind": "command", "argv": ["true"]}))
    assert main(["submit", str(case), str(spec)]) == 0
    assert main(["serve", str(case), "--once", "--poll-interval", "0.01"]) == 0
    assert main(["status", str(case), "cli-task"]) == 0
    status_output = capsys.readouterr().out
    assert '"task_id": "cli-task"' in status_output
    assert '"state": "succeeded"' in status_output
    assert main(["doctor", str(case)]) == 0
    output = capsys.readouterr().out
    assert '"credentials_inspected": false' in output
    assert '"network_checked": false' in output
