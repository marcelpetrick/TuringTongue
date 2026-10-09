# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""Credential mechanisms, lifecycle states and the bootstrap report."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime


class CredentialState(enum.StrEnum):
    """``missing -> provisioning -> valid -> expired/revoked``."""

    MISSING = "missing"
    PROVISIONING = "provisioning"
    VALID = "valid"
    EXPIRED = "expired"
    REVOKED = "revoked"


class Mechanism(enum.StrEnum):
    """How a credential is obtained, in the owner's preference order (see PREFERENCE)."""

    ENVIRONMENT = "environment"
    """Already present in the environment / .env (a CI secret is injected this way)."""
    SANDBOX = "sandbox"
    """Official provider sandbox: real service, test-only classifications, no cost."""
    MACHINE_TOKEN = "machine_token"  # noqa: S105 - mechanism name, not a secret
    """Official API that issues a short-lived token from a long-lived account secret."""
    ACCOUNT_KEY = "account_key"
    """Official API that issues a non-expiring key inside an existing human account."""
    OAUTH = "oauth"
    OWNED_EPHEMERAL = "owned_ephemeral"
    """Short-lived test identity from a service we operate (none exists today)."""
    CI_SECRET = "ci_secret"  # noqa: S105 - mechanism name, not a secret
    MANUAL = "manual"
    """Manual provisioning required: the provider offers no automatable path."""


PREFERENCE: tuple[Mechanism, ...] = (
    Mechanism.ENVIRONMENT,
    Mechanism.SANDBOX,
    Mechanism.MACHINE_TOKEN,
    Mechanism.ACCOUNT_KEY,
    Mechanism.OAUTH,
    Mechanism.OWNED_EPHEMERAL,
    Mechanism.CI_SECRET,
    Mechanism.MANUAL,
)


@dataclass(slots=True)
class BootstrapReport:
    """Outcome of ``init``/``cleanup`` for one provider. Never contains secret values."""

    provider_id: str
    state: CredentialState
    mechanisms: list[Mechanism] = field(default_factory=list)
    message: str = ""
    requests_used: int = 0
    expires_at: datetime | None = None
    reused: bool = False

    @property
    def ready(self) -> bool:
        """True when a live E2E check can run."""
        return self.state is CredentialState.VALID

    def as_dict(self) -> dict[str, object]:
        """Plain data for JSON output."""
        return {
            "provider_id": self.provider_id,
            "state": self.state.value,
            "mechanisms": [m.value for m in self.mechanisms],
            "message": self.message,
            "requests_used": self.requests_used,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "reused": self.reused,
        }
