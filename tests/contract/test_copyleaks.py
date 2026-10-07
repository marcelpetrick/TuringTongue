# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
import json
from collections.abc import Iterator

import httpx
import pytest
import respx

from tests.contract.conftest import Runner, fixture
from turingtongue import Verdict
from turingtongue.models import ErrorCategory
from turingtongue.providers import copyleaks
from turingtongue.providers.copyleaks import LOGIN_URL

pytestmark = pytest.mark.contract
ENV = {"COPYLEAKS_EMAIL": "me@example.test", "COPYLEAKS_API_KEY": "cl-secret-key"}
TEXT = "This is a sufficiently long text for Copyleaks. " * 8
CHECK = respx.patterns.M(
    url__regex=r"https://api\.copyleaks\.com/v2/writer-detector/[0-9a-f]{32}/check"
)


@pytest.fixture(autouse=True)
def _fresh_cache() -> Iterator[None]:
    copyleaks.clear_token_cache()
    yield
    copyleaks.clear_token_cache()


@respx.mock
def test_login_check_and_token_reuse(run_provider: Runner) -> None:
    login = respx.post(LOGIN_URL).respond(200, json=fixture("copyleaks", "login"))
    check = respx.route(CHECK).respond(200, json=fixture("copyleaks", "check"))
    result = run_provider("copyleaks", TEXT, ENV, sensitivity=2)
    p = result.providers[0]
    assert result.verdict is Verdict.AI
    assert p.normalized_evidence == 1.0
    assert p.model_version == "v9.0"
    assert (p.segments[0].start, p.segments[0].end, p.segments[0].label) == (0, 554, "ai")
    assert p.cost is not None
    assert p.cost.credits_used == 1
    assert json.loads(login.calls.last.request.content) == {
        "email": "me@example.test",
        "key": "cl-secret-key",
    }
    request = check.calls.last.request
    assert request.headers["Authorization"] == "Bearer ACLNSKNSDAACCAJANCOIUiausoo_saidjaskldjoa"
    assert json.loads(request.content) == {"text": TEXT, "sandbox": False, "sensitivity": 2}
    assert "ACLNSKNSDAACCAJ" not in json.dumps(result.to_dict()["errors"])
    run_provider("copyleaks", TEXT, ENV)
    assert login.call_count == 1
    assert check.call_count == 2


@respx.mock
def test_sandbox_results_are_excluded(run_provider: Runner) -> None:
    respx.post(LOGIN_URL).respond(200, json=fixture("copyleaks", "login"))
    check = respx.route(CHECK).respond(200, json=fixture("copyleaks", "check"))
    result = run_provider("copyleaks", TEXT, {**ENV, "COPYLEAKS_SANDBOX": "1"})
    p = result.providers[0]
    assert result.verdict is Verdict.NO_VERDICT
    assert p.normalized_evidence is None
    assert p.raw_label == "ai"
    assert "SANDBOX_MOCK_RESULT" in p.warning_codes
    assert p.exclusion_reason == copyleaks.SANDBOX_REASON
    assert json.loads(check.calls.last.request.content)["sandbox"] is True


@respx.mock
def test_expired_token_relogin_once(run_provider: Runner) -> None:
    login = respx.post(LOGIN_URL).respond(200, json={"access_token": "tok-123456789"})
    respx.route(CHECK).mock(
        side_effect=[httpx.Response(401), httpx.Response(200, json=fixture("copyleaks", "check"))]
    )
    p = run_provider("copyleaks", TEXT, ENV).providers[0]
    assert p.ok
    assert login.call_count == 2


@respx.mock
def test_login_rejected(run_provider: Runner) -> None:
    respx.post(LOGIN_URL).respond(401, json={"message": "bad key cl-secret-key"})
    result = run_provider("copyleaks", TEXT, ENV)
    assert result.errors[0].category is ErrorCategory.AUTHENTICATION_FAILED
    assert "cl-secret-key" not in result.to_json()


@respx.mock
def test_other_check_error_propagates(run_provider: Runner) -> None:
    respx.post(LOGIN_URL).respond(200, json=fixture("copyleaks", "login"))
    respx.route(CHECK).respond(400, json={"error": "bad"})
    assert run_provider("copyleaks", TEXT, ENV).errors[0].category is ErrorCategory.PROVIDER_ERROR


def test_too_short_is_skipped_without_network(run_provider: Runner) -> None:
    result = run_provider("copyleaks", "short", ENV)
    assert result.errors[0].category is ErrorCategory.INPUT_TOO_SHORT


@respx.mock
def test_actual_credits_and_neutral_summary(run_provider: Runner) -> None:
    respx.post(LOGIN_URL).respond(200, json={"access_token": "t" * 20, ".expires": "garbage"})
    body = {
        "summary": {"ai": 0.0, "human": 0.0},
        "scannedDocument": {"actualCredits": 2},
        "results": [{"classification": 1, "matches": [{"text": {}}]}],
    }
    respx.route(CHECK).respond(200, json=body)
    p = run_provider("copyleaks", TEXT, ENV, language="en").providers[0]
    assert p.normalized_evidence == 0.0
    assert p.cost is not None
    assert p.cost.credits_used == 2
    assert p.model_version is None
