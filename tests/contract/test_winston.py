# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""Contract tests for the Winston adapter."""

import json

import pytest
import respx

from tests.contract.conftest import Runner, fixture
from turingtongue import Verdict
from turingtongue.models import ErrorCategory
from turingtongue.providers import winston

pytestmark = pytest.mark.contract
LONG = "This paragraph is long enough for every provider minimum. " * 12


# -- Winston ------------------------------------------------------------------------
@respx.mock
def test_winston_inverts_human_score(run_provider: Runner) -> None:
    route = respx.post(winston.URL).respond(200, json=fixture("winston", "ok"))
    result = run_provider("winston", LONG, {"WINSTON_AI_API_KEY": "w-secret"}, version="5.0")
    p = result.providers[0]
    assert result.verdict is Verdict.AI
    assert p.raw_score == 12
    assert p.normalized_evidence == pytest.approx(1 - 2 * 0.12)
    assert p.raw_label == "ai"
    assert p.model_version == "5.0"
    assert p.cost is not None
    assert (p.cost.credits_used, p.cost.credits_remaining) == (412, 1588)
    assert p.warning_codes == ["ATTACK_DETECTED_HOMOGLYPH_ATTACK"]
    assert len(p.segments) == 2
    request = route.calls.last.request
    assert request.headers["Authorization"] == "Bearer w-secret"
    assert json.loads(request.content) == {
        "text": LONG,
        "sentences": True,
        "language": "auto",
        "version": "5.0",
    }


@respx.mock
def test_winston_alias_env_and_dict_sentences(run_provider: Runner) -> None:
    body = {"score": 90, "sentences": {"0": {"text": "x", "score": 90}}}
    respx.post(winston.URL).respond(200, json=body)
    p = run_provider("winston", LONG, {"WINSTON_API_KEY": "legacy-name"}).providers[0]
    assert p.raw_label == "human"
    assert p.cost is None
    assert len(p.segments) == 1


def test_winston_min_length_and_missing_key(run_provider: Runner) -> None:
    short = run_provider("winston", "too short", {"WINSTON_API_KEY": "k"})
    assert short.errors[0].category is ErrorCategory.INPUT_TOO_SHORT
    missing = run_provider("winston", LONG, {})
    assert missing.errors[0].category is ErrorCategory.NOT_CONFIGURED
    assert "WINSTON_AI_API_KEY or WINSTON_API_KEY" in missing.errors[0].message


@respx.mock
def test_winston_payment_required(run_provider: Runner) -> None:
    respx.post(winston.URL).respond(
        402, json={"error": "PAYMENT_REQUIRED", "description": "Insufficient credits"}
    )
    error = run_provider("winston", LONG, {"WINSTON_API_KEY": "k"}).errors[0]
    assert error.category is ErrorCategory.QUOTA_EXHAUSTED
