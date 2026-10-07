# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""Orchestrator + adapters + ensemble together, HTTP mocked with respx."""

import asyncio
import json

import httpx
import pytest
import respx

from tests.helpers import ECHO_URL, registry
from turingtongue import Checker, ConfigurationError, Settings, Verdict
from turingtongue.client import check
from turingtongue.config import ProviderOverrides
from turingtongue.models import ErrorCategory, ProviderStatus

pytestmark = pytest.mark.integration

TEXT = "The quick brown fox jumps over the lazy dog again and again today."
ENV = {"ECHO_KEY": "sk-echo-secret", "ECHO2_EMAIL": "me@example.test"}


def checker(env: dict[str, str] | None = None, **settings: object) -> Checker:
    base = Settings(env=ENV if env is None else env, max_retries=0)
    return Checker(base.with_changes(**settings), registry=registry())


@respx.mock
async def test_default_selection_runs_configured_providers() -> None:
    route = respx.post(ECHO_URL).respond(200, json={"p_ai": 0.1})
    result = await checker().acheck(TEXT)
    assert result.verdict is Verdict.HUMAN
    assert [p.provider_id for p in result.providers] == ["echo", "echo2"]
    assert result.selection["mode"] == "default"
    assert result.selection["skipped"] == {"web": "disabled by default/config"}
    sent = json.loads(route.calls[0].request.content)
    assert sent["text"] in TEXT
    echo = result.providers[0]
    assert echo.truncated
    assert echo.submitted_characters == len(sent["text"])
    assert TEXT.startswith(sent["text"])
    assert json.loads(route.calls[1].request.content)["text"] == TEXT
    assert echo.phase_timings_ms.keys() == {"prepare", "network", "parse_and_overhead"}
    assert any("only the first" in w for w in result.warnings)
    assert result.timing.wall_clock_ms > 0
    assert result.package_version


@respx.mock
async def test_partial_failure_still_returns_verdict() -> None:
    respx.post(ECHO_URL).mock(
        side_effect=[httpx.Response(200, json={"p_ai": 0.95}), httpx.Response(503)]
    )
    result = await checker().acheck(TEXT)
    assert result.verdict is Verdict.AI
    statuses = sorted(p.status for p in result.providers)
    assert statuses == [ProviderStatus.FAILED, ProviderStatus.OK]
    assert len(result.errors) == 1
    assert result.errors[0].category is ErrorCategory.SERVICE_UNAVAILABLE


@respx.mock
async def test_all_fail_no_verdict_and_no_secret_leak() -> None:
    respx.post(ECHO_URL).respond(401, json={"error": "invalid key sk-echo-secret"})
    result = await checker().acheck(TEXT)
    assert result.verdict is Verdict.NO_VERDICT
    assert {e.category for e in result.errors} == {ErrorCategory.AUTHENTICATION_FAILED}
    assert "sk-echo-secret" not in result.to_json()


@respx.mock
async def test_schema_change_is_reported() -> None:
    respx.post(ECHO_URL).respond(200, json={"unexpected": 1})
    result = await checker().acheck(TEXT, providers=["echo2"])
    assert result.errors[0].category is ErrorCategory.SCHEMA_CHANGED


async def test_missing_credentials_default_vs_explicit() -> None:
    default = await checker(env={}).acheck(TEXT)
    assert default.providers == []
    assert default.verdict is Verdict.NO_VERDICT
    assert "not configured" in default.selection["skipped"]["echo"]
    assert any("no provider could run" in w for w in default.warnings)

    explicit = await checker(env={}).acheck(TEXT, providers="echo,echo2")
    assert [e.category for e in explicit.errors] == [ErrorCategory.NOT_CONFIGURED] * 2
    assert "ECHO_KEY" in explicit.errors[0].message
    assert explicit.verdict is Verdict.NO_VERDICT


@respx.mock
async def test_all_includes_unconfigured_but_not_mock() -> None:
    respx.post(ECHO_URL).respond(200, json={"p_ai": 0.9})
    result = await checker(env={"ECHO_KEY": "k"}).acheck(TEXT, providers="all", transport="api")
    ids = {p.provider_id: p.status for p in result.providers}
    assert ids == {"echo": ProviderStatus.OK, "echo2": ProviderStatus.FAILED}
    assert "web" in result.selection["skipped"]


async def test_mock_transport_and_explicit_mock() -> None:
    result = await checker(env={"TURINGTONGUE_MOCK_RESULT": "ai"}).acheck(TEXT, transport="mock")
    assert result.verdict is Verdict.AI
    assert result.providers[0].raw_response is None
    verbose = await checker(env={}).acheck(TEXT, providers=["mock"], verbose=True)
    assert verbose.verdict is Verdict.HUMAN
    assert verbose.providers[0].raw_response == {"mock_result": "human"}


@pytest.mark.parametrize(
    ("answer", "category"), [("error", "SERVICE_UNAVAILABLE"), ("x", "UNSUPPORTED_INPUT")]
)
async def test_mock_failures(answer: str, category: str) -> None:
    result = await checker(env={}).acheck(
        TEXT, providers=["mock"], provider_options={"mock": {"result": answer}}
    )
    assert result.errors[0].category.value == category


async def test_mixed_mock_is_borderline() -> None:
    result = await checker(env={"TURINGTONGUE_MOCK_RESULT": "mixed"}).acheck(TEXT, providers="mock")
    assert result.verdict is Verdict.NO_VERDICT


async def test_provider_timeout() -> None:
    result = await checker(providers={"web": ProviderOverrides(timeout_s=0.05)}).acheck(
        TEXT, providers=["web"]
    )
    assert result.errors[0].category is ErrorCategory.TIMEOUT
    assert "provider deadline" in result.errors[0].message


async def test_overall_deadline() -> None:
    result = await checker(deadline_s=0.05).acheck(TEXT, providers=["web"])
    assert result.errors[0].category is ErrorCategory.TIMEOUT
    assert "overall run deadline" in result.errors[0].message


async def test_crashing_adapter_is_contained() -> None:
    reg = registry(
        '\n[providers.crash]\nname = "Crash"\ntransport = "api"\n'
        'adapter = "tests.helpers:CrashProvider"\nrequires_credentials = false\n'
    )
    result = await Checker(Settings(env={}), registry=reg).acheck(TEXT, providers=["crash"])
    assert result.errors[0].category is ErrorCategory.UNKNOWN_ERROR
    assert "RuntimeError" in result.errors[0].message


async def test_transport_filter_skips_explicit() -> None:
    result = await checker().acheck(TEXT, providers=["web"], transport="api")
    assert result.providers == []
    assert "transport browser" in result.selection["skipped"]["web"]


async def test_config_disable_and_weight() -> None:
    overrides = {"echo": ProviderOverrides(enabled=False), "mock": ProviderOverrides(weight=3.0)}
    c = checker(providers=overrides)
    assert [s.id for s in c.select().run] == ["echo2"]
    result = await c.acheck(TEXT, providers=["mock"])
    assert result.providers[0].weight_factors["reliability"] == 3.0


async def test_invalid_input() -> None:
    with pytest.raises(ConfigurationError, match="empty"):
        await checker().acheck("   \n")
    with pytest.raises(ConfigurationError, match="must be a str"):
        await checker().acheck(b"bytes")  # type: ignore[arg-type]
    with pytest.raises(ConfigurationError, match="unknown transport"):
        await checker().acheck(TEXT, transport="carrier-pigeon")
    with pytest.raises(ConfigurationError, match="unknown provider"):
        await checker().acheck(TEXT, providers=["nope"])


async def test_concurrent_checks_share_per_provider_gate() -> None:
    c = checker(env={})
    results = await asyncio.gather(*(c.acheck(TEXT, providers="mock") for _ in range(3)))
    assert all(r.verdict is Verdict.HUMAN for r in results)


def test_sync_facade(monkeypatch: pytest.MonkeyPatch) -> None:
    result = checker(env={}).check(TEXT, providers=["mock"])
    assert result.verdict is Verdict.HUMAN
    monkeypatch.setenv("TURINGTONGUE_MOCK_RESULT", "ai")
    assert check(TEXT, providers=["mock"]).verdict is Verdict.AI


async def test_sync_facade_refuses_inside_loop() -> None:
    with pytest.raises(ConfigurationError, match="event loop"):
        checker().check(TEXT)


@respx.mock
async def test_text_is_sent_byte_for_byte() -> None:
    weird = "  Leading spaces,\u200b zero-width, Cyrillic а, tabs\t\tand\r\nCRLF  "
    route = respx.post(ECHO_URL).respond(200, json={"p_ai": 0.5})
    await checker().acheck(weird, providers=["echo2"])
    assert json.loads(route.calls[0].request.content)["text"] == weird
