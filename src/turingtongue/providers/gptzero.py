# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""GPTZero adapter — https://gptzero.stoplight.io/docs/gptzero-api

``POST https://api.gptzero.me/v2/predict/text`` with ``x-api-key``. Returns
``class_probabilities`` over human / ai / mixed, a ``confidence_category`` and
sentence probabilities (no character offsets). GPTZero silently truncates input at
50,000 characters, so we cut an exact prefix ourselves and report it.
"""

from __future__ import annotations

from typing import Any

from turingtongue.models import ErrorCategory, Segment
from turingtongue.normalization.confidence import ordinal_confidence
from turingtongue.normalization.limits import PreparedInput
from turingtongue.normalization.scores import fractions_to_evidence
from turingtongue.providers.base import BaseProvider, Detection, DetectionOptions
from turingtongue.transport import HttpCaller

URL = "https://api.gptzero.me/v2/predict/text"


def classify_error(status: int, body: Any) -> tuple[ErrorCategory, bool] | None:
    """GPTZero reports exhausted monthly word quotas as HTTP 429."""
    message = str(body.get("error", "")) if isinstance(body, dict) else ""
    if status == 429 and "limit" in message.lower():
        return ErrorCategory.QUOTA_EXHAUSTED, False
    return None


class GPTZeroProvider(BaseProvider):
    """GPTZero document classification (human / ai / mixed)."""

    async def _detect(
        self, prepared: PreparedInput, caller: HttpCaller, options: DetectionOptions
    ) -> Detection:
        key = self.credential("GPTZERO_API_KEY")
        payload: dict[str, Any] = {
            "document": prepared.text,
            "multilingual": bool(self.option(options, "multilingual", False)),
        }
        model_version = self.option(options, "model_version", None)
        if model_version and not payload["multilingual"]:
            payload["modelVersion"] = str(model_version)
        outcome = await caller.request_json(
            "POST",
            URL,
            headers={"x-api-key": key, "Accept": "application/json"},
            json_body=payload,
            timeout_s=options.timeout_s,
            classify=classify_error,
        )
        body = outcome.body
        document = body["documents"][0]
        probs = document["class_probabilities"]
        p_ai, p_human, p_mixed = (float(probs.get(k, 0.0)) for k in ("ai", "human", "mixed"))
        category = document.get("confidence_category")
        segments = [
            Segment(start=None, end=None, score=float(s["generated_prob"]), kind="sentence")
            for s in document.get("sentences") or []
            if s.get("generated_prob") is not None
        ]
        warnings = []
        subclass = document.get("subclass") or {}
        for parent in subclass.values():
            if isinstance(parent, dict) and parent.get("predicted_class"):
                warnings.append(f"SUBCLASS={str(parent['predicted_class']).upper()}")
        return Detection(
            evidence=fractions_to_evidence(p_ai, p_human, p_mixed),
            score_semantics=(
                "class probabilities human/ai/mixed; evidence = (ai + ½·mixed − human); "
                "raw score = completely_generated_prob"
            ),
            raw_label=str(document.get("predicted_class")),
            raw_score=_float_or_none(document.get("completely_generated_prob")),
            raw_confidence=category,
            confidence=ordinal_confidence(category),
            model="gptzero",
            model_version=str(body.get("version") or document.get("version") or "") or None,
            segments=segments,
            warnings=warnings,
            attempts=outcome.attempts,
            rate_limit=outcome.rate_limit,
            raw=_without_input(body),
        )


def _float_or_none(value: Any) -> float | None:
    return None if value is None else float(value)


def _without_input(body: Any) -> Any:
    """Drop the echoed input text and sentences from the raw capture (privacy)."""
    if not isinstance(body, dict):
        return body
    trimmed = dict(body)
    trimmed["documents"] = [
        {k: v for k, v in doc.items() if k not in {"inputText", "sentences"}}
        for doc in body.get("documents", [])
        if isinstance(doc, dict)
    ]
    return trimmed
