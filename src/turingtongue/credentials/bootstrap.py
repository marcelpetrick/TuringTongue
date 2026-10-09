# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""``init`` / ``cleanup`` for live E2E: pick the least-friction *permitted* mechanism.

Per provider the registry lists supported mechanisms (``bootstrap`` field). Today:

* every provider: ``environment`` — credentials injected via env / CI secret;
* Copyleaks additionally: ``machine_token`` (official login API turns the long-lived
  email + API key into a 48 h bearer token, reused across the run and discarded at
  cleanup) and ``sandbox`` (official free mode: real service, mock classifications).
* ZeroGPT additionally: ``account_key`` (an explicit two-call existing-account flow
  logs in and issues one documented non-expiring API key; account signup stays manual).

No provider offers machine-driven *account* registration, so a missing account secret
yields ``missing`` with actionable instructions (``manual-credential-required``) — the
bootstrap never scripts website signups, CAPTCHAs or email verification.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import httpx

from turingtongue.config import Settings
from turingtongue.credentials.base import BootstrapReport, CredentialState, Mechanism
from turingtongue.credentials.store import (
    CredentialStore,
    default_state_dir,
    save_dotenv_credential,
)
from turingtongue.errors import ConfigurationError, ProviderFailure
from turingtongue.providers import copyleaks, zerogpt
from turingtongue.redaction import redact
from turingtongue.registry import ProviderSpec, Registry
from turingtongue.transport import HttpCaller, RetryPolicy

COPYLEAKS_LOGIN_REQUEST_BUDGET = 1
ZEROGPT_ACQUISITION_REQUEST_BUDGET = 2


def _mechanisms(spec: ProviderSpec) -> list[Mechanism]:
    return [Mechanism(m) for m in spec.bootstrap]


def _store(settings: Settings, store: CredentialStore | None) -> CredentialStore:
    return store or CredentialStore(default_state_dir(settings.env))


def manual_message(spec: ProviderSpec, missing: list[str]) -> str:
    """The explicit, actionable ``manual-credential-required`` message."""
    help_text = spec.credential_help or f"see {spec.docs_url}"
    return (
        f"manual-credential-required: set {', '.join(missing)} (environment or CI secret). "
        f"{spec.name} offers no machine-driven account registration. {help_text}"
    )


async def bootstrap(
    provider_id: str,
    settings: Settings,
    *,
    acquire_credential: bool = False,
    registry: Registry | None = None,
    store: CredentialStore | None = None,
    client: httpx.AsyncClient | None = None,
    dotenv_path: Path = Path(".env"),
) -> BootstrapReport:
    """Make ``provider_id`` ready for a live E2E check, or explain exactly why not."""
    spec = (registry or Registry.builtin()).get(provider_id)
    mechanisms = _mechanisms(spec)
    report = BootstrapReport(spec.id, CredentialState.MISSING, mechanisms)
    if Mechanism.ACCOUNT_KEY in mechanisms and spec.id == "zerogpt":
        return await _zerogpt_key(
            settings,
            _store(settings, store),
            spec,
            report,
            client,
            dotenv_path=dotenv_path,
            acquire_credential=acquire_credential,
        )
    missing = spec.missing_credentials(settings.env)
    if missing:
        report.message = manual_message(spec, missing)
        return report
    if Mechanism.MACHINE_TOKEN in mechanisms and spec.id == "copyleaks":
        return await _copyleaks_token(
            settings,
            _store(settings, store),
            report,
            client,
            acquire_credential=acquire_credential,
        )
    report.state = CredentialState.VALID
    report.message = (
        "credential present in the environment; it is verified by the first live E2E request"
    )
    return report


async def _zerogpt_key(
    settings: Settings,
    store: CredentialStore,
    spec: ProviderSpec,
    report: BootstrapReport,
    client: httpx.AsyncClient | None,
    *,
    dotenv_path: Path,
    acquire_credential: bool,
) -> BootstrapReport:
    email = settings.credential("ZEROGPT_EMAIL") or ""
    password = settings.credential("ZEROGPT_PASSWORD") or ""
    api_key = settings.credential("ZEROGPT_API_KEY")
    if api_key and settings.credential("ZEROGPT_BEARER_TOKEN"):
        report.state = CredentialState.VALID
        report.message = "API key and login JWT are present in the environment"
        return report
    reused = _reuse_zerogpt_token(store, email, api_key, report)
    if reused is not None:
        return reused
    if not acquire_credential:
        if api_key:
            report.message = (
                "credential-acquisition-required: the existing ZeroGPT API key was not changed; "
                "rerun init with --acquire-credential to obtain a run-scoped login JWT"
            )
        else:
            report.message = (
                "manual-credential-required: set ZEROGPT_API_KEY, or set ZEROGPT_EMAIL and "
                "ZEROGPT_PASSWORD then rerun with --acquire-credential. ZeroGPT offers no "
                f"machine-driven account registration. {spec.credential_help}"
            )
        return report
    missing_account = [
        name
        for name, value in (("ZEROGPT_EMAIL", email), ("ZEROGPT_PASSWORD", password))
        if not value
    ]
    if missing_account:
        report.message = manual_message(spec, missing_account)
        return report
    report.state = CredentialState.PROVISIONING
    own_client = client is None
    http = client or httpx.AsyncClient(timeout=settings.timeout_s)
    caller = HttpCaller(
        http,
        provider_name="ZeroGPT",
        policy=RetryPolicy(max_retries=0),
        max_response_bytes=settings.max_response_bytes,
        secrets=[email, password, api_key],
    )
    try:
        token, expires = await zerogpt.login(caller, email, password, settings.timeout_s)
        report.requests_used = 1
        if api_key is None:
            key_caller = HttpCaller(
                http,
                provider_name="ZeroGPT",
                policy=RetryPolicy(max_retries=0),
                max_response_bytes=settings.max_response_bytes,
                secrets=[email, password, token],
            )
            api_key = await zerogpt.generate_api_key(key_caller, token, settings.timeout_s)
            report.requests_used = ZEROGPT_ACQUISITION_REQUEST_BUDGET
            save_dotenv_credential(dotenv_path, "ZEROGPT_API_KEY", api_key)
        store.save("zerogpt", token=token, expires=expires, account=email)
    except ProviderFailure as failure:
        report.state = CredentialState.MISSING
        report.requests_used += failure.attempt_count
        detail = (
            f"HTTP {failure.http_status}"
            if failure.http_status is not None
            else redact(failure.message, [email, password, api_key])
        )
        report.message = f"credential acquisition failed: {failure.category.value} — {detail}"
        return report
    except (ConfigurationError, OSError) as failure:
        report.state = CredentialState.MISSING
        report.message = f"credential persistence failed: {type(failure).__name__}"
        return report
    finally:
        if own_client:
            await http.aclose()
    zerogpt.seed_token(email, token, expires)
    report.state, report.expires_at = CredentialState.VALID, expires
    if report.requests_used == 1:
        report.message = (
            "existing non-expiring ZeroGPT API key retained; run-scoped login JWT obtained"
        )
    else:
        report.message = (
            "non-expiring ZeroGPT API key issued once via the official existing-account API, "
            "saved to owner-only .env; run-scoped login JWT obtained"
        )
    return report


def _reuse_zerogpt_token(
    store: CredentialStore,
    email: str,
    api_key: str | None,
    report: BootstrapReport,
) -> BootstrapReport | None:
    stored = store.load("zerogpt")
    if not stored or stored.get("account") != email:
        return None
    try:
        expires = datetime.fromisoformat(stored["expires"])
        token = stored["token"]
    except KeyError, TypeError, ValueError:
        report.state = CredentialState.EXPIRED
        return None
    zerogpt.seed_token(email, token, expires)
    if not api_key or zerogpt.cached_token(email) is None:
        report.state = CredentialState.EXPIRED
        return None
    report.state, report.expires_at, report.reused = CredentialState.VALID, expires, True
    report.message = "reused the run-scoped ZeroGPT login JWT and existing non-expiring API key"
    return report


async def _copyleaks_token(
    settings: Settings,
    store: CredentialStore,
    report: BootstrapReport,
    client: httpx.AsyncClient | None,
    *,
    acquire_credential: bool,
) -> BootstrapReport:
    email = settings.credential("COPYLEAKS_EMAIL") or ""
    key = settings.credential("COPYLEAKS_API_KEY") or ""
    stored = store.load("copyleaks")
    if stored and stored.get("account") == email:
        expires = datetime.fromisoformat(stored["expires"])
        copyleaks.seed_token(email, stored["token"], expires)
        if copyleaks.cached_token(email) is not None:
            report.state, report.expires_at, report.reused = CredentialState.VALID, expires, True
            report.message = "reused the machine-issued Copyleaks token of this run"
            return report
        report.state = CredentialState.EXPIRED
    if not acquire_credential:
        report.state = CredentialState.MISSING
        report.message = (
            "credential-acquisition-required: no valid run-scoped Copyleaks token; "
            "rerun init with --acquire-credential to call the official login API"
        )
        return report
    report.state = CredentialState.PROVISIONING
    own_client = client is None
    http = client or httpx.AsyncClient(timeout=settings.timeout_s)
    caller = HttpCaller(
        http,
        provider_name="Copyleaks",
        # Credential acquisition has its own one-request budget.  In particular, do
        # not inherit the normal provider retry policy: a retry is another login
        # request and would make both the documented budget and requests_used false.
        policy=RetryPolicy(max_retries=COPYLEAKS_LOGIN_REQUEST_BUDGET - 1),
        max_response_bytes=settings.max_response_bytes,
        secrets=[email, key],
    )
    try:
        token, expires = await copyleaks.login(caller, email, key, settings.timeout_s)
    except ProviderFailure as failure:
        report.state = CredentialState.MISSING
        report.requests_used = failure.attempt_count
        report.message = (
            f"login failed: {failure.category.value} — {redact(failure.message, [email, key])}"
        )
        return report
    finally:
        if own_client:
            await http.aclose()
    store.save("copyleaks", token=token, expires=expires, account=email)
    report.state, report.expires_at = CredentialState.VALID, expires
    report.requests_used = 1
    report.message = "machine-issued Copyleaks token obtained via the official login API"
    return report


def activate(provider_id: str, settings: Settings, store: CredentialStore | None = None) -> None:
    """Load run-scoped tokens into the adapters before an E2E check (no network)."""
    if provider_id not in {"copyleaks", "zerogpt"}:
        return
    stored = _store(settings, store).load(provider_id)
    prefix = provider_id.upper()
    email = settings.credential(f"{prefix}_EMAIL")
    if stored and email and stored.get("account") == email:
        try:
            expires = datetime.fromisoformat(stored["expires"])
            token = stored["token"]
        except KeyError, TypeError, ValueError:
            return
        if provider_id == "copyleaks":
            copyleaks.seed_token(email, token, expires)
        else:
            zerogpt.seed_token(email, token, expires)


def cleanup(
    provider_id: str,
    settings: Settings,
    *,
    registry: Registry | None = None,
    store: CredentialStore | None = None,
) -> BootstrapReport:
    """Discard run-scoped credentials. Copyleaks documents no revoke endpoint."""
    spec = (registry or Registry.builtin()).get(provider_id)
    removed = _store(settings, store).delete(spec.id)
    if spec.id == "copyleaks":
        copyleaks.clear_token_cache()
    elif spec.id == "zerogpt":
        zerogpt.clear_token_cache()
    message = (
        "run-scoped token deleted locally; it expires on the provider side by itself "
        "(no revoke endpoint documented)"
        if removed
        else "nothing to clean up (no run-scoped credential stored)"
    )
    if spec.id == "zerogpt":
        message = (
            "run-scoped login JWT deleted locally; the non-expiring ZeroGPT API key remains "
            "in the owner-controlled environment/.env and was not remotely revoked"
            if removed
            else "nothing to clean up (no run-scoped login JWT stored); the non-expiring "
            "ZeroGPT API key was not changed or remotely revoked"
        )
    elif spec.id != "copyleaks" and not removed:
        message += "; environment credentials are owned by the CI secret store"
    report = BootstrapReport(spec.id, CredentialState.MISSING, _mechanisms(spec), message)
    report.expires_at = datetime.now(UTC) if removed else None
    return report
