# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""Review B — adversarial end-to-end scenarios (vision §21.3) across all real adapters.

Every provider endpoint is mocked with respx; the full orchestrator, adapters, limits,
ensemble and serialization run for real.
"""

import json
from typing import Any
from urllib.parse import parse_qs

import httpx
import pytest
import respx

from tests.contract.conftest import fixture
from turingtongue import Checker, Settings, Verdict
from turingtongue.models import ErrorCategory
from turingtongue.providers import copyleaks

pytestmark = pytest.mark.integration

ENV = {
    "SAPLING_API_KEY": "k1",
    "GPTZERO_API_KEY": "k2",
    "PANGRAM_API_KEY": "k3",
    "COPYLEAKS_EMAIL": "e@example.test",
    "COPYLEAKS_API_KEY": "k4",
    "WINSTON_AI_API_KEY": "k5",
    "ORIGINALITY_API_KEY": "k6",
    "HIVE_API_KEY": "k7",
}
URLS = {
    "sapling": "https://api.sapling.ai/api/v1/aidetect",
    "gptzero": "https://api.gptzero.me/v2/predict/text",
    "winston": "https://api.gowinston.ai/v2/ai-content-detection",
    "originality": "https://api.originality.ai/api/v3/scan",
    "hive": "https://api.thehive.ai/api/v2/task/sync",
}
PANGRAM = "https://text.external-api.pangram.com"
COPYLEAKS_CHECK = respx.patterns.M(
    url__regex=r"https://api\.copyleaks\.com/v2/writer-detector/.+/check"
)


def _bodies(ai: bool) -> dict[str, Any]:
    p = 0.95 if ai else 0.05
    return {
        "sapling": {"score": p},
        "gptzero": {"documents": [{"class_probabilities": {"ai": p, "human": 1 - p, "mixed": 0}}]},
        "winston": {"score": (1 - p) * 100},
        "originality": {"results": {"ai": {"confidence": {"AI": p}}}},
        "hive": {
            "status": [
                {
                    "status": {"code": "0"},
                    "response": {"aggregate_score": [{"class": "ai_generated", "score": p}]},
                }
            ]
        },
        "pangram": {
            "stage": "STAGE_SUCCESS",
            "fraction_ai": p,
            "fraction_human": 1 - p,
            "windows": [],
        },
        "copyleaks": {"summary": {"ai": p, "human": 1 - p}},
    }


def _mock_all(ai_for: set[str], failing: dict[str, int] | None = None) -> dict[str, respx.Route]:
    failing = failing or {}
    copyleaks.clear_token_cache()
    routes: dict[str, respx.Route] = {}
    for pid, url in URLS.items():
        body = _bodies(pid in ai_for)[pid]
        routes[pid] = respx.post(url).mock(
            return_value=httpx.Response(failing[pid])
            if pid in failing
            else httpx.Response(200, json=body)
        )
    respx.post(f"{PANGRAM}/task").respond(200, json={"task_id": "t"})
    routes["pangram"] = respx.get(f"{PANGRAM}/task/t").respond(
        200, json=_bodies("pangram" in ai_for)["pangram"]
    )
    respx.post(copyleaks.LOGIN_URL).respond(200, json=fixture("copyleaks", "login"))
    routes["copyleaks"] = respx.route(COPYLEAKS_CHECK).respond(
        200, json=_bodies("copyleaks" in ai_for)["copyleaks"]
    )
    return routes


def _checker(**changes: Any) -> Checker:
    return Checker(Settings(env=ENV, max_retries=0).with_changes(**changes))


LONG = "This sentence is written to exceed every documented provider minimum length. " * 6
ALL = set(URLS) | {"pangram", "copyleaks"}


@respx.mock
def test_all_agree_ai() -> None:
    _mock_all(ALL)
    result = _checker().check(LONG)
    assert result.verdict is Verdict.AI
    assert result.aggregate.providers_used == 7
    assert result.aggregate.agreement == 1.0
    assert result.timing.wall_clock_ms < result.timing.provider_latency_sum_ms + 1000


@respx.mock
def test_several_disagree_is_visible() -> None:
    _mock_all({"sapling", "gptzero", "winston"})
    result = _checker().check(LONG)
    assert result.verdict is Verdict.NO_VERDICT
    assert result.aggregate.diagnostic.value == "conflicted"
    # 3 AI votes (Winston halved: text below its recommended 600 chars) vs 4 human votes,
    # each with unknown confidence (factor 0.75): (3 - 1.875) / 4.875
    assert result.aggregate.agreement == pytest.approx((3 - 1.875) / 4.875)
    assert any("disagree" in w for w in result.warnings)


@respx.mock
def test_one_provider_down_and_one_rate_limited() -> None:
    _mock_all(set(), failing={"hive": 503, "gptzero": 429})
    result = _checker().check(LONG)
    assert result.verdict is Verdict.HUMAN
    categories = {e.provider_id: e.category for e in result.errors}
    assert categories == {
        "hive": ErrorCategory.SERVICE_UNAVAILABLE,
        "gptzero": ErrorCategory.RATE_LIMITED,
    }


@respx.mock
def test_all_providers_fail() -> None:
    _mock_all(set(), failing=dict.fromkeys(URLS, 500))
    respx.post(f"{PANGRAM}/task").respond(401)
    respx.post(copyleaks.LOGIN_URL).respond(401)
    result = _checker().check(LONG)
    assert result.verdict is Verdict.NO_VERDICT
    assert len(result.errors) == 7
    assert result.aggregate.diagnostic.value == "no_evidence"


@respx.mock
def test_short_text_is_handled_per_provider() -> None:
    _mock_all(set())
    result = _checker().check("Too short to judge.")
    by_id = {p.provider_id: p for p in result.providers}
    assert by_id["copyleaks"].error is not None
    assert by_id["copyleaks"].error.category is ErrorCategory.INPUT_TOO_SHORT
    assert by_id["winston"].error is not None
    assert "BELOW_RECOMMENDED_MINIMUM" in by_id["sapling"].warning_codes
    assert by_id["sapling"].weight_factors["applicability"] == 0.5


@respx.mock
def test_huge_text_exact_prefixes_and_coverage() -> None:
    routes = _mock_all(set())
    text = ("Ünïcödé words 👩‍💻 and more. " * 9000)[:250_000]
    result = _checker().check(text)
    by_id = {p.provider_id: p for p in result.providers}
    for pid, limit in {
        "gptzero": 50_000,
        "copyleaks": 100_000,
        "winston": 150_000,
        "sapling": 200_000,
    }.items():
        assert by_id[pid].truncated, pid
        assert by_id[pid].submitted_characters == limit
        assert by_id[pid].input_coverage == pytest.approx(limit / len(text))
    sent = json.loads(routes["gptzero"].calls.last.request.content)["document"]
    assert sent == text[:50_000]
    assert not by_id["originality"].truncated
    assert result.verdict is Verdict.HUMAN


@respx.mock
def test_unicode_confusables_reach_every_provider_unchanged() -> None:
    routes = _mock_all(set())
    text = LONG + " Cyrillic а/Latin a, zero\u200bwidth, NBSP , RTL \u202e, CRLF\r\n  trailing  "
    _checker().check(text)
    assert json.loads(routes["sapling"].calls.last.request.content)["text"] == text
    assert json.loads(routes["winston"].calls.last.request.content)["text"] == text
    assert json.loads(routes["originality"].calls.last.request.content)["content"] == text
    assert json.loads(routes["copyleaks"].calls.last.request.content)["text"] == text
    form = parse_qs(routes["hive"].calls.last.request.content.decode(), keep_blank_values=True)
    assert form["text_data"] == [text]


@respx.mock
def test_non_english_is_not_filtered() -> None:
    routes = _mock_all(set())
    text = "这是一段中文文本，用于测试多语言支持。" * 20 + " Ein deutscher Satz. Un texte français."
    result = _checker().check(text)
    assert all(r.call_count == 1 for pid, r in routes.items() if pid in URLS)
    assert result.verdict is Verdict.HUMAN


@respx.mock
def test_schema_variation_is_isolated() -> None:
    _mock_all(set())
    respx.post(URLS["sapling"]).respond(200, json={"score": "not-a-number"})
    respx.post(URLS["originality"]).respond(200, json=["unexpected", "list"])
    result = _checker().check(LONG)
    categories = {e.provider_id: e.category for e in result.errors}
    assert categories == {
        "sapling": ErrorCategory.SCHEMA_CHANGED,
        "originality": ErrorCategory.SCHEMA_CHANGED,
    }
    assert result.verdict is Verdict.HUMAN


@respx.mock
def test_timeouts_are_bounded() -> None:
    _mock_all(set())
    respx.post(URLS["hive"]).mock(side_effect=httpx.ReadTimeout("slow"))
    result = _checker().check(LONG)
    assert {e.provider_id: e.category for e in result.errors} == {"hive": ErrorCategory.TIMEOUT}


@respx.mock
def test_json_is_stable_and_versioned() -> None:
    _mock_all(set())
    first = _checker().check(LONG).to_dict()
    second = _checker().check(LONG).to_dict()
    assert list(first) == list(second)
    assert first["schema_version"] == "1.0"
    assert [p["provider_id"] for p in first["providers"]] == [
        p["provider_id"] for p in second["providers"]
    ]
    assert list(first["providers"][0]) == list(second["providers"][0])
    assert LONG not in json.dumps(first)
