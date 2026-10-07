# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""Provider confidence → [0, 1] and → ensemble confidence factor.

Unknown confidence stays ``None``; it is never invented. In the ensemble an unknown
confidence uses the documented neutral factor :data:`UNKNOWN_CONFIDENCE_FACTOR`.
"""

from __future__ import annotations

from collections.abc import Mapping

UNKNOWN_CONFIDENCE_FACTOR = 0.75
"""Midpoint of the known-confidence factor range [0.5, 1.0]."""

ORDINAL_CONFIDENCE: Mapping[str, float] = {
    "low": 1 / 3,
    "medium": 2 / 3,
    "moderate": 2 / 3,
    "high": 1.0,
}
"""Ordinal rank of categorical confidence labels — a rank, not a probability."""


def ordinal_confidence(label: str | None) -> float | None:
    """``high``/``medium``/``low`` → ordinal rank in (0, 1]; None if unknown."""
    if label is None:
        return None
    return ORDINAL_CONFIDENCE.get(label.strip().lower())


def confidence_factor(confidence: float | None) -> float:
    """Ensemble weight factor: ``0.5 + 0.5·c`` for known ``c``, else the neutral factor.

    A provider never loses more than half its vote for low confidence: confidence
    semantics differ by vendor, so they modulate rather than dominate.
    """
    if confidence is None:
        return UNKNOWN_CONFIDENCE_FACTOR
    clamped = min(1.0, max(0.0, confidence))
    return 0.5 + 0.5 * clamped
