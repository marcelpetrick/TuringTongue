# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""Contract tests for the Hive adapter."""

import pytest
import respx

from tests.contract.conftest import Runner, fixture
from turingtongue.models import ErrorCategory
from turingtongue.providers import hive

pytestmark = pytest.mark.contract
LONG = "This paragraph is long enough for every provider minimum. " * 12


# -- Hive ---------------------------------------------------------------------------
@respx.mock
def test_hive_list_envelope(run_provider: Runner) -> None:
    route = respx.post(hive.URL).respond(200, json=fixture("hive", "list_status"))
    p = run_provider("hive", LONG, {"HIVE_API_KEY": "h-secret"}).providers[0]
    assert p.raw_score == pytest.approx(0.9994929075028791)
    assert [(s.start, s.end) for s in p.segments] == [(0, 2048), (2048, 2586)]
    assert p.model == "AI_CLASSIFICATION"
    request = route.calls.last.request
    assert request.headers["authorization"] == "token h-secret"
    assert request.content.decode().startswith("text_data=")


@respx.mock
def test_hive_object_envelope(run_provider: Runner) -> None:
    respx.post(hive.URL).respond(200, json=fixture("hive", "object_status"))
    p = run_provider("hive", LONG, {"HIVE_API_KEY": "k"}).providers[0]
    assert p.raw_label == "human"
    assert p.model_version == "3"
    assert p.segments[0].score == pytest.approx(0.02)


@respx.mock
def test_hive_task_error_and_missing_score(run_provider: Runner) -> None:
    respx.post(hive.URL).respond(
        200, json={"status": [{"status": {"code": "3200", "message": "invalid input"}}]}
    )
    assert run_provider("hive", LONG, {"HIVE_API_KEY": "k"}).errors[0].category is (
        ErrorCategory.PROVIDER_ERROR
    )
    respx.post(hive.URL).respond(
        200, json={"status": {"status": {"code": 0}, "response": {"aggregate_score": ["x"]}}}
    )
    assert run_provider("hive", LONG, {"HIVE_API_KEY": "k"}).errors[0].category is (
        ErrorCategory.SCHEMA_CHANGED
    )


@pytest.mark.parametrize(
    ("status", "category"),
    [
        (405, ErrorCategory.QUOTA_EXHAUSTED),
        (403, ErrorCategory.AUTHENTICATION_FAILED),
        (400, ErrorCategory.PROVIDER_ERROR),
    ],
)
@respx.mock
def test_hive_http_errors(run_provider: Runner, status: int, category: ErrorCategory) -> None:
    respx.post(hive.URL).respond(status, json={"return_code": status, "message": "x"})
    assert run_provider("hive", LONG, {"HIVE_API_KEY": "k"}).errors[0].category is category
