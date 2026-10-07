# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
import json

import pytest
import respx

from scripts import provider_health
from turingtongue.providers.sapling import URL

pytestmark = pytest.mark.unit


def test_no_credentials_sends_nothing(capsys: pytest.CaptureFixture[str]) -> None:
    assert provider_health.main([]) == 0
    assert "nothing was sent" in capsys.readouterr().out


@respx.mock
def test_configured_provider_is_reported(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("SAPLING_API_KEY", "k")
    monkeypatch.setenv("GPTZERO_API_KEY", "k")
    respx.post(URL).respond(200, json={"score": 0.1, "version": "v1"})
    respx.post("https://api.gptzero.me/v2/predict/text").respond(503)
    monkeypatch.setenv("TURINGTONGUE_CONFIG", "")
    assert provider_health.main([]) == 0
    out = capsys.readouterr().out
    assert "| sapling | ok | — | -0.80 |" in out
    assert "| gptzero | failed | SERVICE_UNAVAILABLE | — |" in out
    assert provider_health.main(["--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert {row["provider"] for row in data} == {"sapling", "gptzero"}
