# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
import json

import pytest
import respx

from tests.contract.conftest import Runner, fixture
from turingtongue import Verdict
from turingtongue.models import ErrorCategory
from turingtongue.providers.gptzero import URL

pytestmark = pytest.mark.contract
ENV = {"GPTZERO_API_KEY": "gz-secret-key"}
TEXT = "The Natural Splendor of Uganda: A Symphony of Landscapes."


@respx.mock
def test_ai_example(run_provider: Runner) -> None:
    route = respx.post(URL).respond(200, json=fixture("gptzero", "ai"))
    result = run_provider("gptzero", TEXT, ENV, model_version="2025-11-28-base")
    p = result.providers[0]
    assert result.verdict is Verdict.AI
    assert p.raw_label == "ai"
    assert p.raw_confidence == "high"
    assert p.normalized_confidence == 1.0
    assert p.normalized_evidence == pytest.approx(0.999980510612919 + 0.5 * 1.9489387080966278e-05)
    assert p.raw_score == pytest.approx(0.9999562639446221)
    assert p.model_version == "2025-11-28-base"
    assert p.segments[0].start is None
    assert "SUBCLASS=PURE_AI" in p.warning_codes
    assert "inputText" not in json.dumps(p.raw_response)
    request = route.calls.last.request
    assert request.headers["x-api-key"] == "gz-secret-key"
    assert json.loads(request.content) == {
        "document": TEXT,
        "multilingual": False,
        "modelVersion": "2025-11-28-base",
    }


@respx.mock
def test_human_example_and_multilingual(run_provider: Runner) -> None:
    route = respx.post(URL).respond(200, json=fixture("gptzero", "human"))
    result = run_provider("gptzero", TEXT, ENV, multilingual=True, model_version="x")
    p = result.providers[0]
    assert result.verdict is Verdict.HUMAN
    assert p.normalized_evidence == pytest.approx((0.03 + 0.03 - 0.91) / 1.0)
    assert p.normalized_confidence == pytest.approx(2 / 3)
    assert "modelVersion" not in json.loads(route.calls.last.request.content)


@respx.mock
def test_truncates_at_50000_characters(run_provider: Runner) -> None:
    route = respx.post(URL).respond(200, json=fixture("gptzero", "human"))
    text = "word " * 12_000
    p = run_provider("gptzero", text, ENV).providers[0]
    assert p.truncated
    assert json.loads(route.calls.last.request.content)["document"] == text[:50_000]


@pytest.mark.parametrize(
    ("message", "category"),
    [
        ("Monthy limit of 1 million words has been reached.", ErrorCategory.QUOTA_EXHAUSTED),
        ("slow down", ErrorCategory.RATE_LIMITED),
    ],
)
@respx.mock
def test_429_quota_vs_rate(run_provider: Runner, message: str, category: ErrorCategory) -> None:
    respx.post(URL).respond(429, json={"error": message})
    assert run_provider("gptzero", TEXT, ENV).errors[0].category is category


@respx.mock
def test_missing_documents_is_schema_change(run_provider: Runner) -> None:
    respx.post(URL).respond(200, json={"documents": []})
    assert run_provider("gptzero", TEXT, ENV).errors[0].category is ErrorCategory.SCHEMA_CHANGED


def test_raw_trim_tolerates_non_dict() -> None:
    from turingtongue.providers.gptzero import _without_input

    assert _without_input([1]) == [1]
