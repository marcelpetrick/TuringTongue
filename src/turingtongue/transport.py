# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""HTTP transport shared by API adapters: finite timeouts, bounded retries, body cap.

Retry policy (vision §11.4):

* retried: HTTP 408, 429, 500, 502, 503, 504 and connect/read/network timeouts;
* never retried: 400, 401, 402, 403, other 4xx, invalid responses;
* exponential backoff with full jitter: ``uniform(0, min(max_s, base_s * 2**attempt))``;
* ``Retry-After`` is honoured as a *minimum* wait; when it exceeds ``max_retry_after_s``
  we stop and report ``RATE_LIMITED`` instead of hammering or silently waiting forever.
"""

from __future__ import annotations

import asyncio
import email.utils
import json
import random
import time
from collections.abc import Awaitable, Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx

from turingtongue.errors import RETRYABLE_STATUSES, ProviderFailure, category_for_status
from turingtongue.models import ErrorCategory, RateLimitInfo
from turingtongue.redaction import redact

MAX_ERROR_DETAIL = 300

ErrorClassifier = Callable[[int, Any], "tuple[ErrorCategory, bool] | None"]
"""Adapter hook: ``(status, parsed_body) -> (category, retryable)`` or None for the default."""


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Bounded retry configuration."""

    max_retries: int = 2
    base_s: float = 0.5
    max_s: float = 8.0
    max_retry_after_s: float = 30.0

    def backoff(self, retry_index: int, rng: random.Random) -> float:
        """Full-jitter exponential backoff for the ``retry_index``-th retry (0-based)."""
        ceiling = min(self.max_s, self.base_s * (2**retry_index))
        return rng.uniform(0, ceiling)


@dataclass(frozen=True, slots=True)
class HttpOutcome:
    """Successful (2xx) JSON response plus request metadata."""

    status: int
    body: Any
    headers: Mapping[str, str]
    attempts: int
    rate_limit: RateLimitInfo | None


def parse_retry_after(value: str | None, *, now: datetime | None = None) -> float | None:
    """Parse ``Retry-After`` (delta-seconds or HTTP-date) into seconds (>= 0)."""
    if not value:
        return None
    value = value.strip()
    try:
        return max(0.0, float(value))
    except ValueError:
        pass
    try:
        when = email.utils.parsedate_to_datetime(value)
    except TypeError, ValueError:
        return None
    current = now or datetime.now(UTC)
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    return max(0.0, (when - current).total_seconds())


def _int_header(headers: Mapping[str, str], *names: str) -> int | None:
    for name in names:
        raw = headers.get(name)
        if raw is not None:
            try:
                return int(float(raw.split(",")[0].strip()))
            except ValueError:
                return None
    return None


def rate_limit_from_headers(headers: Mapping[str, str]) -> RateLimitInfo | None:
    """Extract common rate-limit headers; None when the provider sends none."""
    info = RateLimitInfo(
        limit=_int_header(headers, "x-ratelimit-limit", "ratelimit-limit"),
        remaining=_int_header(headers, "x-ratelimit-remaining", "ratelimit-remaining"),
        reset=headers.get("x-ratelimit-reset") or headers.get("ratelimit-reset"),
        retry_after_s=parse_retry_after(headers.get("retry-after")),
    )
    return None if info == RateLimitInfo() else info


def _try_json(body: bytes) -> Any:
    try:
        return json.loads(body)
    except ValueError:
        return None


def _error_detail(body: bytes, secrets: Iterable[str | None]) -> str:
    text = body.decode("utf-8", errors="replace")
    try:
        parsed = json.loads(text)
    except ValueError:
        parsed = None
    if isinstance(parsed, dict):
        for key in ("error", "message", "detail", "msg", "errors"):
            if key in parsed:
                text = str(parsed[key])
                break
    text = " ".join(text.split())
    return redact(text, secrets)[:MAX_ERROR_DETAIL]


class HttpCaller:
    """Performs JSON requests for one provider with the shared policy."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        provider_name: str,
        policy: RetryPolicy,
        max_response_bytes: int,
        secrets: Iterable[str | None] = (),
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        rng: random.Random | None = None,
    ) -> None:
        self._client = client
        self._name = provider_name
        self._policy = policy
        self._max_bytes = max_response_bytes
        self._secrets = tuple(secrets)
        self._sleep = sleep
        self._rng = rng or random.Random()  # noqa: S311 - jitter, not cryptography
        self.network_ms = 0.0

    async def request_json(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        json_body: Any = None,
        form: Mapping[str, str] | None = None,
        timeout_s: float,
        classify: ErrorClassifier | None = None,
    ) -> HttpOutcome:
        """Send a request, retrying transient failures; return parsed JSON on 2xx.

        ``classify`` lets an adapter override the category/retryability of documented
        provider-specific error responses.
        """
        attempt = 0
        while True:
            attempt += 1
            try:
                return await self._attempt(
                    method, url, headers, json_body, form, timeout_s, attempt, classify
                )
            except ProviderFailure as failure:
                failure.attempt_count = attempt
                retries_used = attempt - 1
                if not failure.retryable or retries_used >= self._policy.max_retries:
                    raise
                wait = self._policy.backoff(retries_used, self._rng)
                if failure.retry_after_s is not None:
                    if failure.retry_after_s > self._policy.max_retry_after_s:
                        raise
                    wait = max(wait, failure.retry_after_s)
                await self._sleep(wait)

    async def _attempt(
        self,
        method: str,
        url: str,
        headers: Mapping[str, str] | None,
        json_body: Any,
        form: Mapping[str, str] | None,
        timeout_s: float,
        attempt: int,
        classify: ErrorClassifier | None,
    ) -> HttpOutcome:
        started = time.perf_counter()
        try:
            async with self._client.stream(
                method,
                url,
                headers=dict(headers or {}),
                json=json_body,
                data=dict(form) if form is not None else None,
                timeout=timeout_s,
            ) as response:
                body = await self._read_capped(response)
        except httpx.TimeoutException as exc:
            raise ProviderFailure(
                ErrorCategory.TIMEOUT, f"{self._name}: request timed out ({type(exc).__name__})"
            ) from exc
        except httpx.RequestError as exc:
            raise ProviderFailure(
                ErrorCategory.NETWORK_ERROR,
                f"{self._name}: network error ({type(exc).__name__})",
            ) from exc
        finally:
            self.network_ms += (time.perf_counter() - started) * 1000
        rate_limit = rate_limit_from_headers(response.headers)
        if not 200 <= response.status_code < 300:
            category = category_for_status(response.status_code)
            retryable = response.status_code in RETRYABLE_STATUSES
            if classify is not None:
                override = classify(response.status_code, _try_json(body))
                if override is not None:
                    category, retryable = override
            detail = _error_detail(body, self._secrets)
            raise ProviderFailure(
                category,
                f"{self._name}: HTTP {response.status_code}" + (f": {detail}" if detail else ""),
                http_status=response.status_code,
                retryable=retryable,
                retry_after_s=rate_limit.retry_after_s if rate_limit else None,
                rate_limit=rate_limit,
            )
        try:
            parsed = json.loads(body) if body else None
        except ValueError as exc:
            raise ProviderFailure(
                ErrorCategory.INVALID_RESPONSE,
                f"{self._name}: response is not valid JSON",
                http_status=response.status_code,
                retryable=False,
            ) from exc
        return HttpOutcome(response.status_code, parsed, response.headers, attempt, rate_limit)

    async def _read_capped(self, response: httpx.Response) -> bytes:
        chunks: list[bytes] = []
        size = 0
        async for chunk in response.aiter_bytes():
            size += len(chunk)
            if size > self._max_bytes:
                raise ProviderFailure(
                    ErrorCategory.INVALID_RESPONSE,
                    f"{self._name}: response exceeds {self._max_bytes} bytes",
                    http_status=response.status_code,
                    retryable=False,
                )
            chunks.append(chunk)
        return b"".join(chunks)
