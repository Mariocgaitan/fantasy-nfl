from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures" / "sem03_2026-09-25"


@pytest.fixture
def fixture_dir() -> Path:
    return FIXTURES
