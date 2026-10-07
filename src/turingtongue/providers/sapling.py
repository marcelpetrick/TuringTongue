# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""Sapling AI Detector adapter — https://sapling.ai/docs/api/detector/

``POST https://api.sapling.ai/api/v1/aidetect`` with ``Authorization: Bearer <key>``.
``score`` is 0 (human) … 1 (AI); sentence scores carry character offsets.
"""

from __future__ import annotations

from typing import Any

from turingtongue.models import CostInfo, ErrorCategory, Segment
from turingtongue.normalization.limits import PreparedInput
from turingtongue.normalization.scores import ai_probability_to_evidence
from turingtongue.providers.base import BaseProvider, Detection, DetectionOptions
from turingtongue.transport import HttpCaller

URL = "https://api.sapling.ai/api/v1/aidetect"


def classify_error(status: int, body: Any) -> tuple[ErrorCategory, bool] | None:
    """Sapling-specific error semantics from its API documentation."""
    message = str(body.get("msg", "")) if isinstance(body, dict) else ""
    has_retry_after = isinstance(body, dict) and "retry_after" in body
    if status == 400 and message.startswith("Unexpected error"):
        return ErrorCategory.SERVICE_UNAVAILABLE, True
    if status == 429 and not has_retry_after:
        # The request exceeds the key's whole allowance: retrying unchanged never helps.
        return ErrorCategory.QUOTA_EXHAUSTED, False
    if status == 429 and "monthly quota" in message.lower():
        return ErrorCategory.QUOTA_EXHAUSTED, False
    return None


class SaplingProvider(BaseProvider):
    """Sapling: document score, AI fraction, sentence scores with offsets."""

    async def _detect(
        self, prepared: PreparedInput, caller: HttpCaller, options: DetectionOptions
    ) -> Detection:
        key = self.credential("SAPLING_API_KEY")
        payload: dict[str, Any] = {
            "text": prepared.text,
            "sent_scores": True,
            "score_string": False,
            "return_usage": True,
        }
        version = self.option(options, "version", None)
        if version:
            payload["version"] = str(version)
        outcome = await caller.request_json(
            "POST",
            URL,
            headers={"Authorization": f"Bearer {key}"},
            json_body=payload,
            timeout_s=options.timeout_s,
            classify=classify_error,
        )
        body = outcome.body
        score = float(body["score"])
        segments = [
            Segment(
                start=int(s["start"]) if s.get("start") is not None else None,
                end=int(s["end"]) if s.get("end") is not None else None,
                score=float(s["score"]),
                kind="sentence",
            )
            for s in body.get("sentence_scores") or []
        ]
        usage = body.get("usage") or {}
        cost = (
            CostInfo(credits_used=float(usage["characters"]), billing_unit="characters")
            if "characters" in usage
            else None
        )
        warnings = []
        if body.get("ai_fraction") is not None:
            warnings.append(f"AI_FRACTION={float(body['ai_fraction']):.2f}")
        return Detection(
            evidence=ai_probability_to_evidence(score),
            score_semantics="score 0 = human … 1 = AI (uncalibrated); evidence = 2·score − 1",
            raw_label="ai" if score >= 0.5 else "human",
            raw_score=score,
            model="sapling-aidetect",
            model_version=str(body["version"]) if body.get("version") else None,
            segments=segments,
            cost=cost,
            warnings=warnings,
            attempts=outcome.attempts,
            rate_limit=outcome.rate_limit,
            raw=_without_text(body),
        )


def _without_text(body: dict[str, Any]) -> dict[str, Any]:
    """Raw capture without echoed input (text, sentences, tokens) — privacy."""
    trimmed = {k: v for k, v in body.items() if k not in {"text", "tokens", "score_string"}}
    trimmed["sentence_scores"] = [
        {k: v for k, v in s.items() if k != "sentence"} for s in body.get("sentence_scores") or []
    ]
    return trimmed
