# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""Pangram adapter — https://docs.pangram.com

Asynchronous task API: ``POST /task`` → ``task_id``; poll ``GET /task/{id}`` until
``STAGE_SUCCESS`` or ``STAGE_FAILED``. ``model`` is always sent (required since
2026-09-30). Polling is paced (default 1 s) and bounded by the provider timeout.
"""

from __future__ import annotations

import asyncio
from typing import Any

from turingtongue.errors import ProviderFailure
from turingtongue.models import ErrorCategory, Segment
from turingtongue.normalization.confidence import ordinal_confidence
from turingtongue.normalization.limits import PreparedInput
from turingtongue.normalization.scores import fractions_to_evidence
from turingtongue.providers.base import BaseProvider, Detection, DetectionOptions
from turingtongue.transport import HttpCaller

BASE_URL = "https://text.external-api.pangram.com"
DEFAULT_POLL_INTERVAL_S = 1.0
MIN_POLL_INTERVAL_S = 0.1


class PangramProvider(BaseProvider):
    """Pangram: AI / AI-assisted / human fractions plus labelled windows."""

    async def _detect(
        self, prepared: PreparedInput, caller: HttpCaller, options: DetectionOptions
    ) -> Detection:
        key = self.credential("PANGRAM_API_KEY")
        headers = {"x-api-key": key, "Accept": "application/json"}
        model = str(self.option(options, "model", "default"))
        interval = float(self.option(options, "poll_interval_s", DEFAULT_POLL_INTERVAL_S))
        created = await caller.request_json(
            "POST",
            f"{BASE_URL}/task",
            headers=headers,
            json_body={"text": prepared.text, "model": model, "public_dashboard_link": False},
            timeout_s=options.timeout_s,
        )
        task_id = str(created.body["task_id"])
        attempts = created.attempts
        polls = 0
        while True:
            polled = await caller.request_json(
                "GET", f"{BASE_URL}/task/{task_id}", headers=headers, timeout_s=options.timeout_s
            )
            attempts += polled.attempts
            polls += 1
            body = polled.body
            stage = body.get("stage")
            if stage == "STAGE_SUCCESS":
                break
            if stage == "STAGE_FAILED":
                headline = str(body.get("headline") or body.get("detail") or "task failed")
                category = (
                    ErrorCategory.UNSUPPORTED_INPUT
                    if headline.startswith("preprocessing")
                    else ErrorCategory.PROVIDER_ERROR
                )
                raise ProviderFailure(category, f"Pangram: {headline}", retryable=False)
            await asyncio.sleep(max(MIN_POLL_INTERVAL_S, interval))
        return self._parse(body, prepared, model, attempts, polls, polled.rate_limit)

    def _parse(
        self,
        body: dict[str, Any],
        prepared: PreparedInput,
        model: str,
        attempts: int,
        polls: int,
        rate_limit: Any,
    ) -> Detection:
        ai = float(body["fraction_ai"])
        assisted = float(body.get("fraction_ai_assisted", 0.0))
        human = float(body["fraction_human"])
        windows = body.get("windows") or []
        offsets_valid = body.get("text") == prepared.text
        segments = [
            Segment(
                start=int(w["start_index"]) if offsets_valid else None,
                end=int(w["end_index"]) if offsets_valid else None,
                label=w.get("label"),
                score=_float(w.get("ai_assistance_score")),
                kind="window",
            )
            for w in windows
        ]
        confidence = _mean_window_confidence(windows)
        warnings = [f"POLLS={polls}"]
        if windows and not offsets_valid:
            warnings.append("WINDOW_OFFSETS_REFER_TO_PROVIDER_NORMALIZED_TEXT")
        if any(w.get("is_humanized") for w in windows):
            warnings.append("HUMANIZER_DETECTED")
        return Detection(
            evidence=fractions_to_evidence(ai, human, assisted),
            score_semantics=(
                "fractions ai/ai_assisted/human of the text; evidence = (ai + ½·assisted − human); "
                "confidence = word-weighted mean of window confidence ranks"
            ),
            raw_label=str(body.get("prediction_short") or body.get("headline") or "") or None,
            raw_score=ai,
            raw_confidence=None if confidence is None else round(confidence, 3),
            confidence=confidence,
            model=model,
            model_version=str(body.get("version") or "") or None,
            segments=segments,
            warnings=warnings,
            attempts=attempts,
            rate_limit=rate_limit,
            raw={
                **{k: v for k, v in body.items() if k not in {"text", "windows"}},
                "windows": [{k: v for k, v in w.items() if k != "text"} for w in windows],
            },
        )


def _float(value: Any) -> float | None:
    return None if value is None else float(value)


def _mean_window_confidence(windows: list[dict[str, Any]]) -> float | None:
    total = 0.0
    weight = 0.0
    for window in windows:
        rank = ordinal_confidence(window.get("confidence"))
        if rank is None:
            continue
        words = float(window.get("word_count") or 1)
        total += rank * words
        weight += words
    return total / weight if weight else None
