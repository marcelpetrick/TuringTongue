# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""Offline mock provider for smoke tests, demos and the Docker health check.

This is NOT a detector: it ignores the text and returns the answer configured via
the ``result`` provider option or ``TURINGTONGUE_MOCK_RESULT`` (``human`` (default),
``ai``, ``mixed`` or ``error``). It is never selected unless named explicitly.
"""

from __future__ import annotations

from turingtongue.errors import ProviderFailure
from turingtongue.models import ErrorCategory
from turingtongue.normalization.limits import PreparedInput
from turingtongue.providers.base import BaseProvider, Detection, DetectionOptions
from turingtongue.transport import HttpCaller

MOCK_ENV_VAR = "TURINGTONGUE_MOCK_RESULT"
_ANSWERS = {"human": (-0.8, 0.9), "ai": (0.8, 0.9), "mixed": (0.0, 0.5)}


class MockProvider(BaseProvider):
    """Returns a fixed, configured answer without any network access."""

    async def _detect(
        self, prepared: PreparedInput, caller: HttpCaller, options: DetectionOptions
    ) -> Detection:
        wanted = str(
            options.provider_options.get("result") or self.settings.env.get(MOCK_ENV_VAR) or "human"
        ).lower()
        if wanted == "error":
            raise ProviderFailure(ErrorCategory.SERVICE_UNAVAILABLE, "Mock: simulated outage")
        if wanted not in _ANSWERS:
            raise ProviderFailure(
                ErrorCategory.UNSUPPORTED_INPUT,
                f"Mock: unknown mock result '{wanted}' (use human, ai, mixed or error)",
            )
        evidence, confidence = _ANSWERS[wanted]
        return Detection(
            evidence=evidence,
            score_semantics="mock: fixed configured answer, not an analysis",
            raw_label=wanted,
            raw_score=(evidence + 1) / 2,
            raw_confidence=confidence,
            confidence=confidence,
            model="mock",
            model_version="1",
            raw={"mock_result": wanted},
        )
