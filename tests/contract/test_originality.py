# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""Contract tests for the Originality adapter."""

import json

import pytest
import respx

from tests.contract.conftest import Runner, fixture
from turingtongue.providers import originality

pytestmark = pytest.mark.contract
LONG = "This paragraph is long enough for every provider minimum. " * 12


# -- Originality --------------------------------------------------------------------
@respx.mock
def test_originality(run_provider: Runner) -> None:
    route = respx.post(originality.URL).respond(200, json=fixture("originality", "ok"))
    p = run_provider("originality", LONG, {"ORIGINALITY_API_KEY": "o-secret"}).providers[0]
    assert p.raw_score == pytest.approx(0.9526)
    assert p.normalized_evidence == pytest.approx(2 * 0.9526 - 1)
    assert p.raw_label == "ai"
    assert p.model == "lite"
    assert p.cost is not None
    assert p.cost.credits_used == 9
    assert p.segments[0].score == pytest.approx(0.9456973173429567)
    assert "properties" not in p.raw_response["results"]
    assert "blocks" not in p.raw_response["results"]["ai"]
    request = route.calls.last.request
    assert request.headers["X-OAI-API-KEY"] == "o-secret"
    sent = json.loads(request.content)
    assert sent["content"] == LONG
    assert sent["storeScan"] is False
    assert sent["check_plagiarism"] is False
    assert sent["aiModelVersion"] == "multilang"


@respx.mock
def test_originality_minimal(run_provider: Runner) -> None:
    respx.post(originality.URL).respond(200, json={"results": {"ai": {"confidence": {"AI": 0.1}}}})
    p = run_provider("originality", LONG, {"ORIGINALITY_API_KEY": "k"}, model="turbo").providers[0]
    assert p.raw_label is None
    assert p.model == "turbo"
    assert p.cost is None
