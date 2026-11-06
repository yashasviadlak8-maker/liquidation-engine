import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest
from engine.rules import load_rules


@pytest.fixture
def rules():
    return load_rules(ROOT / "rules" / "fy2026_27.json")
