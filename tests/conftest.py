from pathlib import Path

import pytest

from mathmodel_agent.runtime.config import init_case


@pytest.fixture
def case_root(tmp_path: Path) -> Path:
    root = tmp_path / "case"
    init_case(root)
    return root
