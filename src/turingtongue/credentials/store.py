# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""Run-scoped store for short-lived machine-issued tokens (never long-lived keys).

Location: ``$TURINGTONGUE_E2E_STATE_DIR`` or ``$XDG_RUNTIME_DIR/turingtongue-e2e`` or a
per-user directory in the system temp dir. Directory mode 0700, files 0600; ``cleanup``
deletes the entry. Long-lived account secrets stay in environment variables / CI secrets.
"""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path

STATE_DIR_ENV = "TURINGTONGUE_E2E_STATE_DIR"


def default_state_dir(env: Mapping[str, str]) -> Path:
    """Where run-scoped tokens live."""
    if env.get(STATE_DIR_ENV):
        return Path(env[STATE_DIR_ENV])
    runtime = env.get("XDG_RUNTIME_DIR")
    if runtime:
        return Path(runtime) / "turingtongue-e2e"
    return Path(tempfile.gettempdir()) / f"turingtongue-e2e-{os.getuid()}"


class CredentialStore:
    """JSON files ``<provider>.json`` holding ``{"token", "expires", "account"}``."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def _path(self, provider_id: str) -> Path:
        return self.directory / f"{provider_id}.json"

    def save(self, provider_id: str, *, token: str, expires: datetime, account: str) -> None:
        """Persist a token with owner-only permissions."""
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.directory.chmod(0o700)
        path = self._path(provider_id)
        payload = json.dumps({"token": token, "expires": expires.isoformat(), "account": account})
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(payload)
        path.chmod(0o600)

    def load(self, provider_id: str) -> dict[str, str] | None:
        """Stored entry or None (missing / unreadable)."""
        try:
            data = json.loads(self._path(provider_id).read_text(encoding="utf-8"))
        except OSError, ValueError:
            return None
        return data if isinstance(data, dict) else None

    def delete(self, provider_id: str) -> bool:
        """Remove the entry; True when something was deleted."""
        try:
            self._path(provider_id).unlink()
        except FileNotFoundError:
            return False
        return True
