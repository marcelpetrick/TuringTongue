# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""Run one tiny, budget-limited live check against a real provider.

The request budget is enforced at the HTTP transport: request number ``max+1`` is never
sent. A live E2E run never falls back to the mock provider; missing credentials fail.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx

from turingtongue._version import __version__
from turingtongue.client import Checker
from turingtongue.config import Settings
from turingtongue.credentials.bootstrap import activate, manual_message
from turingtongue.credentials.store import CredentialStore
from turingtongue.errors import ProviderFailure
from turingtongue.models import ErrorCategory, ProviderStatus, TransportKind
from turingtongue.providers import copyleaks, zerogpt
from turingtongue.registry import Registry

SAMPLE = (
    "It was on a dreary night of November that I beheld the accomplishment of my toils. "
    "With an anxiety that almost amounted to agony, I collected the instruments of life "
    "around me, that I might infuse a spark of being into the lifeless thing that lay at "
    "my feet. It was already one in the morning; the rain pattered dismally against the "
    "panes, and my candle was nearly burnt out, when, by the glimmer of the half-"
    "extinguished light, I saw the dull yellow eye of the creature open."
)
"""Mary Shelley, *Frankenstein* (1818), ch. 5 — public domain, > 255 characters."""


class RequestBudget(httpx.AsyncBaseTransport):
    """Transport wrapper that refuses to send more than ``limit`` requests."""

    def __init__(self, inner: httpx.AsyncBaseTransport, limit: int) -> None:
        self.inner = inner
        self.limit = limit
        self.used = 0

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        """Count and forward, or refuse once the budget is spent."""
        if self.used >= self.limit:
            raise ProviderFailure(
                ErrorCategory.QUOTA_EXHAUSTED,
                f"E2E request budget of {self.limit} exhausted; request not sent",
                retryable=False,
            )
        self.used += 1
        return await self.inner.handle_async_request(request)

    async def aclose(self) -> None:
        """Close the wrapped transport."""
        await self.inner.aclose()


@dataclass(slots=True)
class E2EReport:
    """Result of one live E2E check. Never contains secrets or the sample text."""

    provider_id: str
    ok: bool
    live: bool
    sandbox: bool
    requests_used: int
    max_requests: int
    checks: dict[str, bool] = field(default_factory=dict)
    message: str = ""
    latency_ms: float | None = None
    model_version: str | None = None
    package_version: str = __version__

    def as_dict(self) -> dict[str, Any]:
        """Plain data for JSON output."""
        return {
            "provider_id": self.provider_id,
            "ok": self.ok,
            "live": self.live,
            "sandbox": self.sandbox,
            "requests_used": self.requests_used,
            "max_requests": self.max_requests,
            "checks": self.checks,
            "message": self.message,
            "latency_ms": self.latency_ms,
            "model_version": self.model_version,
            "package_version": self.package_version,
        }


async def run_e2e(
    provider_id: str,
    settings: Settings,
    *,
    max_requests: int = 2,
    timeout_s: float = 30.0,
    retries: int = 1,
    sandbox: bool = True,
    registry: Registry | None = None,
    store: CredentialStore | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> E2EReport:
    """One budgeted live request (or two) through the full orchestrator path."""
    reg = registry or Registry.builtin()
    spec = reg.get(provider_id)
    uses_sandbox = sandbox and "sandbox" in spec.bootstrap
    report = E2EReport(
        spec.id,
        ok=False,
        live=True,
        sandbox=uses_sandbox,
        requests_used=0,
        max_requests=max_requests,
    )
    if spec.transport is TransportKind.MOCK:
        report.live = False
        report.message = "the mock provider is not a live service; refusing a live E2E run"
        return report
    missing = spec.missing_credentials(settings.env)
    if missing:
        report.message = manual_message(spec, missing)
        return report
    activate(spec.id, settings, store)
    if spec.id == "copyleaks":
        email = settings.credential("COPYLEAKS_EMAIL") or ""
        if copyleaks.cached_token(email) is None:
            report.message = (
                "credential-acquisition-required: run 'turingtongue init copyleaks "
                "--mode e2e --acquire-credential' before the live check"
            )
            return report
    elif spec.id == "zerogpt":
        email = settings.credential("ZEROGPT_EMAIL") or ""
        if (
            settings.credential("ZEROGPT_BEARER_TOKEN") is None
            and zerogpt.cached_token(email) is None
        ):
            report.message = (
                "credential-acquisition-required: run 'turingtongue init zerogpt "
                "--mode e2e --acquire-credential' before the live check"
            )
            return report
    budget = RequestBudget(transport or httpx.AsyncHTTPTransport(), max_requests)

    def client_factory(s: Settings) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=budget, timeout=s.timeout_s, follow_redirects=False)

    run_settings = settings.with_changes(
        timeout_s=timeout_s, deadline_s=timeout_s * 2, max_retries=retries
    )
    checker = Checker(run_settings, registry=reg, client_factory=client_factory)
    options = {spec.id: {"sandbox": True}} if uses_sandbox else {}
    result = await checker.acheck(SAMPLE, providers=[spec.id], provider_options=options)
    provider = result.providers[0]
    report.requests_used = budget.used
    report.latency_ms = provider.latency_ms
    report.model_version = provider.model_version
    report.checks = {
        "authenticated": provider.error is None
        or provider.error.category
        not in {ErrorCategory.AUTHENTICATION_FAILED, ErrorCategory.AUTHORIZATION_FAILED},
        "request_accepted": provider.status is ProviderStatus.OK,
        "response_parsed": provider.status is ProviderStatus.OK and provider.raw_label is not None,
        "within_budget": budget.used <= max_requests,
    }
    report.ok = all(report.checks.values())
    if provider.error is not None:
        report.message = f"{provider.error.category.value}: {provider.error.message}"
    else:
        mode = "sandbox (mock classification)" if uses_sandbox else "live classification"
        report.message = f"{spec.name} answered via {mode}; raw label {provider.raw_label!r}"
    return report
