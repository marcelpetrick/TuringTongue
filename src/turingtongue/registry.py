# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""Machine-readable provider registry (vision §5.3).

Frequently changing provider facts (limits, defaults, verification dates) live in
``data/providers.toml`` so they can be updated without touching adapter or ensemble
code. Adapters are imported lazily, which keeps optional (browser) providers from
affecting API-only users.
"""

from __future__ import annotations

import importlib
import tomllib
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from importlib import resources
from typing import TYPE_CHECKING, Any

from turingtongue.errors import ConfigurationError
from turingtongue.models import TransportKind
from turingtongue.normalization.limits import LimitUnit

if TYPE_CHECKING:
    from turingtongue.providers.base import ProviderFactory


@dataclass(frozen=True, slots=True)
class ProviderSpec:
    """Static metadata about one provider integration."""

    id: str
    name: str
    transport: TransportKind
    adapter: str
    """``module:Class`` path of the adapter, imported on first use."""
    requires_credentials: bool
    credential_env: tuple[str, ...]
    enabled_by_default: bool
    supports_segments: bool
    supports_mixed_label: bool
    supports_model_version: bool
    known_min_input: int | None
    recommended_min_input: int | None
    known_max_input: int | None
    limit_unit: LimitUnit
    known_languages: str
    adapter_status: str
    last_verified: str
    docs_url: str
    notes: str = ""
    endpoint: str = ""
    bootstrap: tuple[str, ...] = ("environment",)
    """Credential bootstrap mechanisms the provider supports (see credentials.Mechanism)."""
    credential_help: str = ""
    """Actionable instructions when a credential has to be provisioned manually."""
    extra: Mapping[str, Any] = field(default_factory=dict)

    def missing_credentials(self, env_lookup: Mapping[str, str] | None = None) -> list[str]:
        """Required environment variables that are absent or blank.

        An entry ``"A|B"`` is satisfied by either variable (documented aliases) and is
        reported as ``"A or B"``.
        """
        env = env_lookup or {}
        return [
            entry.replace("|", " or ")
            for entry in self.credential_env
            if not any(env.get(name, "").strip() for name in entry.split("|"))
        ]

    def load_adapter(self) -> ProviderFactory:
        """Import and return the adapter class."""
        module_name, _, attr = self.adapter.partition(":")
        factory: ProviderFactory = getattr(importlib.import_module(module_name), attr)
        return factory


_REQUIRED = {"name", "transport", "adapter"}


def _spec(provider_id: str, raw: Mapping[str, Any]) -> ProviderSpec:
    missing = _REQUIRED - set(raw)
    if missing:
        raise ConfigurationError(f"provider '{provider_id}' lacks fields {sorted(missing)}")
    known = {f for f in ProviderSpec.__dataclass_fields__ if f not in {"id", "extra"}}
    return ProviderSpec(
        id=provider_id,
        name=raw["name"],
        transport=TransportKind(raw["transport"]),
        adapter=raw["adapter"],
        requires_credentials=bool(raw.get("requires_credentials", True)),
        credential_env=tuple(raw.get("credential_env", ())),
        enabled_by_default=bool(raw.get("enabled_by_default", False)),
        supports_segments=bool(raw.get("supports_segments", False)),
        supports_mixed_label=bool(raw.get("supports_mixed_label", False)),
        supports_model_version=bool(raw.get("supports_model_version", False)),
        known_min_input=raw.get("known_min_input"),
        recommended_min_input=raw.get("recommended_min_input"),
        known_max_input=raw.get("known_max_input"),
        limit_unit=LimitUnit(raw.get("limit_unit", "characters")),
        known_languages=raw.get("known_languages", "unknown"),
        adapter_status=raw.get("adapter_status", "unknown"),
        last_verified=raw.get("last_verified", "unknown"),
        docs_url=raw.get("docs_url", ""),
        notes=raw.get("notes", ""),
        endpoint=raw.get("endpoint", ""),
        bootstrap=tuple(raw.get("bootstrap", ("environment",))),
        credential_help=raw.get("credential_help", ""),
        extra={k: v for k, v in raw.items() if k not in known},
    )


class Registry:
    """Ordered collection of provider specs."""

    def __init__(self, specs: Iterable[ProviderSpec]) -> None:
        self._specs = {spec.id: spec for spec in specs}

    @classmethod
    def from_toml(cls, text: str) -> Registry:
        """Parse a registry document (``[providers.<id>]`` tables)."""
        data = tomllib.loads(text)
        return cls(_spec(pid, raw) for pid, raw in data.get("providers", {}).items())

    @classmethod
    def builtin(cls) -> Registry:
        """The registry shipped with the package."""
        text = resources.files("turingtongue.data").joinpath("providers.toml").read_text("utf-8")
        return cls.from_toml(text)

    def __iter__(self) -> Iterator[ProviderSpec]:
        return iter(self._specs.values())

    def __len__(self) -> int:
        return len(self._specs)

    def __contains__(self, provider_id: object) -> bool:
        return provider_id in self._specs

    def get(self, provider_id: str) -> ProviderSpec:
        """Spec by id; raises ConfigurationError for unknown ids."""
        try:
            return self._specs[provider_id.strip().lower()]
        except KeyError:
            known = ", ".join(self._specs)
            raise ConfigurationError(
                f"unknown provider '{provider_id}'. Known providers: {known}"
            ) from None

    def ids(self) -> list[str]:
        """All provider ids in registry order."""
        return list(self._specs)
