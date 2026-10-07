# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""ZeroGPT Business API adapter — https://api.zerogpt.com/docs

``POST https://api.zerogpt.com/api/detect/detectText`` with header ``ApiKey`` and
``{"input_text": ...}``. Responses use ``{"success", "code", "data", "message"}``;
``data.fakePercentage`` is the share (0–100) of words judged AI. The documentation
is thin (no example response), so this provider is **not enabled by default**.
"""

from __future__ import annotations

from turingtongue.errors import ProviderFailure
from turingtongue.models import CostInfo, ErrorCategory, Segment
from turingtongue.normalization.limits import PreparedInput
from turingtongue.normalization.scores import ai_probability_to_evidence, percent_to_unit
from turingtongue.providers.base import BaseProvider, Detection, DetectionOptions
from turingtongue.transport import HttpCaller

URL = "https://api.zerogpt.com/api/detect/detectText"


class ZeroGPTProvider(BaseProvider):
    """ZeroGPT: percentage of AI words plus highlighted sentences."""

    async def _detect(
        self, prepared: PreparedInput, caller: HttpCaller, options: DetectionOptions
    ) -> Detection:
        key = self.credential("ZEROGPT_API_KEY")
        outcome = await caller.request_json(
            "POST",
            URL,
            headers={"ApiKey": key, "Accept": "application/json"},
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
