# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""Typed result model and its stable, versioned JSON representation.

Orientation convention used everywhere in this package::

    normalized_evidence = -1.0  maximally human-leaning evidence
                           0.0  neutral / inconclusive
                          +1.0  maximally AI-leaning evidence

This is *evidence*, not a calibrated probability.
"""

from __future__ import annotations

import dataclasses
import enum
import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

SCHEMA_VERSION = "1.0"
"""Version of the serialized result schema. Bump on any incompatible change."""


class Verdict(enum.StrEnum):
    """Public one-word answer."""

    HUMAN = "human"
    AI = "ai"
    NO_VERDICT = "no_verdict"

    @property
    def display(self) -> str:
        """Upper-case form printed by the CLI (``HUMAN``, ``AI``, ``NO_VERDICT``)."""
        return self.value.upper()


class Diagnostic(enum.StrEnum):
    """Finer internal classification of the ensemble evidence."""

    STRONGLY_HUMAN = "strongly_human"
    HUMAN_LEANING = "human_leaning"
    BORDERLINE = "borderline"
    CONFLICTED = "conflicted"
    AI_LEANING = "ai_leaning"
    STRONGLY_AI = "strongly_ai"
    NO_EVIDENCE = "no_evidence"


class TransportKind(enum.StrEnum):
    """How a provider is reached."""

    API = "api"
    SDK = "sdk"
    BROWSER = "browser"
    MOCK = "mock"


class ProviderStatus(enum.StrEnum):
    """Outcome of one provider attempt."""

    OK = "ok"
    FAILED = "failed"


class ErrorCategory(enum.StrEnum):
    """Common failure categories (vision §7.3). Failures are data, not crashes."""

    NOT_CONFIGURED = "NOT_CONFIGURED"
    AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"
    AUTHORIZATION_FAILED = "AUTHORIZATION_FAILED"
    RATE_LIMITED = "RATE_LIMITED"
    QUOTA_EXHAUSTED = "QUOTA_EXHAUSTED"
    TIMEOUT = "TIMEOUT"
    NETWORK_ERROR = "NETWORK_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    INVALID_RESPONSE = "INVALID_RESPONSE"
    SCHEMA_CHANGED = "SCHEMA_CHANGED"
    INPUT_TOO_SHORT = "INPUT_TOO_SHORT"
    INPUT_TOO_LARGE = "INPUT_TOO_LARGE"
    UNSUPPORTED_INPUT = "UNSUPPORTED_INPUT"
    UNSUPPORTED_LANGUAGE = "UNSUPPORTED_LANGUAGE"
    BROWSER_AUTOMATION_FAILED = "BROWSER_AUTOMATION_FAILED"
    TERMS_NOT_PERMITTED = "TERMS_NOT_PERMITTED"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


@dataclass(frozen=True, slots=True)
class Segment:
    """Provider-returned sub-result (sentence, window, paragraph…).

    Offsets index into the *submitted* text. The text itself is not copied here so
    results can be shared without leaking the document.
    """

    start: int | None
    end: int | None
    label: str | None = None
    score: float | None = None
    kind: str = "segment"


@dataclass(frozen=True, slots=True)
class RateLimitInfo:
    """Rate-limit metadata reported by the provider (headers or body)."""

    limit: int | None = None
    remaining: int | None = None
    reset: str | None = None
    retry_after_s: float | None = None


@dataclass(frozen=True, slots=True)
class CostInfo:
    """Billing metadata — only filled when the provider reports it reliably."""

    credits_used: float | None = None
    credits_remaining: float | None = None
    estimated_cost: float | None = None
    currency: str | None = None
    billing_unit: str | None = None


@dataclass(frozen=True, slots=True)
class ProviderError:
    """A provider failure record. Never contains secrets."""

    provider_id: str
    category: ErrorCategory
    message: str
    http_status: int | None = None
    retryable: bool = False
    attempt_count: int = 0
    latency_ms: float | None = None


@dataclass(slots=True)
class ProviderResult:
    """Everything known about one provider attempt, native and normalized."""

    provider_id: str
    provider_name: str
    transport: TransportKind
    status: ProviderStatus
    raw_label: str | None = None
    raw_score: float | None = None
    raw_confidence: str | float | None = None
    score_semantics: str | None = None
    normalized_evidence: float | None = None
    normalized_confidence: float | None = None
    model: str | None = None
    model_version: str | None = None
    segments: list[Segment] = field(default_factory=list)
    input_characters: int = 0
    submitted_characters: int = 0
    input_coverage: float = 0.0
    truncated: bool = False
    latency_ms: float | None = None
    attempt_count: int = 0
    rate_limit: RateLimitInfo | None = None
    cost: CostInfo | None = None
    warning_codes: list[str] = field(default_factory=list)
    error: ProviderError | None = None
    checked_at: str | None = None
    adapter_version: str | None = None
    phase_timings_ms: dict[str, float] = field(default_factory=dict)
    vote_weight: float | None = None
    weight_factors: dict[str, float] = field(default_factory=dict)
    included_in_ensemble: bool = False
    exclusion_reason: str | None = None
    raw_response: Any = None

    @property
    def ok(self) -> bool:
        """True when the provider produced usable evidence."""
        return self.status is ProviderStatus.OK and self.normalized_evidence is not None


@dataclass(frozen=True, slots=True)
class InputInfo:
    """Size and fingerprint of the caller's text (the text itself is not stored)."""

    characters: int
    words: int
    utf8_bytes: int
    sha256: str

    @classmethod
    def from_text(cls, text: str) -> InputInfo:
        """Describe ``text`` without altering or retaining it."""
        encoded = text.encode("utf-8", errors="surrogatepass")
        return cls(
            characters=len(text),
            words=len(text.split()),
            utf8_bytes=len(encoded),
            sha256=hashlib.sha256(encoded).hexdigest(),
        )


@dataclass(frozen=True, slots=True)
class Aggregate:
    """Ensemble outcome. Evidence, confidence and agreement are distinct concepts."""

    evidence_score: float | None
    strength: float
    confidence: float
    agreement: float | None
    effective_weight: float
    providers_used: int
    diagnostic: Diagnostic
    reasons: list[str] = field(default_factory=list)
    weights_version: str = ""
    policy: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Timing:
    """Run timing. Providers run concurrently, so the latency sum != wall clock."""

    started_at: str
    finished_at: str
    wall_clock_ms: float
    ensemble_ms: float
    provider_latency_sum_ms: float


@dataclass(slots=True)
class CheckResult:
    """Top-level result of one check. Serializes to versioned JSON."""

    verdict: Verdict
    aggregate: Aggregate
    input: InputInfo
    providers: list[ProviderResult]
    timing: Timing
    selection: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    package_version: str = ""
    schema_version: str = SCHEMA_VERSION

    @property
    def errors(self) -> list[ProviderError]:
        """All provider failures of this run."""
        return [p.error for p in self.providers if p.error is not None]

    def to_dict(self) -> dict[str, Any]:
        """Plain-data form with a stable top-level key order (schema_version first)."""
        body: dict[str, Any] = _plain(self)
        body["errors"] = [_plain(e) for e in self.errors]
        order = ["schema_version", "package_version", "verdict", "aggregate", "input"]
        ordered = {key: body.pop(key) for key in order}
        ordered.update(body)
        return ordered

    def to_json(self, *, indent: int | None = 2) -> str:
        """Serialize to JSON (UTF-8 safe, non-ASCII preserved)."""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


def _plain(value: Any) -> Any:
    """Recursively convert dataclasses/enums to JSON-compatible data."""
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {f.name: _plain(getattr(value, f.name)) for f in dataclasses.fields(value)}
    if isinstance(value, enum.Enum):
        return value.value
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_plain(v) for v in value]
    return value
