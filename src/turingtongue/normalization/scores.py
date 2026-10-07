# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""Map provider-native scores onto evidence in [-1 (human), +1 (AI)].

These mappings are *orientation* conversions only. A provider's "0.8 AI probability"
becomes evidence +0.6; nothing here claims the result is calibrated.
"""

from __future__ import annotations

import math


def _unit(value: float, name: str) -> float:
    if not isinstance(value, int | float) or math.isnan(value) or not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must be within [0, 1], got {value!r}")
    return float(value)


def ai_probability_to_evidence(p_ai: float) -> float:
    """``p_ai`` in [0, 1] (1 = AI) → ``2·p − 1``."""
    return 2.0 * _unit(p_ai, "AI score") - 1.0


def human_probability_to_evidence(p_human: float) -> float:
    """``p_human`` in [0, 1] (1 = human) → ``1 − 2·p``."""
    return 1.0 - 2.0 * _unit(p_human, "human score")


def percent_to_unit(percent: float) -> float:
    """0–100 percentage → 0–1."""
    if not isinstance(percent, int | float) or math.isnan(percent) or not 0 <= percent <= 100:
        raise ValueError(f"percentage must be within [0, 100], got {percent!r}")
    return float(percent) / 100.0


def fractions_to_evidence(ai: float, human: float, mixed: float = 0.0) -> float:
    """Document fractions (AI / human / AI-assisted or mixed) → evidence.

    ``evidence = (ai + 0.5·mixed − human) / (ai + mixed + human)``: mixed/assisted text
    counts as half-way, so a fully "AI-assisted" document is +0.5, not +1.
    """
    parts = [_unit(ai, "AI fraction"), _unit(human, "human fraction"), _unit(mixed, "mixed")]
    total = sum(parts)
    if total == 0:
        raise ValueError("fractions must not all be zero")
    return (parts[0] + 0.5 * parts[2] - parts[1]) / total
