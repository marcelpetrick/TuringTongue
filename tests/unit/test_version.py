# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
import re
import tomllib
from pathlib import Path

import pytest

import turingtongue

pytestmark = pytest.mark.unit


def test_version_matches_pyproject() -> None:
    pyproject = Path(__file__).parents[2] / "pyproject.toml"
    declared = tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]["version"]
    assert turingtongue.__version__ == declared
    assert re.fullmatch(r"\d+\.\d+\.\d+", declared)
