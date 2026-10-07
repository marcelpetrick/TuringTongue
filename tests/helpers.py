# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""Test-only adapters and registry builders."""

from __future__ import annotations

import asyncio

from turingtongue.errors import ProviderFailure
from turingtongue.models import ErrorCategory
from turingtongue.normalization.limits import PreparedInput
from turingtongue.normalization.scores import ai_probability_to_evidence
from turingtongue.providers.base import BaseProvider, Detection, DetectionOptions
from turingtongue.registry import Registry
from turingtongue.transport import HttpCaller

ECHO_URL = "https://echo.example.test/detect"


class EchoProvider(BaseProvider):
    """Posts the text to ECHO_URL and reads ``{"p_ai": float}``."""

    async def _detect(
        self, prepared: PreparedInput, caller: HttpCaller, options: DetectionOptions
    ) -> Detection:
        key = self.credential("ECHO_KEY")
        outcome = await caller.request_json(
            "POST",
            ECHO_URL,
            headers={"X-Api-Key": key},
            json_body={"text": prepared.text},
            timeout_s=options.timeout_s,
        )
        p_ai = float(outcome.body["p_ai"])
        return Detection(
            evidence=ai_probability_to_evidence(p_ai),
            score_semantics="p_ai",
            raw_score=p_ai,
            attempts=outcome.attempts,
            raw=outcome.body,
        )


class SlowProvider(BaseProvider):
    async def _detect(
        self, prepared: PreparedInput, caller: HttpCaller, options: DetectionOptions
    ) -> Detection:
        await asyncio.sleep(10)
        raise ProviderFailure(ErrorCategory.UNKNOWN_ERROR, "unreachable")  # pragma: no cover


class CrashProvider:
    def __init__(self, spec: object, settings: object, client: object) -> None:
        self.spec = spec

    async def detect(self, text: str, *, options: DetectionOptions) -> object:
        raise RuntimeError("boom")


def registry(extra: str = "") -> Registry:
    return Registry.from_toml(
        f"""
[providers.echo]
name = "Echo"
transport = "api"
adapter = "tests.helpers:EchoProvider"
credential_env = ["ECHO_KEY"]
enabled_by_default = true
known_max_input = 10
recommended_min_input = 3
limit_unit = "words"

[providers.echo2]
name = "Echo Two"
transport = "api"
adapter = "tests.helpers:EchoProvider"
credential_env = ["ECHO_KEY", "ECHO2_EMAIL"]
enabled_by_default = true

[providers.web]
name = "Web"
transport = "browser"
adapter = "tests.helpers:SlowProvider"
requires_credentials = false
enabled_by_default = false

[providers.mock]
name = "Mock"
transport = "mock"
adapter = "turingtongue.providers.mock:MockProvider"
requires_credentials = false
{extra}
"""
    )
