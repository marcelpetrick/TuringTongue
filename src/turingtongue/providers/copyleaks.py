# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""Copyleaks AI Content Detector adapter — https://docs.copyleaks.com

Two steps: ``POST https://id.copyleaks.com/v3/account/login/api`` with email + key
returns a 48 h bearer token (login is limited to 12 calls / 15 min, so the token is
cached in memory per account and refreshed only near expiry); then
``POST https://api.copyleaks.com/v2/writer-detector/{scanId}/check``.

Sandbox mode (``COPYLEAKS_SANDBOX=1`` or option ``sandbox``) returns **mock**
classifications: such results are shown but excluded from the ensemble.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from turingtongue.errors import ProviderFailure
from turingtongue.models import CostInfo, ErrorCategory, Segment
from turingtongue.normalization.limits import PreparedInput
from turingtongue.normalization.scores import fractions_to_evidence
from turingtongue.providers.base import BaseProvider, Detection, DetectionOptions
from turingtongue.transport import HttpCaller

LOGIN_URL = "https://id.copyleaks.com/v3/account/login/api"
CHECK_URL = "https://api.copyleaks.com/v2/writer-detector/{scan_id}/check"
REFRESH_MARGIN = timedelta(minutes=10)
FALLBACK_LIFETIME = timedelta(hours=47)
SANDBOX_REASON = "Copyleaks sandbox returns mock classifications"


@dataclass(frozen=True, slots=True)
class _Token:
    value: str
    expires: datetime


_TOKENS: dict[str, _Token] = {}
"""In-memory token cache keyed by account email (never written to disk)."""


def clear_token_cache() -> None:
    """Forget cached Copyleaks tokens (tests, credential rotation)."""
    _TOKENS.clear()


def _parse_expiry(value: Any) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return datetime.now(UTC) + FALLBACK_LIFETIME
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


class CopyleaksProvider(BaseProvider):
    """Copyleaks writer-detector: per-section human/AI classification + summary."""

    async def _token(self, caller: HttpCaller, options: DetectionOptions, *, fresh: bool) -> str:
        email = self.credential("COPYLEAKS_EMAIL")
        key = self.credential("COPYLEAKS_API_KEY")
        cached = _TOKENS.get(email)
        if not fresh and cached and cached.expires - REFRESH_MARGIN > datetime.now(UTC):
            return cached.value
        outcome = await caller.request_json(
            "POST",
            LOGIN_URL,
            headers={"Accept": "application/json"},
            json_body={"email": email, "key": key},
            timeout_s=options.timeout_s,
        )
        token = _Token(
            str(outcome.body["access_token"]), _parse_expiry(outcome.body.get(".expires"))
        )
        _TOKENS[email] = token
        return token.value

    async def _detect(
        self, prepared: PreparedInput, caller: HttpCaller, options: DetectionOptions
    ) -> Detection:
        sandbox = bool(
            self.option(options, "sandbox", self.settings.env.get("COPYLEAKS_SANDBOX") == "1")
        )
        payload: dict[str, Any] = {"text": prepared.text, "sandbox": sandbox}
        for name in ("language", "sensitivity", "explain"):
            value = self.option(options, name, None)
            if value is not None:
                payload[name] = value
        url = CHECK_URL.format(scan_id=uuid.uuid4().hex)
        token = await self._token(caller, options, fresh=False)
        try:
            outcome = await self._check(caller, url, token, payload, options)
        except ProviderFailure as failure:
            if failure.category is not ErrorCategory.AUTHENTICATION_FAILED:
                raise
            # Token revoked/expired early: log in again exactly once.
            token = await self._token(caller, options, fresh=True)
            outcome = await self._check(caller, url, token, payload, options)
        body = outcome.body
        summary = body["summary"]
        ai, human = float(summary["ai"]), float(summary["human"])
        document = body.get("scannedDocument") or {}
        credits = document.get("credits", document.get("actualCredits"))
        segments = []
        for section in body.get("results") or []:
            label = {1: "human", 2: "ai"}.get(section.get("classification"))
            for match in section.get("matches") or []:
                chars = (match.get("text") or {}).get("chars") or {}
                for start, length in zip(
                    chars.get("starts", []), chars.get("lengths", []), strict=False
                ):
                    segments.append(
                        Segment(
                            start=int(start),
                            end=int(start) + int(length),
                            label=label,
                            score=_float(section.get("probability")),
                            kind="section",
                        )
                    )
        return Detection(
            evidence=fractions_to_evidence(ai, human) if ai + human > 0 else 0.0,
            score_semantics="summary ai/human confidences; evidence = (ai − human)/(ai + human)",
            raw_label="ai" if ai > human else "human",
            raw_score=ai,
            model="copyleaks-writer-detector",
            model_version=str(body.get("modelVersion") or "") or None,
            segments=segments,
            cost=CostInfo(
                credits_used=_float(credits),
                billing_unit="credit (page of up to 250 words)",
            )
            if credits is not None
            else None,
            warnings=["SANDBOX_MOCK_RESULT"] if sandbox else [],
            attempts=outcome.attempts,
            rate_limit=outcome.rate_limit,
            raw=body,
            exclude_reason=SANDBOX_REASON if sandbox else None,
        )

    async def _check(
        self,
        caller: HttpCaller,
        url: str,
        token: str,
        payload: dict[str, Any],
        options: DetectionOptions,
    ) -> Any:
        return await caller.request_json(
            "POST",
            url,
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            json_body=payload,
            timeout_s=options.timeout_s,
        )

    def _secrets(self) -> list[str | None]:
        return [*super()._secrets(), *(t.value for t in _TOKENS.values())]


def _float(value: Any) -> float | None:
    return None if value is None else float(value)
