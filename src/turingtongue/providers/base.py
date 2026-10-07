# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""Common provider protocol and the shared adapter flow (vision §5).

An adapter owns authentication, request construction, provider-specific limits,
response parsing, score semantics, model/version and segment extraction, rate-limit
and cost metadata, and error mapping. It never decides the ensemble verdict.
"""

from __future__ import annotations

import abc
import logging
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

import httpx

from turingtongue._version import __version__
from turingtongue.config import Settings
from turingtongue.ensemble import WARN_BELOW_RECOMMENDED_MINIMUM, WARN_TRUNCATED
from turingtongue.errors import ProviderFailure
from turingtongue.models import (
    CostInfo,
    ErrorCategory,
    ProviderError,
    ProviderResult,
    ProviderStatus,
    RateLimitInfo,
    Segment,
    TransportKind,
)
from turingtongue.normalization.limits import PreparedInput, measure, prepare_input
from turingtongue.redaction import redact
from turingtongue.registry import ProviderSpec
from turingtongue.transport import HttpCaller, RetryPolicy

logger = logging.getLogger("turingtongue.providers")


@dataclass(frozen=True, slots=True)
class DetectionOptions:
    """Per-call options passed to an adapter."""

    timeout_s: float = 30.0
    capture_raw: bool = False
    provider_options: Mapping[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Detection:
    """Parsed provider answer, before it becomes a ProviderResult.

    ``exclude_reason`` keeps a result visible but out of the ensemble (e.g. sandbox
    mode returning mock classifications).
    """

    evidence: float
    score_semantics: str
    raw_label: str | None = None
    raw_score: float | None = None
    raw_confidence: str | float | None = None
    confidence: float | None = None
    model: str | None = None
    model_version: str | None = None
    segments: list[Segment] = field(default_factory=list)
    cost: CostInfo | None = None
    warnings: list[str] = field(default_factory=list)
    attempts: int = 1
    rate_limit: RateLimitInfo | None = None
    raw: Any = None
    exclude_reason: str | None = None


class Provider(Protocol):
    """What the orchestrator needs from any provider (API, browser or mock)."""

    spec: ProviderSpec

    async def detect(self, text: str, *, options: DetectionOptions) -> ProviderResult:
        """Analyse ``text`` (exactly as given) and return a result — never raise."""
        ...


class ProviderFactory(Protocol):
    """Callable that builds a provider for one run."""

    def __call__(
        self, spec: ProviderSpec, settings: Settings, client: httpx.AsyncClient
    ) -> Provider: ...


def now_iso() -> str:
    """Current UTC time in ISO-8601."""
    return datetime.now(UTC).isoformat(timespec="milliseconds")


def failure_result(
    spec: ProviderSpec,
    failure: ProviderFailure,
    *,
    text: str = "",
    latency_ms: float | None = None,
    checked_at: str | None = None,
) -> ProviderResult:
    """Build a failed ProviderResult from a categorized failure."""
    return ProviderResult(
        provider_id=spec.id,
        provider_name=spec.name,
        transport=spec.transport,
        status=ProviderStatus.FAILED,
        input_characters=len(text),
        latency_ms=latency_ms,
        attempt_count=failure.attempt_count,
        rate_limit=failure.rate_limit,
        error=ProviderError(
            provider_id=spec.id,
            category=failure.category,
            message=failure.message,
            http_status=failure.http_status,
            retryable=failure.retryable,
            attempt_count=failure.attempt_count,
            latency_ms=latency_ms,
        ),
        checked_at=checked_at or now_iso(),
        adapter_version=__version__,
        exclusion_reason=failure.category.value,
    )


class BaseProvider(abc.ABC):
    """Shared flow: credentials → limits → call → parse → ProviderResult."""

    def __init__(self, spec: ProviderSpec, settings: Settings, client: httpx.AsyncClient) -> None:
        self.spec = spec
        self.settings = settings
        self.client = client

    # -- hooks for subclasses -------------------------------------------------------
    @abc.abstractmethod
    async def _detect(
        self, prepared: PreparedInput, caller: HttpCaller, options: DetectionOptions
    ) -> Detection:
        """Send ``prepared.text`` and parse the provider's answer."""

    def max_input(self, options: DetectionOptions) -> int | None:
        """Hard maximum in ``spec.limit_unit`` (override for plan-dependent limits)."""
        return self.spec.known_max_input

    # -- helpers --------------------------------------------------------------------
    def credential(self, name: str) -> str:
        """Return a required credential or raise NOT_CONFIGURED.

        ``name`` may list aliases as ``"A|B"``; the first one that is set wins.
        """
        for alias in name.split("|"):
            value = self.settings.credential(alias)
            if value is not None:
                return value
        raise ProviderFailure(
            ErrorCategory.NOT_CONFIGURED,
            f"{self.spec.name}: environment variable {name.replace('|', ' or ')} is not set",
        )

    def option(self, options: DetectionOptions, key: str, default: Any) -> Any:
        """Provider option from config/call, falling back to ``default``."""
        return options.provider_options.get(key, default)

    def _secrets(self) -> list[str | None]:
        return [
            self.settings.credential(alias)
            for entry in self.spec.credential_env
            for alias in entry.split("|")
        ]

    def _caller(self) -> HttpCaller:
        s = self.settings
        return HttpCaller(
            self.client,
            provider_name=self.spec.name,
            policy=RetryPolicy(
                max_retries=s.max_retries, base_s=s.backoff_base_s, max_s=s.backoff_max_s
            ),
            max_response_bytes=s.max_response_bytes,
            secrets=self._secrets(),
        )

    @staticmethod
    def schema_error(message: str) -> ProviderFailure:
        """Failure for a response that does not match the documented schema."""
        return ProviderFailure(ErrorCategory.SCHEMA_CHANGED, message, retryable=False)

    # -- main entry point -----------------------------------------------------------
    async def detect(self, text: str, *, options: DetectionOptions) -> ProviderResult:
        """Run the adapter; every failure is returned as data, never raised."""
        checked_at = now_iso()
        started = time.perf_counter()
        caller: HttpCaller | None = None
        try:
            for name in self.spec.credential_env:
                self.credential(name)
            prepared = prepare_input(
                text,
                max_size=self.max_input(options),
                min_size=self.spec.known_min_input,
                unit=self.spec.limit_unit,
            )
            prepare_ms = (time.perf_counter() - started) * 1000
            caller = self._caller()
            detection = await self._detect(prepared, caller, options)
        except ProviderFailure as failure:
            failure.message = redact(failure.message, self._secrets())
            return failure_result(
                self.spec,
                failure,
                text=text,
                latency_ms=(time.perf_counter() - started) * 1000,
                checked_at=checked_at,
            )
        except (KeyError, TypeError, ValueError, AttributeError, IndexError) as exc:
            logger.debug("%s: unexpected response shape", self.spec.id, exc_info=True)
            shape_failure = self.schema_error(
                f"{self.spec.name}: unexpected response shape ({type(exc).__name__}: "
                f"{redact(str(exc), self._secrets())[:200]})"
            )
            return failure_result(
                self.spec,
                shape_failure,
                text=text,
                latency_ms=(time.perf_counter() - started) * 1000,
                checked_at=checked_at,
            )
        latency_ms = (time.perf_counter() - started) * 1000
        warnings = list(detection.warnings)
        if prepared.truncated:
            warnings.append(WARN_TRUNCATED)
        size = measure(text, self.spec.limit_unit)
        minimum = self.spec.recommended_min_input
        if minimum is not None and size is not None and size < minimum:
            warnings.append(WARN_BELOW_RECOMMENDED_MINIMUM)
        network_ms = caller.network_ms
        return ProviderResult(
            provider_id=self.spec.id,
            provider_name=self.spec.name,
            transport=self.spec.transport,
            status=ProviderStatus.OK,
            raw_label=detection.raw_label,
            raw_score=detection.raw_score,
            raw_confidence=detection.raw_confidence,
            score_semantics=detection.score_semantics,
            normalized_evidence=(
                None if detection.exclude_reason else max(-1.0, min(1.0, detection.evidence))
            ),
            normalized_confidence=detection.confidence,
            model=detection.model,
            model_version=detection.model_version,
            segments=detection.segments,
            input_characters=prepared.input_characters,
            submitted_characters=prepared.submitted_characters,
            input_coverage=prepared.coverage,
            truncated=prepared.truncated,
            latency_ms=latency_ms,
            attempt_count=detection.attempts,
            rate_limit=detection.rate_limit,
            cost=detection.cost,
            warning_codes=warnings,
            checked_at=checked_at,
            adapter_version=__version__,
            phase_timings_ms={
                "prepare": prepare_ms,
                "network": network_ms,
                "parse_and_overhead": max(0.0, latency_ms - prepare_ms - network_ms),
            },
            raw_response=detection.raw if options.capture_raw else None,
            exclusion_reason=detection.exclude_reason,
        )


def transport_matches(kind: TransportKind, wanted: str) -> bool:
    """Transport filter used for provider selection (``api``/``browser``/``any``)."""
    match wanted:
        case "api":
            return kind in {TransportKind.API, TransportKind.SDK}
        case "browser":
            return kind is TransportKind.BROWSER
        case "mock":
            return kind is TransportKind.MOCK
        case _:
            return True
