# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""Exceptions used inside the package and HTTP-status → category mapping.

Provider adapters raise :class:`ProviderFailure`; the orchestrator converts it into
a :class:`~turingtongue.models.ProviderError` record. Nothing here may carry secrets:
messages are passed through :func:`turingtongue.redaction.redact` before use.
"""

from __future__ import annotations

from turingtongue.models import ErrorCategory

RETRYABLE_CATEGORIES = frozenset(
    {
        ErrorCategory.RATE_LIMITED,
        ErrorCategory.TIMEOUT,
        ErrorCategory.NETWORK_ERROR,
        ErrorCategory.SERVICE_UNAVAILABLE,
    }
)


class TuringTongueError(Exception):
    """Base class of all package exceptions."""


class ConfigurationError(TuringTongueError):
    """Invalid user configuration, arguments or input (CLI exit code 3)."""


class ProviderFailure(TuringTongueError):
    """A provider attempt failed in a categorized, user-presentable way."""

    def __init__(
        self,
        category: ErrorCategory,
        message: str,
        *,
        http_status: int | None = None,
        retryable: bool | None = None,
        retry_after_s: float | None = None,
    ) -> None:
        super().__init__(message)
        self.category = category
        self.message = message
        self.http_status = http_status
        self.retryable = category in RETRYABLE_CATEGORIES if retryable is None else retryable
        self.retry_after_s = retry_after_s


def category_for_status(status: int) -> ErrorCategory:
    """Map an HTTP status code to the common error category.

    Only the status is used; we do not guess whether a provider *intended* to block us.
    """
    match status:
        case 401:
            return ErrorCategory.AUTHENTICATION_FAILED
        case 402:
            return ErrorCategory.QUOTA_EXHAUSTED
        case 403:
            return ErrorCategory.AUTHORIZATION_FAILED
        case 408 | 504:
            return ErrorCategory.TIMEOUT
        case 413:
            return ErrorCategory.INPUT_TOO_LARGE
        case 415 | 422:
            return ErrorCategory.UNSUPPORTED_INPUT
        case 429:
            return ErrorCategory.RATE_LIMITED
        case 500 | 502 | 503:
            return ErrorCategory.SERVICE_UNAVAILABLE
        case _ if 400 <= status < 500:
            return ErrorCategory.PROVIDER_ERROR
        case _ if status >= 500:
            return ErrorCategory.SERVICE_UNAVAILABLE
        case _:
            return ErrorCategory.UNKNOWN_ERROR


RETRYABLE_STATUSES = frozenset({408, 429, 500, 502, 503, 504})
"""HTTP statuses that may be retried (vision §11.4). 400/401/403 are never retried."""
