# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""Secret redaction for errors, logs and recorded fixtures."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping

MASK = "***"
MIN_SECRET_LENGTH = 4
SENSITIVE_HEADERS = frozenset(
    {
        "authorization",
        "proxy-authorization",
        "cookie",
        "set-cookie",
        "x-api-key",
        "api-key",
        "apikey",
        "x-auth-token",
        "x-originality-key",
        "token",
    }
)
_BEARER = re.compile(r"(?i)\b(bearer|token|basic)\s+[A-Za-z0-9._~+/=-]{8,}")
_KEYVALUE = re.compile(r"(?i)\b(api[_-]?key|apikey|token|secret|password)(\s*[=:]\s*)[^\s&,;\"']+")


def redact(text: str, secrets: Iterable[str | None] = ()) -> str:
    """Remove known secret values and obvious credential patterns from ``text``."""
    for secret in secrets:
        if secret and len(secret) >= MIN_SECRET_LENGTH:
            text = text.replace(secret, MASK)
    text = _BEARER.sub(lambda m: f"{m.group(1)} {MASK}", text)
    return _KEYVALUE.sub(lambda m: f"{m.group(1)}{m.group(2)}{MASK}", text)


def redact_headers(headers: Mapping[str, str]) -> dict[str, str]:
    """Copy ``headers`` with every sensitive value masked."""
    return {k: (MASK if k.lower() in SENSITIVE_HEADERS else v) for k, v in headers.items()}


def is_sensitive_header(name: str) -> bool:
    """True when a header name carries credentials."""
    return name.lower() in SENSITIVE_HEADERS
