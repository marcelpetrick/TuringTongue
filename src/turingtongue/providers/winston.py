# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""Winston AI adapter — https://docs.gowinston.ai

``POST https://api.gowinston.ai/v2/ai-content-detection`` with a bearer token.
``score`` is a **human** score 0–100 (low = AI), so it is inverted. The response
reports credits used/remaining and flags detected evasion attacks.
"""

from __future__ import annotations

from typing import Any

from turingtongue.models import CostInfo, Segment
from turingtongue.normalization.limits import PreparedInput
from turingtongue.normalization.scores import human_probability_to_evidence, percent_to_unit
from turingtongue.providers.base import BaseProvider, Detection, DetectionOptions
from turingtongue.transport import HttpCaller

URL = "https://api.gowinston.ai/v2/ai-content-detection"
CREDENTIAL = "WINSTON_AI_API_KEY|WINSTON_API_KEY"


class WinstonProvider(BaseProvider):
    """Winston AI: human score 0–100, sentence scores, credit accounting."""

    async def _detect(
        self, prepared: PreparedInput, caller: HttpCaller, options: DetectionOptions
    ) -> Detection:
        key = self.credential(CREDENTIAL)
        payload: dict[str, Any] = {
            "text": prepared.text,
            "sentences": True,
            "language": str(self.option(options, "language", "auto")),
        }
        version = self.option(options, "version", None)
        if version:
            payload["version"] = str(version)
        outcome = await caller.request_json(
            "POST",
            URL,
            headers={"Authorization": f"Bearer {key}", "Accept": "application/json"},
            json_body=payload,
            timeout_s=options.timeout_s,
        )
        body = outcome.body
        human_score = float(body["score"])
        sentences = body.get("sentences") or []
        if isinstance(sentences, dict):  # schema says object, prose says array
            sentences = list(sentences.values())
        segments = [
            Segment(start=None, end=None, score=_float(s.get("score")), kind="sentence")
            for s in sentences
            if isinstance(s, dict)
        ]
        warnings = [
            f"ATTACK_DETECTED_{name.upper()}"
            for name, hit in (body.get("attack_detected") or {}).items()
            if hit
        ]
        used, remaining = body.get("credits_used"), body.get("credits_remaining")
        cost = (
            CostInfo(
                credits_used=_float(used),
                credits_remaining=_float(remaining),
                billing_unit="credit (1 per word)",
            )
            if used is not None or remaining is not None
            else None
        )
        return Detection(
            evidence=human_probability_to_evidence(percent_to_unit(human_score)),
            score_semantics="human score 0–100 (low = AI); evidence = 1 − 2·score/100",
            raw_label="human" if human_score >= 50 else "ai",
            raw_score=human_score,
            model="winston",
            model_version=str(body.get("version") or "") or None,
            segments=segments,
            cost=cost,
            warnings=warnings,
            attempts=outcome.attempts,
            rate_limit=outcome.rate_limit,
            raw={k: v for k, v in body.items() if k != "sentences"},
        )


def _float(value: Any) -> float | None:
    return None if value is None else float(value)
