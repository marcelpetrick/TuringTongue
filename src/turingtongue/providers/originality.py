# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""Originality.ai adapter — https://docs.originality.ai

``POST https://api.originality.ai/api/v3/scan`` with ``X-OAI-API-KEY``. Only the AI
check is enabled (plagiarism, facts, readability … cost extra and add latency) and
``storeScan`` is false for privacy. Note: Originality accounts auto top-up credits by
default; this library cannot see or stop that.
"""

from __future__ import annotations

from typing import Any

from turingtongue.models import CostInfo, Segment
from turingtongue.normalization.limits import PreparedInput
from turingtongue.normalization.scores import ai_probability_to_evidence
from turingtongue.providers.base import BaseProvider, Detection, DetectionOptions
from turingtongue.transport import HttpCaller

URL = "https://api.originality.ai/api/v3/scan"
DEFAULT_MODEL = "multilang"


class OriginalityProvider(BaseProvider):
    """Originality.ai AI scan: AI vs Original confidence plus text blocks."""

    async def _detect(
        self, prepared: PreparedInput, caller: HttpCaller, options: DetectionOptions
    ) -> Detection:
        key = self.credential("ORIGINALITY_API_KEY")
        model = str(self.option(options, "model", DEFAULT_MODEL))
        payload = {
            "title": "turingtongue",
            "check_ai": True,
            "check_plagiarism": False,
            "check_facts": False,
            "check_readability": False,
            "check_grammar": False,
            "check_contentQuality": False,
            "check_ai_allowance": False,
            "storeScan": False,
            "excludedUrls": [],
            "aiModelVersion": model,
            "content": prepared.text,
        }
        outcome = await caller.request_json(
            "POST",
            URL,
            headers={"X-OAI-API-KEY": key, "Accept": "application/json"},
            json_body=payload,
            timeout_s=options.timeout_s,
        )
        results = outcome.body["results"]
        ai = results["ai"]
        p_ai = float(ai["confidence"]["AI"])
        classification = (ai.get("classification") or {}).get("AI")
        segments = [
            Segment(
                start=None,
                end=None,
                score=_float((b.get("result") or {}).get("fake")),
                kind="block",
            )
            for b in ai.get("blocks") or []
            if isinstance(b, dict)
        ]
        used = (results.get("credits") or {}).get("used")
        return Detection(
            evidence=ai_probability_to_evidence(p_ai),
            score_semantics="confidence.AI 0–1 (Original = 1 − AI); evidence = 2·AI − 1",
            raw_label=("ai" if classification == 1 else "original")
            if classification is not None
            else None,
            raw_score=p_ai,
            model=str(ai.get("aiModel") or model),
            segments=segments,
            cost=CostInfo(credits_used=float(used), billing_unit="credit (100 words)")
            if used is not None
            else None,
            attempts=outcome.attempts,
            rate_limit=outcome.rate_limit,
            raw=_trim(outcome.body),
        )


def _float(value: Any) -> float | None:
    return None if value is None else float(value)


def _trim(body: Any) -> Any:
    """Drop echoed content and blocks from the raw capture (privacy)."""
    results = dict(body.get("results") or {})
    results.pop("properties", None)
    if isinstance(results.get("ai"), dict):
        results["ai"] = {k: v for k, v in results["ai"].items() if k != "blocks"}
    return {"results": results}
