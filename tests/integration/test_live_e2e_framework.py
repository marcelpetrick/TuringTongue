# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""Credential bootstrap + budgeted live-E2E runner, with the real services mocked."""

import base64
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
from turingtongue.providers import copyleaks, zerogpt
from turingtongue.providers.sapling import URL as SAPLING_URL

pytestmark = pytest.mark.integration
ENV = {"COPYLEAKS_EMAIL": "ci@example.test", "COPYLEAKS_API_KEY": "cl-account-secret"}
ZEROGPT_ACCOUNT = {
    "ZEROGPT_EMAIL": "owner@example.test",
    "ZEROGPT_PASSWORD": "correct-horse-battery-staple",
}
ZEROGPT_KEY = "zg-issued-non-expiring-key"


def _jwt() -> str:
    payload = base64.urlsafe_b64encode(json.dumps({"exp": 4_102_444_800}).encode()).decode()
    return f"header.{payload.rstrip('=')}.signature"


ZEROGPT_JWT = _jwt()
TOKEN = "ACLNSKNSDAACCAJANCOIUiausoo_saidjaskldjoa"
CHECK = respx.patterns.M(
    url__regex=r"https://api\.copyleaks\.com/v2/writer-detector/[0-9a-f]{32}/check"
)


@pytest.fixture(autouse=True)
def _clean_cache() -> Iterator[None]:
    copyleaks.clear_token_cache()
    zerogpt.clear_token_cache()
    yield
    copyleaks.clear_token_cache()
    zerogpt.clear_token_cache()


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
    first = await bootstrap("copyleaks", settings(), store=store, acquire_credential=True)
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
    assert (
        await bootstrap("copyleaks", settings(), store=store, acquire_credential=True)
    ).state is CredentialState.VALID
    store.save(
        "copyleaks", token="other", expires=datetime.now(UTC) + timedelta(days=1), account="else@x"
    )
    assert (
        await bootstrap("copyleaks", settings(), store=store, acquire_credential=True)
    ).requests_used == 1
    assert login.call_count == 2


@respx.mock
async def test_login_rejected_is_reported_without_secrets(store: CredentialStore) -> None:
    respx.post(copyleaks.LOGIN_URL).respond(401, json={"message": "invalid key cl-account-secret"})
    report = await bootstrap("copyleaks", settings(), store=store, acquire_credential=True)
    assert report.state is CredentialState.MISSING
    assert report.requests_used == 1
    assert "AUTHENTICATION_FAILED" in report.message
    assert "cl-account-secret" not in report.message


@respx.mock
async def test_login_request_budget_disables_retries_and_reports_attempts_honestly(
    store: CredentialStore,
) -> None:
    login = respx.post(copyleaks.LOGIN_URL).respond(503)
    retrying_settings = Settings(env=ENV, max_retries=9)

    report = await bootstrap("copyleaks", retrying_settings, store=store, acquire_credential=True)

    assert report.state is CredentialState.MISSING
    assert report.requests_used == 1
    assert login.call_count == 1


async def test_environment_mechanism_for_other_providers(store: CredentialStore) -> None:
    report = await bootstrap("sapling", settings({"SAPLING_API_KEY": "k"}), store=store)
    assert report.state is CredentialState.VALID
    assert "verified by the first live E2E request" in report.message


@respx.mock
async def test_zerogpt_issues_key_once_and_persists_only_expected_secrets(
    store: CredentialStore, tmp_path: Path
) -> None:
    login = respx.post(zerogpt.LOGIN_URL).respond(
        200, json={"success": True, "data": {"token": ZEROGPT_JWT}}
    )
    generate = respx.get(zerogpt.GENERATE_KEY_URL).respond(
        200, json={"success": True, "data": {"apiKey": ZEROGPT_KEY}}
    )
    dotenv = tmp_path / ".env"

    report = await bootstrap(
        "zerogpt",
        settings(ZEROGPT_ACCOUNT),
        store=store,
        acquire_credential=True,
        dotenv_path=dotenv,
    )

    assert (report.state, report.requests_used, report.reused) == (
        CredentialState.VALID,
        2,
        False,
    )
    assert login.call_count == generate.call_count == 1
    assert stat.S_IMODE(dotenv.stat().st_mode) == 0o600
    assert "ZEROGPT_API_KEY=" in dotenv.read_text()
    assert ZEROGPT_ACCOUNT["ZEROGPT_PASSWORD"] not in dotenv.read_text()
    assert ZEROGPT_JWT not in dotenv.read_text()
    assert ZEROGPT_KEY not in json.dumps(report.as_dict())
    token_state = (store.directory / "zerogpt.json").read_text()
    assert ZEROGPT_KEY not in token_state
    assert ZEROGPT_ACCOUNT["ZEROGPT_PASSWORD"] not in token_state


@respx.mock
async def test_zerogpt_existing_api_key_is_never_reissued(
    store: CredentialStore, tmp_path: Path
) -> None:
    env = {**ZEROGPT_ACCOUNT, "ZEROGPT_API_KEY": "already-owned"}
    login = respx.post(zerogpt.LOGIN_URL).respond(
        200, json={"success": True, "data": {"token": ZEROGPT_JWT}}
    )
    generate = respx.get(zerogpt.GENERATE_KEY_URL).respond(
        200, json={"success": True, "data": {"apiKey": "must-not-be-used"}}
    )

    report = await bootstrap(
        "zerogpt",
        settings(env),
        store=store,
        acquire_credential=True,
        dotenv_path=tmp_path / ".env",
    )

    assert (report.state, report.requests_used) == (CredentialState.VALID, 1)
    assert "retained" in report.message
    assert login.call_count == 1
    assert generate.call_count == 0
    assert not (tmp_path / ".env").exists()


@respx.mock
async def test_zerogpt_acquisition_is_explicit_and_account_is_human_created(
    store: CredentialStore,
) -> None:
    login = respx.post(zerogpt.LOGIN_URL).respond(500)
    report = await bootstrap("zerogpt", settings(ZEROGPT_ACCOUNT), store=store)
    assert report.state is CredentialState.MISSING
    assert report.requests_used == 0
    assert report.message.startswith("manual-credential-required")
    assert login.call_count == 0
    missing = await bootstrap("zerogpt", settings({}), store=store, acquire_credential=True)
    assert "ZEROGPT_EMAIL" in missing.message
    assert "no machine-driven account registration" in missing.message


@respx.mock
async def test_zerogpt_acquisition_has_no_retries_and_fails_closed(
    store: CredentialStore, tmp_path: Path
) -> None:
    login = respx.post(zerogpt.LOGIN_URL).mock(
        side_effect=[
            httpx.Response(503, json={"message": ZEROGPT_ACCOUNT["ZEROGPT_PASSWORD"]}),
            httpx.Response(200, json={"success": True, "data": {"token": ZEROGPT_JWT}}),
        ]
    )
    report = await bootstrap(
        "zerogpt",
        Settings(env=ZEROGPT_ACCOUNT, max_retries=9),
        store=store,
        acquire_credential=True,
        dotenv_path=tmp_path / ".env",
    )
    assert (report.state, report.requests_used, login.call_count) == (
        CredentialState.MISSING,
        1,
        1,
    )
    assert ZEROGPT_ACCOUNT["ZEROGPT_PASSWORD"] not in report.message

    login.reset()
    login.mock(
        return_value=httpx.Response(200, json={"success": True, "data": {"token": "not-a-jwt"}})
    )
    schema = await bootstrap(
        "zerogpt",
        settings(ZEROGPT_ACCOUNT),
        store=store,
        acquire_credential=True,
        dotenv_path=tmp_path / ".env",
    )
    assert schema.state is CredentialState.MISSING
    assert schema.requests_used == 1
    assert "SCHEMA_CHANGED" in schema.message

    login.reset()
    login.mock(
        return_value=httpx.Response(
            200,
            json={"success": True, "data": {"token": "header.%%%%.signature"}},
        )
    )
    malformed = await bootstrap(
        "zerogpt",
        settings(ZEROGPT_ACCOUNT),
        store=store,
        acquire_credential=True,
        dotenv_path=tmp_path / ".env",
    )
    assert malformed.state is CredentialState.MISSING
    assert malformed.requests_used == 1
    assert "SCHEMA_CHANGED" in malformed.message


@respx.mock
async def test_zerogpt_key_envelope_is_defensive_and_budget_is_two(
    store: CredentialStore, tmp_path: Path
) -> None:
    respx.post(zerogpt.LOGIN_URL).respond(
        200, json={"success": True, "data": {"token": ZEROGPT_JWT}}
    )
    generate = respx.get(zerogpt.GENERATE_KEY_URL).respond(
        200,
        json={"success": True, "data": {"apiKey": "one", "key": "different"}},
    )
    report = await bootstrap(
        "zerogpt",
        settings(ZEROGPT_ACCOUNT),
        store=store,
        acquire_credential=True,
        dotenv_path=tmp_path / ".env",
    )
    assert (report.state, report.requests_used, generate.call_count) == (
        CredentialState.MISSING,
        2,
        1,
    )
    assert "unambiguous key field" in report.message
    assert not (tmp_path / ".env").exists()

    generate.reset()
    generate.mock(
        return_value=httpx.Response(
            200,
            json={"success": True, "data": "key generation succeeded"},
        )
    )
    invalid = await bootstrap(
        "zerogpt",
        settings(ZEROGPT_ACCOUNT),
        store=store,
        acquire_credential=True,
        dotenv_path=tmp_path / ".env",
    )
    assert invalid.state is CredentialState.MISSING
    assert invalid.requests_used == 2
    assert "invalid key" in invalid.message


@respx.mock
async def test_zerogpt_acquired_credentials_activate_for_e2e(
    store: CredentialStore, tmp_path: Path
) -> None:
    respx.post(zerogpt.LOGIN_URL).respond(
        200, json={"success": True, "data": {"token": ZEROGPT_JWT}}
    )
    respx.get(zerogpt.GENERATE_KEY_URL).respond(200, json={"success": True, "data": ZEROGPT_KEY})
    dotenv = tmp_path / ".env"
    await bootstrap(
        "zerogpt",
        settings(ZEROGPT_ACCOUNT),
        store=store,
        acquire_credential=True,
        dotenv_path=dotenv,
    )
    zerogpt.clear_token_cache()
    detect = respx.post(zerogpt.URL).respond(200, json=fixture("zerogpt", "ok-synthetic"))
    loaded = Settings.load(env=ZEROGPT_ACCOUNT, dotenv_path=dotenv).with_changes(max_retries=0)

    report = await run_e2e("zerogpt", loaded, store=store, max_requests=1)

    assert report.ok
    assert report.requests_used == 1
    assert detect.calls.last.request.headers["ApiKey"] == ZEROGPT_KEY
    assert detect.calls.last.request.headers["Authorization"] == f"Bearer {ZEROGPT_JWT}"
    cleaned = cleanup("zerogpt", loaded, store=store)
    assert "not remotely revoked" in cleaned.message
    assert ZEROGPT_KEY in dotenv.read_text()


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
    await bootstrap("copyleaks", settings(), store=store, acquire_credential=True)
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
async def test_e2e_without_explicit_acquisition_never_logs_in(store: CredentialStore) -> None:
    login = respx.post(copyleaks.LOGIN_URL).respond(200, json=fixture("copyleaks", "login"))
    check = respx.route(CHECK).respond(200, json=fixture("copyleaks", "check"))
    report = await run_e2e("copyleaks", settings(), store=store, max_requests=1)
    assert login.call_count == 0
    assert check.call_count == 0
    assert not report.ok
    assert report.requests_used == 0
    assert report.message.startswith("credential-acquisition-required")


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
    assert s.run("init", "copyleaks", "--mode", "e2e") == cli.EXIT_USAGE
    assert "credential-acquisition-required" in s.out.getvalue()
    assert not respx.calls
    s = Streams()
    assert s.run("init", "copyleaks", "--mode", "e2e", "--acquire-credential") == 0
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
    assert s.run("init", "copyleaks", "--json", "--acquire-credential") == 1
    assert json.loads(s.out.getvalue())["state"] == "missing"
    monkeypatch.setenv("SAPLING_API_KEY", "k")
    respx.post(SAPLING_URL).respond(403)
    assert Streams().run("e2e", "sapling", "--no-sandbox") == 1


@respx.mock
def test_cli_zerogpt_explicit_acquisition_and_e2e(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TURINGTONGUE_E2E_STATE_DIR", str(tmp_path / "state"))
    for key, value in ZEROGPT_ACCOUNT.items():
        monkeypatch.setenv(key, value)
    login = respx.post(zerogpt.LOGIN_URL).respond(
        200, json={"success": True, "data": {"token": ZEROGPT_JWT}}
    )
    respx.get(zerogpt.GENERATE_KEY_URL).respond(
        200, json={"success": True, "data": {"api_key": ZEROGPT_KEY}}
    )
    detect = respx.post(zerogpt.URL).respond(200, json=fixture("zerogpt", "ok-synthetic"))

    without_flag = Streams()
    assert without_flag.run("init", "zerogpt", "--mode", "e2e") == cli.EXIT_USAGE
    assert login.call_count == 0
    acquired = Streams()
    assert acquired.run("init", "zerogpt", "--mode", "e2e", "--acquire-credential", "--json") == 0
    payload = json.loads(acquired.out.getvalue())
    assert payload["requests_used"] == 2
    assert ZEROGPT_KEY not in acquired.out.getvalue()
    assert ZEROGPT_KEY in (tmp_path / ".env").read_text()

    monkeypatch.setenv("ZEROGPT_API_KEY", ZEROGPT_KEY)
    assert Streams().run("e2e", "zerogpt", "--max-requests", "1") == 0
    assert detect.call_count == 1
    cleaned = Streams()
    assert cleaned.run("cleanup", "zerogpt", "--json") == 0
    assert "not remotely revoked" in json.loads(cleaned.out.getvalue())["message"]
