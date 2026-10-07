# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""Hive AI-Generated Text Detection adapter — https://docs.thehive.ai

``POST https://api.thehive.ai/api/v2/task/sync`` with ``authorization: token <key>``
and **form** field ``text_data``. Hive splits the text into 2,048-character chunks
itself; those chunk scores are exposed as segments (provider-side segmentation, not
local preprocessing). The docs show two envelope shapes; both are accepted.
"""

from __future__ import annotations

from typing import Any

from turingtongue.errors import ProviderFailure
from turingtongue.models import ErrorCategory, Segment
from turingtongue.normalization.limits import PreparedInput
from turingtongue.normalization.scores import ai_probability_to_evidence
from turingtongue.providers.base import BaseProvider, Detection, DetectionOptions
from turingtongue.transport import HttpCaller

URL = "https://api.thehive.ai/api/v2/task/sync"
AI_CLASS = "ai_generated"


def classify_error(status: int, body: Any) -> tuple[ErrorCategory, bool] | None:
    """Hive documents 405 as 'insufficient balance' and 403 as an API-key problem."""
    if status == 405:
        return ErrorCategory.QUOTA_EXHAUSTED, False
    if status == 403:
        return ErrorCategory.AUTHENTICATION_FAILED, False
    return None


def _class_score(entries: Any, wanted: str) -> float | None:
    """Accept ``[{"class": c, "score": s}]`` and ``[{c: s}]`` shapes."""
    for entry in entries or []:
        if not isinstance(entry, dict):
            continue
        if entry.get("class") == wanted and "score" in entry:
            return float(entry["score"])
        if wanted in entry:
            return float(entry[wanted])
    return None


class HiveProvider(BaseProvider):
    """Hive: aggregate ai_generated score plus provider-side chunk scores."""

    async def _detect(
        self, prepared: PreparedInput, caller: HttpCaller, options: DetectionOptions
    ) -> Detection:
        key = self.credential("HIVE_API_KEY")
        outcome = await caller.request_json(
            "POST",
            URL,
            headers={"authorization": f"token {key}", "accept": "application/json"},
            form={"text_data": prepared.text},
            timeout_s=options.timeout_s,
            classify=classify_error,
        )
        status = outcome.body["status"]
        if isinstance(status, list):
            status = status[0]
        code = str((status.get("status") or {}).get("code", "0"))
        if code != "0":
            message = (status.get("status") or {}).get("message", "task failed")
            raise ProviderFailure(ErrorCategory.PROVIDER_ERROR, f"Hive: {message} (code {code})")
        response = status["response"]
        score = _class_score(response.get("aggregate_score"), AI_CLASS)
        if score is None:
            raise self.schema_error("Hive: no ai_generated aggregate score in response")
        segments = [
            Segment(
                start=_int(chunk.get("start_index")),
                end=_int(chunk.get("end_index")),
                score=_class_score(chunk.get("classes"), AI_CLASS),
                kind="chunk",
            )
            for chunk in response.get("output") or []
            if isinstance(chunk, dict)
        ]
        model_input = response.get("input") or {}
        return Detection(
            evidence=ai_probability_to_evidence(score),
            score_semantics="aggregate ai_generated score 0–1; evidence = 2·score − 1",
            raw_label="ai" if score >= 0.5 else "human",
            raw_score=score,
            model=str(model_input.get("model_type") or "hive-ai-text"),
            model_version=str(model_input.get("model_version") or "") or None,
            segments=segments,
            attempts=outcome.attempts,
            rate_limit=outcome.rate_limit,
            raw={"status": {"response": {k: v for k, v in response.items() if k != "input"}}},
        )


def _int(value: Any) -> int | None:
    return None if value is None else int(value)
