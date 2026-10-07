# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
import pytest

from turingtongue.errors import (
    RETRYABLE_STATUSES,
    ProviderFailure,
    category_for_status,
)
from turingtongue.models import ErrorCategory
from turingtongue.redaction import MASK, is_sensitive_header, redact, redact_headers

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("status", "category"),
    [
        (401, ErrorCategory.AUTHENTICATION_FAILED),
        (402, ErrorCategory.QUOTA_EXHAUSTED),
        (403, ErrorCategory.AUTHORIZATION_FAILED),
        (408, ErrorCategory.TIMEOUT),
        (504, ErrorCategory.TIMEOUT),
        (413, ErrorCategory.INPUT_TOO_LARGE),
        (422, ErrorCategory.UNSUPPORTED_INPUT),
        (429, ErrorCategory.RATE_LIMITED),
        (503, ErrorCategory.SERVICE_UNAVAILABLE),
        (400, ErrorCategory.PROVIDER_ERROR),
        (418, ErrorCategory.PROVIDER_ERROR),
        (599, ErrorCategory.SERVICE_UNAVAILABLE),
        (302, ErrorCategory.UNKNOWN_ERROR),
    ],
)
def test_category_for_status(status: int, category: ErrorCategory) -> None:
    assert category_for_status(status) is category


def test_retryable_statuses_exclude_client_errors() -> None:
    assert {400, 401, 403}.isdisjoint(RETRYABLE_STATUSES)
    assert {408, 429, 500, 502, 503, 504} == RETRYABLE_STATUSES


def test_provider_failure_defaults_retryable_by_category() -> None:
    assert ProviderFailure(ErrorCategory.TIMEOUT, "x").retryable
    assert not ProviderFailure(ErrorCategory.AUTHENTICATION_FAILED, "x").retryable
    assert not ProviderFailure(ErrorCategory.TIMEOUT, "x", retryable=False).retryable
    failure = ProviderFailure(ErrorCategory.RATE_LIMITED, "slow", http_status=429, retry_after_s=2)
    assert (failure.http_status, failure.retry_after_s, str(failure)) == (429, 2, "slow")


def test_redact_known_secret_and_patterns() -> None:
    text = "key sk-SECRET123 Authorization: Bearer abcdefghijkl api_key=zzz9 token: qq"
    out = redact(text, ["sk-SECRET123", None, "ab"])
    assert "sk-SECRET123" not in out
    assert "abcdefghijkl" not in out
    assert "zzz9" not in out
    assert f"api_key={MASK}" in out


def test_redact_headers() -> None:
    headers = {"Authorization": "Bearer x", "X-API-Key": "k", "Content-Type": "json"}
    assert redact_headers(headers) == {
        "Authorization": MASK,
        "X-API-Key": MASK,
        "Content-Type": "json",
    }
    assert is_sensitive_header("Cookie")
    assert not is_sensitive_header("Accept")
