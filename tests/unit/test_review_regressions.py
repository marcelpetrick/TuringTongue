# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""Regression tests for review findings (T110)."""

import asyncio
import io
import json
from pathlib import Path

import pytest
import respx
from rich.console import Console

from tests.contract.conftest import fixture
from turingtongue import Checker, Settings
from turingtongue.cli import main as cli
from turingtongue.cli.output import render_verbose
from turingtongue.config import ProviderOverrides
from turingtongue.providers import pangram, sapling

pytestmark = pytest.mark.unit
SECRET_TEXT = "Here is a sentence. " * 20


@respx.mock
def test_sapling_raw_capture_has_no_input_text() -> None:
    respx.post(sapling.URL).respond(200, json=fixture("sapling", "ok"))
    result = Checker(Settings(env={"SAPLING_API_KEY": "k"})).check(
        SECRET_TEXT, providers=["sapling"], verbose=True
    )
    raw = json.dumps(result.providers[0].raw_response)
    assert "Here is a sentence" not in raw
    assert '"score"' in raw


@respx.mock
def test_pangram_raw_capture_has_no_window_text(monkeypatch: pytest.MonkeyPatch) -> None:
    waits: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        waits.append(seconds)

    monkeypatch.setattr("turingtongue.providers.pangram.asyncio.sleep", fake_sleep)
    respx.post(f"{pangram.BASE_URL}/task").respond(200, json={"task_id": "t"})
    respx.get(f"{pangram.BASE_URL}/task/t").mock(
        side_effect=[
            respx.MockResponse(200, json={"stage": "STAGE_QUEUED"}),
            respx.MockResponse(200, json=fixture("pangram", "success")),
        ]
    )
    result = Checker(Settings(env={"PANGRAM_API_KEY": "k"})).check(
        "AI-assisted passage. Human passage.",
        providers=["pangram"],
        verbose=True,
        provider_options={"pangram": {"poll_interval_s": -5}},
    )
    raw = json.dumps(result.providers[0].raw_response)
    assert "passage" not in raw
    assert waits == [pangram.MIN_POLL_INTERVAL_S]


def test_provider_gates_are_per_loop_objects() -> None:
    checker = Checker(Settings(env={}))

    async def grab() -> asyncio.Semaphore:
        return checker._provider_gate("mock")

    first = asyncio.run(grab())
    second = asyncio.run(grab())
    assert first is not second
    assert len(checker._provider_gates) <= 1


def test_hostile_markup_in_provider_strings_does_not_crash() -> None:
    result = Checker(Settings(env={})).check("Some text.", providers=["mock"])
    result.providers[0].model_version = "v2 [/bold] [red]"
    out = io.StringIO()
    render_verbose(result, Console(file=out, width=200))
    assert "v2 [/bold] [red]" in out.getvalue()


def test_cli_timeout_beats_config_provider_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = tmp_path / "c.toml"
    config.write_text("[providers.sapling]\ntimeout_s = 99\nweight = 2\n")
    monkeypatch.setenv("HOME", str(tmp_path))
    args = cli.build_parser().parse_args(["--config", str(config), "check", "--timeout", "7"])
    settings = cli.make_settings(args)
    assert settings.timeout_s == 7
    assert settings.overrides("sapling").timeout_s is None
    assert settings.overrides("sapling").weight == 2


def test_weight_overrides_are_visible_in_weights_version() -> None:
    settings = Settings(env={}, providers={"mock": ProviderOverrides(weight=2.5)})
    result = Checker(settings).check("Some text.", providers=["mock"])
    assert result.aggregate.weights_version == "v0-equal-weights+overrides(mock=2.5)"
    plain = Checker(Settings(env={})).check("Some text.", providers=["mock"])
    assert plain.aggregate.weights_version == "v0-equal-weights"
