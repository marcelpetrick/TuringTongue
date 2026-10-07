# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""Shared pytest fixtures."""

from __future__ import annotations

import pytest

PROVIDER_ENV_VARS = (
    "GPTZERO_API_KEY",
    "PANGRAM_API_KEY",
    "SAPLING_API_KEY",
    "COPYLEAKS_API_KEY",
    "COPYLEAKS_EMAIL",
    "WINSTON_API_KEY",
    "ORIGINALITY_API_KEY",
    "HIVE_API_KEY",
    "ZEROGPT_API_KEY",
    "TURINGTONGUE_CONFIG",
    "TURINGTONGUE_MOCK_RESULT",
)


@pytest.fixture(autouse=True)
def _isolated_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests never see the developer's real credentials or config."""
    for name in PROVIDER_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("TURINGTONGUE_NO_DOTENV", "1")
