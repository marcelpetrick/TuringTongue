# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""Runtime configuration: credentials from the environment, optional TOML file.

Precedence (highest first):

1. explicit keyword arguments / ``Settings`` fields set in code;
2. the TOML config file (``$TURINGTONGUE_CONFIG`` or ``~/.config/turingtongue/config.toml``);
3. built-in defaults.

Credentials are **only** read from environment variables (optionally pre-filled from a
local, gitignored ``.env`` file that never overrides real environment variables). The
config file rejects secret-looking keys so secrets do not end up there by accident.
"""

from __future__ import annotations

import json
import os
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from turingtongue.errors import ConfigurationError

CONFIG_ENV_VAR = "TURINGTONGUE_CONFIG"
NO_DOTENV_ENV_VAR = "TURINGTONGUE_NO_DOTENV"
DEFAULT_CONFIG_PATH = Path("~/.config/turingtongue/config.toml")
_SECRET_KEYS = ("key", "token", "secret", "password")
_GLOBAL_KEYS = {
    "timeout_s",
    "deadline_s",
    "max_concurrency",
    "per_provider_concurrency",
    "max_retries",
    "backoff_base_s",
    "backoff_max_s",
    "max_response_bytes",
}
_PROVIDER_KEYS = {"enabled", "weight", "timeout_s", "options"}


@dataclass(frozen=True, slots=True)
class ProviderOverrides:
    """Per-provider settings from the config file."""

    enabled: bool | None = None
    weight: float | None = None
    timeout_s: float | None = None
    options: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Settings:
    """All tunables of a check run. Defaults are deliberately conservative."""

    timeout_s: float = 30.0
    """Per-provider deadline for one complete provider call including retries."""
    deadline_s: float | None = 120.0
    """Overall run deadline; providers still running are reported as TIMEOUT."""
    max_concurrency: int = 4
    """Global cap of providers running at the same time."""
    per_provider_concurrency: int = 1
    """Cap of simultaneous requests to one provider (avoids bursts)."""
    max_retries: int = 2
    """Retries after the first attempt, only for transient failures."""
    backoff_base_s: float = 0.5
    backoff_max_s: float = 8.0
    max_response_bytes: int = 5_000_000
    capture_raw: bool = False
    """Keep (redacted) raw provider responses in results — for debugging only."""
    providers: Mapping[str, ProviderOverrides] = field(default_factory=dict)
    env: Mapping[str, str] = field(default_factory=lambda: dict(os.environ))

    def credential(self, name: str) -> str | None:
        """Return a credential from the environment, or None when absent/blank."""
        value = self.env.get(name, "").strip()
        return value or None

    def overrides(self, provider_id: str) -> ProviderOverrides:
        """Per-provider overrides (empty when not configured)."""
        return self.providers.get(provider_id, ProviderOverrides())

    def with_changes(self, **changes: Any) -> Settings:
        """Return a copy with some fields replaced."""
        return replace(self, **changes)

    @classmethod
    def load(
        cls,
        config_path: str | Path | None = None,
        *,
        env: Mapping[str, str] | None = None,
        dotenv_path: str | Path | None = ".env",
    ) -> Settings:
        """Build settings from environment, optional ``.env`` and optional TOML file."""
        environment = dict(os.environ if env is None else env)
        if dotenv_path is not None and not environment.get(NO_DOTENV_ENV_VAR):
            for key, value in read_dotenv(Path(dotenv_path)).items():
                environment.setdefault(key, value)
        path = _resolve_config_path(config_path, environment)
        data = _read_toml(path) if path is not None else {}
        return _from_mapping(data, environment)


def _resolve_config_path(explicit: str | Path | None, env: Mapping[str, str]) -> Path | None:
    if explicit is not None:
        path = Path(explicit).expanduser()
        if not path.is_file():
            raise ConfigurationError(f"config file not found: {path}")
        return path
    if env.get(CONFIG_ENV_VAR):
        return _resolve_config_path(env[CONFIG_ENV_VAR], {})
    default = DEFAULT_CONFIG_PATH.expanduser()
    return default if default.is_file() else None


def _read_toml(path: Path) -> dict[str, Any]:
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ConfigurationError(f"cannot read config file {path}: {exc}") from exc


def _reject_secrets(section: str, keys: Mapping[str, Any]) -> None:
    for key in keys:
        if any(marker in key.lower() for marker in _SECRET_KEYS):
            raise ConfigurationError(
                f"'{section}.{key}' looks like a secret; put credentials in environment variables"
            )


def _from_mapping(data: Mapping[str, Any], env: Mapping[str, str]) -> Settings:
    defaults = data.get("defaults", {})
    unknown = set(data) - {"defaults", "providers"}
    if unknown:
        raise ConfigurationError(f"unknown config sections: {sorted(unknown)}")
    _reject_secrets("defaults", defaults)
    bad = set(defaults) - _GLOBAL_KEYS
    if bad:
        raise ConfigurationError(f"unknown keys in [defaults]: {sorted(bad)}")
    providers: dict[str, ProviderOverrides] = {}
    for provider_id, section in data.get("providers", {}).items():
        _reject_secrets(f"providers.{provider_id}", section)
        bad = set(section) - _PROVIDER_KEYS
        if bad:
            raise ConfigurationError(f"unknown keys in [providers.{provider_id}]: {sorted(bad)}")
        providers[provider_id] = ProviderOverrides(
            enabled=section.get("enabled"),
            weight=_non_negative(section.get("weight"), f"providers.{provider_id}.weight"),
            timeout_s=section.get("timeout_s"),
            options=dict(section.get("options", {})),
        )
    try:
        return Settings(providers=providers, env=env, **defaults)
    except TypeError as exc:  # pragma: no cover - guarded by key validation above
        raise ConfigurationError(str(exc)) from exc


def _non_negative(value: Any, name: str) -> float | None:
    if value is None:
        return None
    if not isinstance(value, int | float) or value < 0:
        raise ConfigurationError(f"{name} must be a non-negative number")
    return float(value)


def read_dotenv(path: Path) -> dict[str, str]:
    """Parse a minimal ``.env`` file (``KEY=value``, ``export``, quotes, ``#`` comments)."""
    if not path.is_file():
        return {}
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.removeprefix("export ").partition("=")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] == '"':
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                value = value[1:-1]
        elif len(value) >= 2 and value[0] == value[-1] == "'":
            value = value[1:-1]
        else:
            value = value.split(" #", 1)[0].strip()
        values[key.strip()] = value
    return values
