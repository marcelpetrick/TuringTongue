# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""``init`` / ``cleanup`` for live E2E: pick the least-friction *permitted* mechanism.

Per provider the registry lists supported mechanisms (``bootstrap`` field). Today:

* every provider: ``environment`` — credentials injected via env / CI secret;
* Copyleaks additionally: ``machine_token`` (official login API turns the long-lived
  email + API key into a 48 h bearer token, reused across the run and discarded at
  cleanup) and ``sandbox`` (official free mode: real service, mock classifications).

No provider offers machine-driven *account* registration, so a missing account secret
yields ``missing`` with actionable instructions (``manual-credential-required``) — the
bootstrap never scripts website signups, CAPTCHAs or email verification.
"""

from __future__ import annotations

from datetime import UTC, datetime

import httpx

from turingtongue.config import Settings
from turingtongue.credentials.base import BootstrapReport, CredentialState, Mechanism
from turingtongue.credentials.store import CredentialStore, default_state_dir
from turingtongue.errors import ProviderFailure
from turingtongue.providers import copyleaks
from turingtongue.redaction import redact
from turingtongue.registry import ProviderSpec, Registry
from turingtongue.transport import HttpCaller, RetryPolicy

COPYLEAKS_LOGIN_REQUEST_BUDGET = 1


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
) -> BootstrapReport:
    """Make ``provider_id`` ready for a live E2E check, or explain exactly why not."""
    spec = (registry or Registry.builtin()).get(provider_id)
    mechanisms = _mechanisms(spec)
    report = BootstrapReport(spec.id, CredentialState.MISSING, mechanisms)
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
    if provider_id != "copyleaks":
        return
    stored = _store(settings, store).load("copyleaks")
    email = settings.credential("COPYLEAKS_EMAIL")
    if stored and email and stored.get("account") == email:
        copyleaks.seed_token(email, stored["token"], datetime.fromisoformat(stored["expires"]))


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
    message = (
        "run-scoped token deleted locally; it expires on the provider side by itself "
        "(no revoke endpoint documented)"
        if removed
        else "nothing to clean up (no run-scoped credential stored)"
    )
    if spec.id != "copyleaks" and not removed:
        message += "; environment credentials are owned by the CI secret store"
    report = BootstrapReport(spec.id, CredentialState.MISSING, _mechanisms(spec), message)
    report.expires_at = datetime.now(UTC) if removed else None
    return report
