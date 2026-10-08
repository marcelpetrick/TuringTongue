# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""Credential bootstrap for live end-to-end validation (``init -> e2e -> cleanup``).

Only provider-supported mechanisms are automated; account signup on provider websites
is never scripted. See docs/e2e-live.md and ADR 0006.
"""

from turingtongue.credentials.base import (
    PREFERENCE,
    BootstrapReport,
    CredentialState,
    Mechanism,
)
from turingtongue.credentials.bootstrap import bootstrap, cleanup
from turingtongue.credentials.store import CredentialStore

__all__ = [
    "PREFERENCE",
    "BootstrapReport",
    "CredentialState",
    "CredentialStore",
    "Mechanism",
    "bootstrap",
    "cleanup",
]
