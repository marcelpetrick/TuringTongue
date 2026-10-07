# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""Public entry point: select providers, run them concurrently, combine the evidence.

Privacy: calling :meth:`Checker.check` sends the text to every selected third-party
service. Their processing and retention policies apply; see ``docs/privacy.md``.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Literal

import httpx

from turingtongue._version import __version__
from turingtongue.config import Settings
from turingtongue.ensemble import DEFAULT_POLICY, EnsemblePolicy, combine
from turingtongue.errors import ConfigurationError, ProviderFailure
from turingtongue.models import (
    CheckResult,
    ErrorCategory,
    InputInfo,
    ProviderResult,
    Timing,
    TransportKind,
)
from turingtongue.providers.base import (
    DetectionOptions,
    Provider,
    failure_result,
    now_iso,
    transport_matches,
)
from turingtongue.registry import ProviderSpec, Registry

logger = logging.getLogger("turingtongue")

Transport = Literal["any", "api", "browser", "mock", "all"]
ProviderSelection = str | Sequence[str] | None
TRANSPORTS: tuple[str, ...] = ("any", "api", "browser", "mock", "all")


@dataclass(slots=True)
class Selection:
    """Which providers will run and why others will not."""

    mode: str
    transport: str
    run: list[ProviderSpec] = field(default_factory=list)
    not_configured: list[ProviderSpec] = field(default_factory=list)
    skipped: dict[str, str] = field(default_factory=dict)

    def describe(self) -> dict[str, object]:
        """Plain data for the result's ``selection`` block."""
        return {
            "mode": self.mode,
            "transport": self.transport,
            "selected": [s.id for s in self.run + self.not_configured],
            "ran": [s.id for s in self.run],
            "skipped": dict(self.skipped),
        }


def _default_client_factory(settings: Settings) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=httpx.Timeout(settings.timeout_s, connect=min(10.0, settings.timeout_s)),
        headers={
            "User-Agent": f"turingtongue/{__version__} (+https://github.com/marcelpetrick/TuringTongue)"
        },
        follow_redirects=False,
        verify=True,
    )


class Checker:
    """Runs a text through several AI-text detectors and combines the answers."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        registry: Registry | None = None,
        policy: EnsemblePolicy = DEFAULT_POLICY,
        client_factory: Callable[[Settings], httpx.AsyncClient] = _default_client_factory,
    ) -> None:
        self.settings = settings if settings is not None else Settings.load()
        self.registry = registry if registry is not None else Registry.builtin()
        self.policy = policy
        self._client_factory = client_factory
        self._provider_gates: dict[tuple[int, str], asyncio.Semaphore] = {}

    def _provider_gate(self, provider_id: str) -> asyncio.Semaphore:
        """Per-provider concurrency cap, shared by concurrent ``acheck`` calls on one loop."""
        key = (id(asyncio.get_running_loop()), provider_id)
        if key not in self._provider_gates:
            limit = max(1, self.settings.per_provider_concurrency)
            self._provider_gates[key] = asyncio.Semaphore(limit)
        return self._provider_gates[key]

    # -- selection -----------------------------------------------------------------
    def _enabled(self, spec: ProviderSpec) -> bool:
        override = self.settings.overrides(spec.id).enabled
        return spec.enabled_by_default if override is None else override

    def _configured(self, spec: ProviderSpec) -> bool:
        return not spec.missing_credentials(self.settings.env)

    def select(self, providers: ProviderSelection = None, transport: str = "any") -> Selection:
        """Resolve a provider request into the providers that will run.

        * ``None``/``"default"`` — enabled-by-default providers that have credentials;
          the others are listed under ``skipped`` (not an error);
        * ``"all"`` — every real provider; missing credentials become NOT_CONFIGURED results;
        * names — exactly those; missing credentials become NOT_CONFIGURED results.

        The mock provider only runs when named explicitly or with ``transport="mock"``.
        """
        if transport not in TRANSPORTS:
            raise ConfigurationError(
                f"unknown transport '{transport}' (use {', '.join(TRANSPORTS)})"
            )
        if isinstance(providers, str):
            providers = [p for p in providers.split(",") if p.strip()]
        names = [p.strip().lower() for p in providers or []]
        named = [n for n in dict.fromkeys(names) if n not in {"all", "default"}]
        if "all" in names:
            mode = "all"
        elif named:
            mode = "explicit"
        else:
            mode = "default"
        selection = Selection(mode=mode, transport=transport)
        named_specs = [self.registry.get(name) for name in named]
        candidates = named_specs if mode == "explicit" else list(self.registry)
        explicit_ids = {spec.id for spec in named_specs}
        for spec in candidates:
            if not transport_matches(spec.transport, transport):
                selection.skipped[spec.id] = f"transport {spec.transport.value} not selected"
                continue
            if (
                spec.transport is TransportKind.MOCK
                and spec.id not in explicit_ids
                and transport != "mock"
            ):
                continue
            if mode == "default" and not self._enabled(spec) and transport != "mock":
                selection.skipped[spec.id] = "disabled by default/config"
                continue
            if self._configured(spec):
                selection.run.append(spec)
            elif mode == "default":
                missing = ", ".join(spec.missing_credentials(self.settings.env))
                selection.skipped[spec.id] = f"not configured ({missing} not set)"
            else:
                selection.not_configured.append(spec)
        return selection

    # -- running -------------------------------------------------------------------
    async def _run_one(
        self,
        provider: Provider,
        text: str,
        options: DetectionOptions,
        gate: asyncio.Semaphore,
    ) -> ProviderResult:
        spec = provider.spec
        started = time.perf_counter()
        checked_at = now_iso()
        async with gate, self._provider_gate(spec.id):
            try:
                async with asyncio.timeout(options.timeout_s):
                    return await provider.detect(text, options=options)
            except TimeoutError:
                failure = ProviderFailure(
                    ErrorCategory.TIMEOUT,
                    f"{spec.name}: no answer within the provider deadline "
                    f"of {options.timeout_s:g} s",
                )
            except Exception as exc:
                logger.exception("adapter %s crashed", spec.id)
                failure = ProviderFailure(
                    ErrorCategory.UNKNOWN_ERROR,
                    f"{spec.name}: adapter error ({type(exc).__name__})",
                )
        return failure_result(
            spec,
            failure,
            text=text,
            latency_ms=(time.perf_counter() - started) * 1000,
            checked_at=checked_at,
        )

    async def acheck(
        self,
        text: str,
        *,
        providers: ProviderSelection = None,
        transport: str = "any",
        verbose: bool = False,
        provider_options: Mapping[str, Mapping[str, object]] | None = None,
    ) -> CheckResult:
        """Async check. ``verbose=True`` additionally keeps raw provider responses."""
        if not isinstance(text, str):
            raise ConfigurationError("text must be a str")
        if not text.strip():
            raise ConfigurationError("text is empty")
        started_at = now_iso()
        started = time.perf_counter()
        selection = self.select(providers, transport)
        results: list[ProviderResult] = [
            failure_result(
                spec,
                ProviderFailure(
                    ErrorCategory.NOT_CONFIGURED,
                    f"{spec.name}: environment variable(s) "
                    f"{', '.join(spec.missing_credentials(self.settings.env))} not set",
                    retryable=False,
                    attempt_count=0,
                ),
                text=text,
            )
            for spec in selection.not_configured
        ]
        warnings: list[str] = []
        if selection.run:
            results.extend(
                await self._run_all(selection.run, text, verbose, provider_options or {})
            )
        elif not selection.not_configured:
            warnings.append(
                "no provider could run: configure API keys (see `turingtongue providers`) "
                "or select providers explicitly"
            )
        order = {spec.id: i for i, spec in enumerate(selection.run + selection.not_configured)}
        results.sort(key=lambda r: order.get(r.provider_id, len(order)))
        ensemble_started = time.perf_counter()
        reliability = {
            spec.id: weight
            for spec in self.registry
            if (weight := self.settings.overrides(spec.id).weight) is not None
        }
        verdict, aggregate = combine(results, reliability=reliability, policy=self.policy)
        ensemble_ms = (time.perf_counter() - ensemble_started) * 1000
        warnings.extend(_warnings(results, aggregate.agreement))
        wall_ms = (time.perf_counter() - started) * 1000
        return CheckResult(
            verdict=verdict,
            aggregate=aggregate,
            input=InputInfo.from_text(text),
            providers=results,
            timing=Timing(
                started_at=started_at,
                finished_at=now_iso(),
                wall_clock_ms=wall_ms,
                ensemble_ms=ensemble_ms,
                provider_latency_sum_ms=sum(r.latency_ms or 0.0 for r in results),
            ),
            selection=selection.describe(),
            warnings=warnings,
            package_version=__version__,
        )

    async def _run_all(
        self,
        specs: Sequence[ProviderSpec],
        text: str,
        verbose: bool,
        provider_options: Mapping[str, Mapping[str, object]],
    ) -> list[ProviderResult]:
        gate = asyncio.Semaphore(max(1, self.settings.max_concurrency))
        async with self._client_factory(self.settings) as client:
            tasks: dict[asyncio.Task[ProviderResult], ProviderSpec] = {}
            for spec in specs:
                overrides = self.settings.overrides(spec.id)
                options = DetectionOptions(
                    timeout_s=overrides.timeout_s or self.settings.timeout_s,
                    capture_raw=verbose or self.settings.capture_raw,
                    provider_options={**overrides.options, **provider_options.get(spec.id, {})},
                )
                provider = spec.load_adapter()(spec, self.settings, client)
                logger.debug("starting provider %s (%s)", spec.id, spec.transport.value)
                task = asyncio.create_task(self._run_one(provider, text, options, gate))
                tasks[task] = spec
            done, pending = await asyncio.wait(tasks, timeout=self.settings.deadline_s)
            results = [task.result() for task in done]
            for task in pending:
                task.cancel()
                spec = tasks[task]
                results.append(
                    failure_result(
                        spec,
                        ProviderFailure(
                            ErrorCategory.TIMEOUT,
                            f"{spec.name}: cancelled at the overall run deadline "
                            f"of {self.settings.deadline_s:g} s",
                        ),
                        text=text,
                    )
                )
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)
        return results

    def check(
        self,
        text: str,
        *,
        providers: ProviderSelection = None,
        transport: str = "any",
        verbose: bool = False,
        provider_options: Mapping[str, Mapping[str, object]] | None = None,
    ) -> CheckResult:
        """Synchronous façade over :meth:`acheck` for scripts (not inside an event loop)."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(
                self.acheck(
                    text,
                    providers=providers,
                    transport=transport,
                    verbose=verbose,
                    provider_options=provider_options,
                )
            )
        raise ConfigurationError("check() cannot run inside an event loop; use 'await acheck()'")


def _warnings(results: Sequence[ProviderResult], agreement: float | None) -> list[str]:
    notes: list[str] = []
    for result in results:
        if result.error is not None:
            notes.append(
                f"{result.provider_name}: {result.error.category.value} — {result.error.message}"
            )
        elif result.truncated:
            notes.append(
                f"{result.provider_name}: only the first {result.submitted_characters} of "
                f"{result.input_characters} characters were analysed (provider limit)"
            )
        if "BELOW_RECOMMENDED_MINIMUM" in result.warning_codes:
            notes.append(f"{result.provider_name}: text is shorter than the provider recommends")
    if agreement is not None and agreement < 1.0:
        notes.append(
            "Providers disagree; inspect individual results before drawing a strong conclusion."
        )
    return notes


def check(
    text: str,
    *,
    providers: ProviderSelection = None,
    transport: str = "any",
    verbose: bool = False,
) -> CheckResult:
    """Convenience: ``Checker().check(text, ...)`` with settings from the environment."""
    return Checker().check(text, providers=providers, transport=transport, verbose=verbose)
