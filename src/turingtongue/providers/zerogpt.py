# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""ZeroGPT Business API adapter — https://api.zerogpt.com/docs

``POST https://api.zerogpt.com/api/detect/detectText`` with both ``ApiKey`` and a
login JWT in ``Authorization: Bearer ...``. Responses use
``{"success", "code", "data", "message"}``;
``data.fakePercentage`` is the share (0–100) of words judged AI. The documentation
is thin (no example response), so this provider is **not enabled by default**.
"""

from __future__ import annotations

import base64
import binascii
import json
from datetime import UTC, datetime
from typing import Any

from turingtongue.errors import ProviderFailure
from turingtongue.models import CostInfo, ErrorCategory, Segment
from turingtongue.normalization.limits import PreparedInput
from turingtongue.normalization.scores import ai_probability_to_evidence, percent_to_unit
from turingtongue.providers.base import BaseProvider, Detection, DetectionOptions
from turingtongue.transport import HttpCaller

URL = "https://api.zerogpt.com/api/detect/detectText"
LOGIN_URL = "https://api.zerogpt.com/api/auth/login"
GENERATE_KEY_URL = "https://api.zerogpt.com/api/auth/generateApiKey"

_TOKEN_CACHE: dict[str, tuple[str, datetime]] = {}


def seed_token(account: str, token: str, expires: datetime) -> None:
    """Install a login JWT obtained by the explicit credential bootstrap."""
    _TOKEN_CACHE[account] = (token, expires)


def cached_token(account: str) -> str | None:
    """Return a still-valid cached JWT for ``account``."""
    cached = _TOKEN_CACHE.get(account)
    if cached is None:
        return None
    token, expires = cached
    if expires <= datetime.now(UTC):
        _TOKEN_CACHE.pop(account, None)
        return None
    return token


def clear_token_cache() -> None:
    """Forget all in-process ZeroGPT login JWTs."""
    _TOKEN_CACHE.clear()


def _jwt_expiry(token: str) -> datetime:
    """Read the required ``exp`` claim without treating it as signature validation."""
    try:
        parts = token.split(".")
        if len(parts) != 3 or not all(parts):
            raise ValueError
        payload = parts[1]
        padding = "=" * (-len(payload) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload + padding))
        expiry = claims["exp"]
        if not isinstance(expiry, int | float):
            raise TypeError
        parsed = datetime.fromtimestamp(expiry, UTC)
    except (
        binascii.Error,
        IndexError,
        KeyError,
        OSError,
        OverflowError,
        TypeError,
        UnicodeDecodeError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        raise ProviderFailure(
            ErrorCategory.SCHEMA_CHANGED,
            "ZeroGPT: login response token is not a JWT with a numeric exp claim",
            retryable=False,
        ) from exc
    if parsed <= datetime.now(UTC):
        raise ProviderFailure(
            ErrorCategory.AUTHENTICATION_FAILED,
            "ZeroGPT: login returned an expired JWT",
            retryable=False,
        )
    return parsed


def _envelope_data(body: Any, operation: str) -> Any:
    if not isinstance(body, dict):
        raise ProviderFailure(
            ErrorCategory.SCHEMA_CHANGED,
            f"ZeroGPT: {operation} response is not the documented envelope",
            retryable=False,
        )
    if body.get("success") is not True:
        raise ProviderFailure(
            ErrorCategory.AUTHENTICATION_FAILED,
            f"ZeroGPT: {operation} was not successful",
            retryable=False,
        )
    if "data" not in body:
        raise ProviderFailure(
            ErrorCategory.SCHEMA_CHANGED,
            f"ZeroGPT: {operation} response has no data field",
            retryable=False,
        )
    return body["data"]


async def login(
    caller: HttpCaller, email: str, password: str, timeout_s: float
) -> tuple[str, datetime]:
    """Exchange existing-account credentials for the documented login JWT."""
    outcome = await caller.request_json(
        "POST",
        LOGIN_URL,
        headers={"Accept": "application/json"},
        json_body={"email": email, "password": password},
        timeout_s=timeout_s,
    )
    data = _envelope_data(outcome.body, "login")
    if not isinstance(data, dict) or not isinstance(data.get("token"), str):
        raise ProviderFailure(
            ErrorCategory.SCHEMA_CHANGED,
            "ZeroGPT: login response has no data.token string",
            retryable=False,
        )
    token = data["token"].strip()
    if not token or len(token) > 16_384 or any(char in token for char in "\r\n\0"):
        raise ProviderFailure(
            ErrorCategory.SCHEMA_CHANGED,
            "ZeroGPT: login response contains an invalid token",
            retryable=False,
        )
    return token, _jwt_expiry(token)


async def generate_api_key(caller: HttpCaller, token: str, timeout_s: float) -> str:
    """Issue the documented non-expiring API key for an existing account."""
    outcome = await caller.request_json(
        "GET",
        GENERATE_KEY_URL,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        timeout_s=timeout_s,
    )
    data = _envelope_data(outcome.body, "API-key generation")
    candidates: list[str] = []
    if isinstance(data, str):
        candidates.append(data)
    elif isinstance(data, dict):
        for name in ("apiKey", "api_key", "ApiKey", "key"):
            value = data.get(name)
            if isinstance(value, str):
                candidates.append(value)
    unique = {candidate.strip() for candidate in candidates if candidate.strip()}
    if len(unique) != 1:
        raise ProviderFailure(
            ErrorCategory.SCHEMA_CHANGED,
            "ZeroGPT: API-key generation response has no unambiguous key field",
            retryable=False,
        )
    key = unique.pop()
    if len(key) < 8 or len(key) > 16_384 or any(char.isspace() or char == "\0" for char in key):
        raise ProviderFailure(
            ErrorCategory.SCHEMA_CHANGED,
            "ZeroGPT: API-key generation returned an invalid key",
            retryable=False,
        )
    return key


class ZeroGPTProvider(BaseProvider):
    """ZeroGPT: percentage of AI words plus highlighted sentences."""

    async def _detect(
        self, prepared: PreparedInput, caller: HttpCaller, options: DetectionOptions
    ) -> Detection:
        key = self.credential("ZEROGPT_API_KEY")
        token = self.settings.credential("ZEROGPT_BEARER_TOKEN") or cached_token(
            self.settings.credential("ZEROGPT_EMAIL") or ""
        )
        if token is None:
            raise ProviderFailure(
                ErrorCategory.NOT_CONFIGURED,
                "ZeroGPT: login JWT missing; run 'turingtongue init zerogpt --mode e2e "
                "--acquire-credential' or set ZEROGPT_BEARER_TOKEN",
            )
        outcome = await caller.request_json(
            "POST",
            URL,
            headers={
                "ApiKey": key,
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            },
            json_body={"input_text": prepared.text},
            timeout_s=options.timeout_s,
        )
        body = outcome.body
        if not body.get("success", False):
            message = str(body.get("message") or "request was not successful")
            raise ProviderFailure(ErrorCategory.PROVIDER_ERROR, f"ZeroGPT: {message}")
        data = body["data"]
        fake = float(data["fakePercentage"])
        highlighted = data.get("h") or []
        cost = data.get("cost")
        warnings = []
        if data.get("textWords") is not None and data.get("aiWords") is not None:
            warnings.append(f"AI_WORDS={data['aiWords']}/{data['textWords']}")
        return Detection(
            evidence=ai_probability_to_evidence(percent_to_unit(fake)),
            score_semantics="fakePercentage = % of words judged AI; evidence = 2·pct/100 − 1",
            raw_label=("human" if data["isHuman"] else "ai") if "isHuman" in data else None,
            raw_score=fake,
            model="zerogpt",
            segments=[Segment(None, None, label="ai", kind="sentence") for _ in highlighted],
            cost=CostInfo(credits_used=float(cost)) if isinstance(cost, int | float) else None,
            warnings=warnings,
            attempts=outcome.attempts,
            rate_limit=outcome.rate_limit,
            raw={
                k: v
                for k, v in data.items()
                if k in {"fakePercentage", "textWords", "aiWords", "isHuman"}
            },
        )

    def _secrets(self) -> list[str | None]:
        return [
            *super()._secrets(),
            self.settings.credential("ZEROGPT_BEARER_TOKEN"),
            cached_token(self.settings.credential("ZEROGPT_EMAIL") or ""),
        ]
