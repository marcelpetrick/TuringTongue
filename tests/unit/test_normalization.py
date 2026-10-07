# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
import math

import pytest

from turingtongue.normalization.confidence import (
    UNKNOWN_CONFIDENCE_FACTOR,
    confidence_factor,
    ordinal_confidence,
)
from turingtongue.normalization.labels import label_to_evidence
from turingtongue.normalization.scores import (
    ai_probability_to_evidence,
    fractions_to_evidence,
    human_probability_to_evidence,
    percent_to_unit,
)

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(("p", "e"), [(0, -1), (0.5, 0), (1, 1), (0.8, 0.6)])
def test_ai_probability(p: float, e: float) -> None:
    assert ai_probability_to_evidence(p) == pytest.approx(e)
    assert human_probability_to_evidence(p) == pytest.approx(-e)


@pytest.mark.parametrize("bad", [-0.1, 1.1, math.nan])
def test_out_of_range_rejected(bad: float) -> None:
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        ai_probability_to_evidence(bad)


def test_percent() -> None:
    assert percent_to_unit(42) == 0.42
    with pytest.raises(ValueError, match="percentage"):
        percent_to_unit(101)


def test_fractions() -> None:
    assert fractions_to_evidence(1, 0) == 1
    assert fractions_to_evidence(0, 1) == -1
    assert fractions_to_evidence(0, 0, 1) == 0.5
    assert fractions_to_evidence(0.25, 0.75) == pytest.approx(-0.5)
    with pytest.raises(ValueError, match="zero"):
        fractions_to_evidence(0, 0, 0)


def test_labels() -> None:
    assert label_to_evidence(" AI ") == 1
    assert label_to_evidence("Human") == -1
    assert label_to_evidence("mixed") == 0
    assert label_to_evidence("weird") is None
    assert label_to_evidence(None) is None


def test_confidence() -> None:
    assert ordinal_confidence("HIGH") == 1
    assert ordinal_confidence("low") == pytest.approx(1 / 3)
    assert ordinal_confidence("?") is None
    assert ordinal_confidence(None) is None
    assert confidence_factor(None) == UNKNOWN_CONFIDENCE_FACTOR
    assert confidence_factor(0) == 0.5
    assert confidence_factor(1) == 1
    assert confidence_factor(7) == 1
