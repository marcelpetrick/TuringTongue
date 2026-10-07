# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
import json

import httpx
import pytest
import respx

from tests.contract.conftest import Runner, fixture
from turingtongue.models import ErrorCategory
from turingtongue.providers.pangram import BASE_URL

pytestmark = pytest.mark.contract
ENV = {"PANGRAM_API_KEY": "pg-secret"}
TEXT = "AI-assisted passage. Human passage."
TASK = {"task_id": "123e4567-e89b-12d3-a456-426614174000"}
POLL = f"{BASE_URL}/task/{TASK['task_id']}"


@respx.mock
def test_submit_poll_and_parse(run_provider: Runner) -> None:
    create = respx.post(f"{BASE_URL}/task").respond(200, json=TASK)
    poll = respx.get(POLL).mock(
        side_effect=[
            httpx.Response(200, json={"task_id": TASK["task_id"], "stage": "STAGE_PREPROCESSING"}),
            httpx.Response(200, json=fixture("pangram", "success")),
        ]
    )
    p = run_provider("pangram", TEXT, ENV, poll_interval_s=0).providers[0]
    assert p.ok
    assert p.normalized_evidence == pytest.approx(0.5 * 0.6 - 0.4)
    assert p.raw_label == "Mixed"
    assert p.model == "default"
    assert p.model_version == "4.0"
    assert p.normalized_confidence == pytest.approx((1.0 * 2 + 2 / 3 * 2) / 4)
    assert [(s.start, s.end, s.label) for s in p.segments] == [
        (0, 21, "AI-Assisted"),
        (21, 35, "Human Written"),
    ]
    assert {"POLLS=2", "HUMANIZER_DETECTED"} <= set(p.warning_codes)
    assert p.attempt_count == 3
    assert poll.call_count == 2
    sent = json.loads(create.calls.last.request.content)
    assert sent == {"text": TEXT, "model": "default", "public_dashboard_link": False}
    assert create.calls.last.request.headers["x-api-key"] == "pg-secret"
    assert "text" not in p.raw_response


@respx.mock
def test_offsets_dropped_when_provider_normalized_text(run_provider: Runner) -> None:
    respx.post(f"{BASE_URL}/task").respond(200, json=TASK)
    respx.get(POLL).respond(200, json=fixture("pangram", "success"))
    p = run_provider("pangram", TEXT + "  ", ENV, model="pangram-4").providers[0]
    assert p.segments[0].start is None
    assert "WINDOW_OFFSETS_REFER_TO_PROVIDER_NORMALIZED_TEXT" in p.warning_codes
    assert p.model == "pangram-4"


@respx.mock
def test_failed_task(run_provider: Runner) -> None:
    respx.post(f"{BASE_URL}/task").respond(200, json=TASK)
    respx.get(POLL).respond(200, json=fixture("pangram", "failed"))
    error = run_provider("pangram", TEXT, ENV).errors[0]
    assert error.category is ErrorCategory.UNSUPPORTED_INPUT
    assert "preprocessing" in error.message


@respx.mock
def test_failed_task_other_reason(run_provider: Runner) -> None:
    respx.post(f"{BASE_URL}/task").respond(200, json=TASK)
    respx.get(POLL).respond(200, json={"stage": "STAGE_FAILED"})
    assert run_provider("pangram", TEXT, ENV).errors[0].category is ErrorCategory.PROVIDER_ERROR


@respx.mock
def test_no_windows_unknown_confidence(run_provider: Runner) -> None:
    respx.post(f"{BASE_URL}/task").respond(200, json=TASK)
    body = {
        "stage": "STAGE_SUCCESS",
        "fraction_ai": 1.0,
        "fraction_human": 0.0,
        "windows": [
            {"label": "AI-Generated", "confidence": "Unknown", "start_index": 0, "end_index": 1}
        ],
    }
    respx.get(POLL).respond(200, json=body)
    p = run_provider("pangram", TEXT, ENV).providers[0]
    assert p.normalized_confidence is None
    assert p.normalized_evidence == 1.0
    assert p.segments[0].score is None


@pytest.mark.parametrize(
    ("status", "category"),
    [(402, ErrorCategory.QUOTA_EXHAUSTED), (422, ErrorCategory.UNSUPPORTED_INPUT)],
)
@respx.mock
def test_submit_errors(run_provider: Runner, status: int, category: ErrorCategory) -> None:
    respx.post(f"{BASE_URL}/task").respond(status, text="nope")
    assert run_provider("pangram", TEXT, ENV).errors[0].category is category
