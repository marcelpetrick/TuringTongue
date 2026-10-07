# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""Contract tests for the ZeroGPT adapter."""
# ZeroGPT's fixture is synthetic: its docs publish a schema but no example response.

import json

import pytest
import respx

from tests.contract.conftest import Runner, fixture
from turingtongue.models import ErrorCategory
from turingtongue.providers import zerogpt

pytestmark = pytest.mark.contract
LONG = "This paragraph is long enough for every provider minimum. " * 12


# -- ZeroGPT ------------------------------------------------------------------------
@respx.mock
def test_zerogpt(run_provider: Runner) -> None:
    route = respx.post(zerogpt.URL).respond(200, json=fixture("zerogpt", "ok-synthetic"))
    p = run_provider("zerogpt", LONG, {"ZEROGPT_API_KEY": "z-secret"}).providers[0]
    assert p.normalized_evidence == pytest.approx(2 * 0.25 - 1)
    assert p.raw_label == "human"
    assert p.warning_codes == ["AI_WORDS=30/120"]
    assert p.cost is not None
    assert len(p.segments) == 1
    assert route.calls.last.request.headers["ApiKey"] == "z-secret"
    assert json.loads(route.calls.last.request.content) == {"input_text": LONG}


@respx.mock
def test_zerogpt_unsuccessful_envelope(run_provider: Runner) -> None:
    respx.post(zerogpt.URL).respond(200, json={"success": False, "message": "No balance"})
    error = run_provider("zerogpt", LONG, {"ZEROGPT_API_KEY": "k"}).errors[0]
    assert error.category is ErrorCategory.PROVIDER_ERROR
    assert "No balance" in error.message


@respx.mock
def test_zerogpt_minimal(run_provider: Runner) -> None:
    respx.post(zerogpt.URL).respond(200, json={"success": True, "data": {"fakePercentage": 90}})
    p = run_provider("zerogpt", LONG, {"ZEROGPT_API_KEY": "k"}).providers[0]
    assert p.raw_label is None
    assert p.cost is None
