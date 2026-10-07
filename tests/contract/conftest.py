# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""Helpers for provider contract tests."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from turingtongue import Checker, CheckResult, Settings

FIXTURES = Path(__file__).parents[1] / "fixtures"


def fixture(provider: str, name: str) -> Any:
    """Load ``tests/fixtures/<provider>/<name>.json``."""
    return json.loads((FIXTURES / provider / f"{name}.json").read_text(encoding="utf-8"))


Runner = Callable[..., CheckResult]


@pytest.fixture
def run_provider() -> Runner:
    """Run one provider through the real orchestrator with the given environment."""

    def run(provider: str, text: str, env: dict[str, str], **options: object) -> CheckResult:
        settings = Settings(env=env, max_retries=1, backoff_base_s=0.0, backoff_max_s=0.0)
        return Checker(settings).check(
            text, providers=[provider], verbose=True, provider_options={provider: options}
        )

    return run
