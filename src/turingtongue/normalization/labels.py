# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""Categorical label → evidence, used when a provider's score semantics are unclear."""

from __future__ import annotations

from collections.abc import Mapping

AI_EVIDENCE = 1.0
HUMAN_EVIDENCE = -1.0
MIXED_EVIDENCE = 0.0

DEFAULT_LABELS: Mapping[str, float] = {
    "ai": AI_EVIDENCE,
    "ai_generated": AI_EVIDENCE,
    "ai-generated": AI_EVIDENCE,
    "machine": AI_EVIDENCE,
    "fake": AI_EVIDENCE,
    "human": HUMAN_EVIDENCE,
    "human_written": HUMAN_EVIDENCE,
    "human-written": HUMAN_EVIDENCE,
    "original": HUMAN_EVIDENCE,
    "real": HUMAN_EVIDENCE,
    "mixed": MIXED_EVIDENCE,
    "ai_assisted": MIXED_EVIDENCE,
    "ai-assisted": MIXED_EVIDENCE,
}


def label_to_evidence(
    label: str | None, mapping: Mapping[str, float] = DEFAULT_LABELS
) -> float | None:
    """Return categorical evidence for ``label`` (case-insensitive) or None if unknown."""
    if label is None:
        return None
    return mapping.get(label.strip().lower())
