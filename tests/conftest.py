from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture
def login_success() -> dict:
    return load("login_success.json")


@pytest.fixture
def workouts_page() -> dict:
    return load("workouts_page.json")


@pytest.fixture
def logbook() -> dict:
    return load("logbook.json")
