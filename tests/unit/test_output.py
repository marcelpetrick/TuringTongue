# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
import io

import pytest
from rich.console import Console

from turingtongue import Checker, Registry, Settings
from turingtongue.cli import output
from turingtongue.models import CheckResult, CostInfo, RateLimitInfo, Segment

pytestmark = pytest.mark.unit


def _render(result: CheckResult) -> str:
    buffer = io.StringIO()
    output.render_verbose(result, Console(file=buffer, width=200, highlight=False))
    return buffer.getvalue()


@pytest.mark.parametrize(
    ("agreement", "word"), [(None, "n/a"), (1.0, "high"), (0.5, "moderate"), (0.1, "low")]
)
def test_agreement_word(agreement: float | None, word: str) -> None:
    assert output._agreement_word(agreement) == word


def test_details_cover_cost_rate_limit_and_segments() -> None:
    result = Checker(Settings(env={})).check("Some text.", providers=["mock"])
    provider = result.providers[0]
    provider.cost = CostInfo(credits_used=3, billing_unit="words")
    provider.rate_limit = RateLimitInfo(remaining=5)
    provider.segments = [Segment(0, 4, "ai", 0.9, "sentence")]
    provider.truncated = True
    text = _render(result)
    assert "cost/credits credits_used=3, billing_unit=words" in text
    assert "rate limit remaining=5" in text
    assert "1 sentence-level results" in text
    assert "100% (cut)" in text
    assert "not sent to any third-party service" in text


def test_sent_note_names_contacted_services_only() -> None:
    result = Checker(Settings(env={})).check("Some text.", providers=["mock", "all"])
    assert output._sent_note(result) == output.NOT_SENT_NOTE
    result.providers[1].error = None
    assert result.providers[1].provider_name in output._sent_note(result)


def test_empty_mapping_and_slots() -> None:
    assert output._mapping({"a": None}) == "none reported"
    assert output._slots(object()) == {}


def test_render_providers_credential_states() -> None:
    buffer = io.StringIO()
    env = {"SAPLING_API_KEY": "k"}
    output.render_providers(Registry.builtin(), env, Console(file=buffer, width=250))
    text = buffer.getvalue()
    assert "not needed" in text
    assert "| set" in text or " set " in text
    assert "200,000 characters" in text
    assert "missing: GPTZERO_API_KEY" in text
