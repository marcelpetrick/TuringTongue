# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
import random
from datetime import UTC, datetime

import httpx
import pytest
import respx

from turingtongue.errors import ProviderFailure
from turingtongue.models import ErrorCategory, RateLimitInfo
from turingtongue.transport import (
    HttpCaller,
    RetryPolicy,
    parse_retry_after,
    rate_limit_from_headers,
)

pytestmark = pytest.mark.unit
URL = "https://api.example.test/detect"


class Sleeper:
    def __init__(self) -> None:
        self.waits: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.waits.append(seconds)


def _caller(
    client: httpx.AsyncClient, sleeper: Sleeper, *, retries: int = 2, max_bytes: int = 10_000
) -> HttpCaller:
    return HttpCaller(
        client,
        provider_name="Example",
        policy=RetryPolicy(max_retries=retries, base_s=1.0, max_s=4.0, max_retry_after_s=10),
        max_response_bytes=max_bytes,
        secrets=["sk-secret-value"],
        sleep=sleeper,
        rng=random.Random(1),
    )


def test_backoff_is_bounded_full_jitter() -> None:
    policy = RetryPolicy(base_s=1.0, max_s=4.0)
    rng = random.Random(0)
    for index in range(10):
        assert 0 <= policy.backoff(index, rng) <= min(4.0, 2**index)


def test_parse_retry_after() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    assert parse_retry_after("5") == 5
    assert parse_retry_after("-3") == 0
    assert parse_retry_after(None) is None
    assert parse_retry_after("garbage") is None
    assert parse_retry_after("Thu, 01 Jan 2026 00:00:10 GMT", now=now) == 10
    assert parse_retry_after("Thu, 01 Jan 2026 00:00:10", now=now) == 10
    assert parse_retry_after("Wed, 31 Dec 2025 00:00:00 GMT", now=now) == 0
    assert parse_retry_after("Thu, 01 Jan 2026 00:00:10 GMT") is not None


def test_rate_limit_headers() -> None:
    headers = httpx.Headers(
        {"X-RateLimit-Limit": "100", "X-RateLimit-Remaining": "7", "Retry-After": "2"}
    )
    assert rate_limit_from_headers(headers) == RateLimitInfo(100, 7, None, 2.0)
    assert rate_limit_from_headers(httpx.Headers({})) is None
    assert rate_limit_from_headers(httpx.Headers({"ratelimit-limit": "x"})) is None


@respx.mock
async def test_success_returns_json() -> None:
    respx.post(URL).respond(200, json={"score": 0.5}, headers={"x-ratelimit-remaining": "3"})
    sleeper = Sleeper()
    async with httpx.AsyncClient() as client:
        caller = _caller(client, sleeper)
        outcome = await caller.request_json("POST", URL, json_body={"text": "x"}, timeout_s=5)
    assert outcome.body == {"score": 0.5}
    assert outcome.attempts == 1
    assert outcome.rate_limit is not None
    assert outcome.rate_limit.remaining == 3
    assert caller.network_ms >= 0
    assert sleeper.waits == []


@respx.mock
async def test_form_body_and_empty_response() -> None:
    route = respx.post(URL).respond(204)
    async with httpx.AsyncClient() as client:
        outcome = await _caller(client, Sleeper()).request_json(
            "POST", URL, form={"a": "b"}, timeout_s=5
        )
    assert outcome.body is None
    assert route.calls.last.request.content == b"a=b"


@respx.mock
async def test_retries_transient_then_succeeds() -> None:
    respx.post(URL).mock(
        side_effect=[
            httpx.Response(503),
            httpx.Response(429, headers={"Retry-After": "3"}),
            httpx.Response(200, json={"ok": True}),
        ]
    )
    sleeper = Sleeper()
    async with httpx.AsyncClient() as client:
        outcome = await _caller(client, sleeper).request_json("POST", URL, timeout_s=5)
    assert outcome.attempts == 3
    assert len(sleeper.waits) == 2
    assert sleeper.waits[1] >= 3


@respx.mock
async def test_retries_are_bounded() -> None:
    route = respx.post(URL).respond(502)
    sleeper = Sleeper()
    async with httpx.AsyncClient() as client:
        with pytest.raises(ProviderFailure) as info:
            await _caller(client, sleeper, retries=1).request_json("POST", URL, timeout_s=5)
    assert route.call_count == 2
    assert info.value.attempt_count == 2
    assert info.value.category is ErrorCategory.SERVICE_UNAVAILABLE


@pytest.mark.parametrize(
    ("status", "category"),
    [
        (400, ErrorCategory.PROVIDER_ERROR),
        (401, ErrorCategory.AUTHENTICATION_FAILED),
        (402, ErrorCategory.QUOTA_EXHAUSTED),
        (403, ErrorCategory.AUTHORIZATION_FAILED),
    ],
)
@respx.mock
async def test_client_errors_are_not_retried(status: int, category: ErrorCategory) -> None:
    route = respx.post(URL).respond(
        status, json={"error": "bad key sk-secret-value Bearer abcdefghijklmnop"}
    )
    async with httpx.AsyncClient() as client:
        with pytest.raises(ProviderFailure) as info:
            await _caller(client, Sleeper()).request_json("POST", URL, timeout_s=5)
    assert route.call_count == 1
    assert info.value.category is category
    assert info.value.http_status == status
    assert "sk-secret-value" not in info.value.message
    assert "abcdefghijklmnop" not in info.value.message
    assert "bad key" in info.value.message


@respx.mock
async def test_long_retry_after_stops_immediately() -> None:
    route = respx.post(URL).respond(429, headers={"Retry-After": "3600"}, text="slow down")
    sleeper = Sleeper()
    async with httpx.AsyncClient() as client:
        with pytest.raises(ProviderFailure) as info:
            await _caller(client, sleeper).request_json("POST", URL, timeout_s=5)
    assert route.call_count == 1
    assert sleeper.waits == []
    assert info.value.category is ErrorCategory.RATE_LIMITED
    assert info.value.retry_after_s == 3600
    assert "slow down" in info.value.message


@pytest.mark.parametrize(
    ("exc", "category"),
    [
        (httpx.ReadTimeout("t"), ErrorCategory.TIMEOUT),
        (httpx.ConnectError("c"), ErrorCategory.NETWORK_ERROR),
    ],
)
@respx.mock
async def test_network_failures_retried(exc: Exception, category: ErrorCategory) -> None:
    route = respx.post(URL).mock(side_effect=exc)
    async with httpx.AsyncClient() as client:
        with pytest.raises(ProviderFailure) as info:
            await _caller(client, Sleeper()).request_json("POST", URL, timeout_s=5)
    assert route.call_count == 3
    assert info.value.category is category


@respx.mock
async def test_invalid_json() -> None:
    respx.post(URL).respond(200, text="<html>")
    async with httpx.AsyncClient() as client:
        with pytest.raises(ProviderFailure) as info:
            await _caller(client, Sleeper()).request_json("POST", URL, timeout_s=5)
    assert info.value.category is ErrorCategory.INVALID_RESPONSE


@respx.mock
async def test_response_size_cap() -> None:
    respx.post(URL).respond(200, json={"x": "y" * 500})
    async with httpx.AsyncClient() as client:
        with pytest.raises(ProviderFailure) as info:
            await _caller(client, Sleeper(), max_bytes=100).request_json("POST", URL, timeout_s=5)
    assert info.value.category is ErrorCategory.INVALID_RESPONSE
    assert "exceeds" in info.value.message


@respx.mock
async def test_non_json_error_body() -> None:
    respx.post(URL).respond(500, text="")
    async with httpx.AsyncClient() as client:
        with pytest.raises(ProviderFailure) as info:
            await _caller(client, Sleeper(), retries=0).request_json("POST", URL, timeout_s=5)
    assert info.value.message == "Example: HTTP 500"
