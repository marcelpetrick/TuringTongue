# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
import hashlib
import json

import pytest

from turingtongue.models import (
    SCHEMA_VERSION,
    Aggregate,
    CheckResult,
    Diagnostic,
    ErrorCategory,
    InputInfo,
    ProviderError,
    ProviderResult,
    ProviderStatus,
    Segment,
    Timing,
    TransportKind,
    Verdict,
)

pytestmark = pytest.mark.unit


def _result() -> CheckResult:
    ok = ProviderResult(
        provider_id="sapling",
        provider_name="Sapling",
        transport=TransportKind.API,
        status=ProviderStatus.OK,
        raw_score=0.9,
        normalized_evidence=0.8,
        segments=[Segment(0, 10, "ai", 0.9, "sentence")],
    )
    failed = ProviderResult(
        provider_id="gptzero",
        provider_name="GPTZero",
        transport=TransportKind.API,
        status=ProviderStatus.FAILED,
        error=ProviderError("gptzero", ErrorCategory.TIMEOUT, "timed out", retryable=True),
    )
    return CheckResult(
        verdict=Verdict.AI,
        aggregate=Aggregate(0.8, 0.8, 0.4, 1.0, 1.0, 1, Diagnostic.STRONGLY_AI),
        input=InputInfo.from_text("Grüße — 👋"),
        providers=[ok, failed],
        timing=Timing("a", "b", 10.0, 0.1, 9.0),
        package_version="1.2.3",
    )


def test_verdict_display() -> None:
    assert Verdict.NO_VERDICT.display == "NO_VERDICT"
    assert Verdict.HUMAN.display == "HUMAN"


def test_input_info_counts_unicode_without_altering() -> None:
    text = "Grüße  \t👋\n"
    info = InputInfo.from_text(text)
    assert info.characters == len(text)
    assert info.words == 2
    assert info.utf8_bytes == len(text.encode())
    assert info.sha256 == hashlib.sha256(text.encode()).hexdigest()


def test_input_info_lone_surrogate_does_not_crash() -> None:
    assert InputInfo.from_text("\ud800").characters == 1


def test_json_is_versioned_and_ordered() -> None:
    data = json.loads(_result().to_json())
    assert next(iter(data)) == "schema_version"
    assert data["schema_version"] == SCHEMA_VERSION
    assert data["verdict"] == "ai"
    assert data["providers"][0]["transport"] == "api"
    assert data["providers"][0]["segments"][0]["kind"] == "sentence"
    assert data["errors"] == [
        {
            "provider_id": "gptzero",
            "category": "TIMEOUT",
            "message": "timed out",
            "http_status": None,
            "retryable": True,
            "attempt_count": 0,
            "latency_ms": None,
        }
    ]
    assert "👋" not in _result().to_json()  # the text itself is never serialized


def test_ok_property() -> None:
    result = _result()
    assert result.providers[0].ok
    assert not result.providers[1].ok
    assert len(result.errors) == 1


def test_to_json_compact() -> None:
    assert "\n" not in _result().to_json(indent=None)
