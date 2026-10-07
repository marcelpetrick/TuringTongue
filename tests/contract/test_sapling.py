# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
import json

import httpx
import pytest
import respx

from tests.contract.conftest import Runner, fixture
from turingtongue.models import ErrorCategory
from turingtongue.providers.sapling import URL

pytestmark = pytest.mark.contract
ENV = {"SAPLING_API_KEY": "sapling-secret-key-123"}
TEXT = "Here is a sentence. " * 20


@respx.mock
def test_parses_documented_response(run_provider: Runner) -> None:
    route = respx.post(URL).respond(200, json=fixture("sapling", "ok"))
    result = run_provider("sapling", TEXT, ENV, version="20260820")
    p = result.providers[0]
    assert p.ok
    assert p.raw_score == pytest.approx(0.8016229165451867)
    assert p.normalized_evidence == pytest.approx(2 * 0.8016229165451867 - 1)
    assert p.normalized_confidence is None
    assert p.model_version == "20260820"
    assert p.segments[0].start == 0
    assert p.segments[0].end == 19
    assert p.cost is not None
    assert p.cost.credits_used == 19
    assert "AI_FRACTION=1.00" in p.warning_codes
    request = route.calls.last.request
    assert request.headers["Authorization"] == "Bearer sapling-secret-key-123"
    body = json.loads(request.content)
    assert body["text"] == TEXT
    assert body["version"] == "20260820"
    assert "key" not in body


@respx.mock
def test_short_text_warns(run_provider: Runner) -> None:
    respx.post(URL).respond(200, json={"score": 0.1})
    p = run_provider("sapling", "Too short.", ENV).providers[0]
    assert "BELOW_RECOMMENDED_MINIMUM" in p.warning_codes
    assert p.model_version is None
    assert p.cost is None


@respx.mock
def test_huge_text_is_truncated_to_exact_prefix(run_provider: Runner) -> None:
    route = respx.post(URL).respond(200, json={"score": 0.2})
    text = "ä" * 200_005
    p = run_provider("sapling", text, ENV).providers[0]
    assert p.truncated
    assert json.loads(route.calls.last.request.content)["text"] == text[:200_000]
    assert p.input_coverage == pytest.approx(200_000 / 200_005)


@pytest.mark.parametrize(
    ("status", "body", "category", "calls"),
    [
        (400, {"msg": "Unexpected error, try again"}, ErrorCategory.SERVICE_UNAVAILABLE, 2),
        (400, {"msg": "Bad input"}, ErrorCategory.PROVIDER_ERROR, 1),
        (401, {"msg": "Invalid key"}, ErrorCategory.AUTHENTICATION_FAILED, 1),
        (402, {"msg": "credits depleted"}, ErrorCategory.QUOTA_EXHAUSTED, 1),
        (429, {"msg": "Too large for allowance"}, ErrorCategory.QUOTA_EXHAUSTED, 1),
        (
            429,
            {"msg": "Rate Limited. Monthly quota used.", "retry_after": 5},
            ErrorCategory.QUOTA_EXHAUSTED,
            1,
        ),
        (
            429,
            {"msg": "Rate limited. Capacity used.", "retry_after": 0},
            ErrorCategory.RATE_LIMITED,
            2,
        ),
        (502, {"msg": "upstream"}, ErrorCategory.SERVICE_UNAVAILABLE, 2),
    ],
)
@respx.mock
def test_error_mapping(
    run_provider: Runner, status: int, body: dict[str, object], category: ErrorCategory, calls: int
) -> None:
    route = respx.post(URL).mock(return_value=httpx.Response(status, json=body))
    result = run_provider("sapling", TEXT, ENV)
    assert result.errors[0].category is category
    assert route.call_count == calls
    assert "sapling-secret-key-123" not in result.to_json()


@respx.mock
def test_schema_drift(run_provider: Runner) -> None:
    respx.post(URL).respond(200, json={"probability": 0.3})
    assert run_provider("sapling", TEXT, ENV).errors[0].category is ErrorCategory.SCHEMA_CHANGED


def test_missing_key(run_provider: Runner) -> None:
    result = run_provider("sapling", TEXT, {})
    assert result.errors[0].category is ErrorCategory.NOT_CONFIGURED
