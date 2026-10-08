# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""Credential bootstrap + budgeted live-E2E runner, with the real services mocked."""

import io
import json
import stat
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
import respx

from tests.contract.conftest import fixture
from turingtongue import Settings
from turingtongue.cli import main as cli
from turingtongue.credentials import CredentialState, CredentialStore, bootstrap, cleanup
from turingtongue.credentials.bootstrap import activate
from turingtongue.credentials.store import default_state_dir
from turingtongue.e2e import RequestBudget, run_e2e
from turingtongue.providers import copyleaks
from turingtongue.providers.sapling import URL as SAPLING_URL

pytestmark = pytest.mark.integration
ENV = {"COPYLEAKS_EMAIL": "ci@example.test", "COPYLEAKS_API_KEY": "cl-account-secret"}
TOKEN = "ACLNSKNSDAACCAJANCOIUiausoo_saidjaskldjoa"
CHECK = respx.patterns.M(
    url__regex=r"https://api\.copyleaks\.com/v2/writer-detector/[0-9a-f]{32}/check"
)


@pytest.fixture(autouse=True)
def _clean_cache() -> Iterator[None]:
    copyleaks.clear_token_cache()
    yield
    copyleaks.clear_token_cache()


@pytest.fixture
def store(tmp_path: Path) -> CredentialStore:
    return CredentialStore(tmp_path / "state")


def settings(env: dict[str, str] | None = None) -> Settings:
    return Settings(env=ENV if env is None else env, max_retries=0)


async def test_missing_account_secret_is_manual(store: CredentialStore) -> None:
    report = await bootstrap("copyleaks", settings({}), store=store)
    assert report.state is CredentialState.MISSING
    assert not report.ready
    assert report.message.startswith("manual-credential-required")
    assert "https://api.copyleaks.com/signup" in report.message
    assert [m.value for m in report.mechanisms] == ["environment", "machine_token", "sandbox"]


@respx.mock
async def test_machine_token_is_issued_stored_privately_and_reused(store: CredentialStore) -> None:
    login = respx.post(copyleaks.LOGIN_URL).respond(200, json=fixture("copyleaks", "login"))
    first = await bootstrap("copyleaks", settings(), store=store)
    assert (first.state, first.requests_used, first.reused) == (CredentialState.VALID, 1, False)
    assert first.expires_at is not None
    path = store.directory / "copyleaks.json"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(store.directory.stat().st_mode) == 0o700
    assert "cl-account-secret" not in path.read_text()
    serialized = json.dumps(first.as_dict())
    assert TOKEN not in serialized
    assert "cl-account-secret" not in serialized
    copyleaks.clear_token_cache()
    second = await bootstrap("copyleaks", settings(), store=store)
    assert (second.state, second.reused, second.requests_used) == (CredentialState.VALID, True, 0)
    assert login.call_count == 1


@respx.mock
async def test_expired_or_foreign_token_is_replaced(store: CredentialStore) -> None:
    store.save(
        "copyleaks",
        token="old",
        expires=datetime.now(UTC) - timedelta(hours=1),
        account=ENV["COPYLEAKS_EMAIL"],
    )
    login = respx.post(copyleaks.LOGIN_URL).respond(200, json=fixture("copyleaks", "login"))
    assert (await bootstrap("copyleaks", settings(), store=store)).state is CredentialState.VALID
    store.save(
        "copyleaks", token="other", expires=datetime.now(UTC) + timedelta(days=1), account="else@x"
    )
    assert (await bootstrap("copyleaks", settings(), store=store)).requests_used == 1
    assert login.call_count == 2


@respx.mock
async def test_login_rejected_is_reported_without_secrets(store: CredentialStore) -> None:
    respx.post(copyleaks.LOGIN_URL).respond(401, json={"message": "invalid key cl-account-secret"})
    report = await bootstrap("copyleaks", settings(), store=store)
    assert report.state is CredentialState.MISSING
    assert "AUTHENTICATION_FAILED" in report.message
    assert "cl-account-secret" not in report.message


async def test_environment_mechanism_for_other_providers(store: CredentialStore) -> None:
    report = await bootstrap("sapling", settings({"SAPLING_API_KEY": "k"}), store=store)
    assert report.state is CredentialState.VALID
    assert "verified by the first live E2E request" in report.message


def test_activate_and_cleanup(store: CredentialStore) -> None:
    store.save(
        "copyleaks",
        token=TOKEN,
        expires=datetime.now(UTC) + timedelta(days=1),
        account=ENV["COPYLEAKS_EMAIL"],
    )
    activate("copyleaks", settings(), store)
    assert copyleaks.cached_token(ENV["COPYLEAKS_EMAIL"]) is not None
    activate("sapling", settings(), store)
    removed = cleanup("copyleaks", settings(), store=store)
    assert "deleted locally" in removed.message
    assert copyleaks.cached_token(ENV["COPYLEAKS_EMAIL"]) is None
    assert "nothing to clean up" in cleanup("copyleaks", settings(), store=store).message
    assert "CI secret store" in cleanup("sapling", settings(), store=store).message


def test_default_state_dir(tmp_path: Path) -> None:
    assert default_state_dir({"TURINGTONGUE_E2E_STATE_DIR": str(tmp_path)}) == tmp_path
    assert default_state_dir({"XDG_RUNTIME_DIR": "/run/user/7"}) == Path(
        "/run/user/7/turingtongue-e2e"
    )
    assert "turingtongue-e2e-" in str(default_state_dir({}))
    assert CredentialStore(tmp_path / "nope").load("x") is None


@respx.mock
async def test_e2e_sandbox_run_uses_one_request_after_init(store: CredentialStore) -> None:
    respx.post(copyleaks.LOGIN_URL).respond(200, json=fixture("copyleaks", "login"))
    check = respx.route(CHECK).respond(200, json=fixture("copyleaks", "check"))
    await bootstrap("copyleaks", settings(), store=store)
    copyleaks.clear_token_cache()
    report = await run_e2e("copyleaks", settings(), store=store)
    assert report.ok
    assert report.sandbox
    assert (report.requests_used, report.max_requests) == (1, 2)
    assert report.checks == {
        "authenticated": True,
        "request_accepted": True,
        "response_parsed": True,
        "within_budget": True,
    }
    assert json.loads(check.calls.last.request.content)["sandbox"] is True
    assert "sandbox" in report.message
    assert TOKEN not in json.dumps(report.as_dict())


@respx.mock
async def test_budget_stops_the_request_that_would_exceed_it(store: CredentialStore) -> None:
    login = respx.post(copyleaks.LOGIN_URL).respond(200, json=fixture("copyleaks", "login"))
    check = respx.route(CHECK).respond(200, json=fixture("copyleaks", "check"))
    report = await run_e2e("copyleaks", settings(), store=store, max_requests=1)
    assert login.call_count == 1
    assert check.call_count == 0
    assert not report.ok
    assert "budget of 1 exhausted" in report.message


@respx.mock
async def test_live_classification_without_sandbox(store: CredentialStore) -> None:
    respx.post(SAPLING_URL).respond(200, json={"score": 0.1})
    report = await run_e2e(
        "sapling", settings({"SAPLING_API_KEY": "k"}), store=store, sandbox=False
    )
    assert report.ok
    assert not report.sandbox
    assert "live classification" in report.message


@respx.mock
async def test_auth_failure_is_a_failed_e2e(store: CredentialStore) -> None:
    respx.post(SAPLING_URL).respond(401, json={"msg": "bad key"})
    report = await run_e2e("sapling", settings({"SAPLING_API_KEY": "k"}), store=store)
    assert not report.ok
    assert report.checks["authenticated"] is False


async def test_never_downgrades_to_mock(store: CredentialStore) -> None:
    missing = await run_e2e("copyleaks", settings({}), store=store)
    assert not missing.ok
    assert missing.message.startswith("manual-credential-required")
    assert missing.requests_used == 0
    mock = await run_e2e("mock", settings({}), store=store)
    assert not mock.ok
    assert not mock.live


async def test_request_budget_closes_inner_transport() -> None:
    inner = httpx.MockTransport(lambda request: httpx.Response(200))
    budget = RequestBudget(inner, 1)
    async with httpx.AsyncClient(transport=budget) as client:
        assert (await client.get("https://x.test")).status_code == 200


class Streams:
    def __init__(self) -> None:
        self.out, self.err = io.StringIO(), io.StringIO()

    def run(self, *argv: str) -> int:
        return cli.run(list(argv), stdin=io.StringIO(), stdout=self.out, stderr=self.err)


@respx.mock
def test_cli_init_e2e_cleanup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("TURINGTONGUE_E2E_STATE_DIR", str(tmp_path / "state"))
    for key, value in ENV.items():
        monkeypatch.setenv(key, value)
    respx.post(copyleaks.LOGIN_URL).respond(200, json=fixture("copyleaks", "login"))
    respx.route(CHECK).respond(200, json=fixture("copyleaks", "check"))
    s = Streams()
    assert s.run("init", "copyleaks", "--mode", "e2e") == 0
    assert "init copyleaks: valid" in s.out.getvalue()
    s = Streams()
    assert s.run("e2e", "copyleaks", "--max-requests", "2", "--json") == 0
    assert json.loads(s.out.getvalue())["ok"] is True
    s = Streams()
    assert s.run("cleanup", "copyleaks", "--json") == 0
    assert "deleted locally" in json.loads(s.out.getvalue())["message"]
    assert Streams().run("e2e", "copyleaks", "--max-requests", "0") == cli.EXIT_USAGE


@respx.mock
def test_cli_exit_codes_for_failures(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("TURINGTONGUE_E2E_STATE_DIR", str(tmp_path / "state"))
    s = Streams()
    assert s.run("init", "copyleaks") == cli.EXIT_USAGE
    assert "manual-credential-required" in s.out.getvalue()
    assert Streams().run("e2e", "gptzero") == cli.EXIT_USAGE
    for key, value in ENV.items():
        monkeypatch.setenv(key, value)
    respx.post(copyleaks.LOGIN_URL).respond(500)
    s = Streams()
    assert s.run("init", "copyleaks", "--json") == 1
    assert json.loads(s.out.getvalue())["state"] == "missing"
    monkeypatch.setenv("SAPLING_API_KEY", "k")
    respx.post(SAPLING_URL).respond(403)
    assert Streams().run("e2e", "sapling", "--no-sandbox") == 1
