# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""TuringTongue: a transparent ensemble over existing AI-text detection services.

>>> from turingtongue import Checker
>>> result = Checker().check(text)                       # doctest: +SKIP
>>> result.verdict.display                               # doctest: +SKIP
'HUMAN'

Calling a check sends the text to third-party services; see docs/privacy.md.
Results are indicators, not proof of authorship.
"""

from turingtongue._version import __version__
from turingtongue.client import Checker, check
from turingtongue.config import Settings
from turingtongue.ensemble import EnsemblePolicy
from turingtongue.errors import ConfigurationError, ProviderFailure, TuringTongueError
from turingtongue.models import (
    SCHEMA_VERSION,
    CheckResult,
    Diagnostic,
    ErrorCategory,
    ProviderResult,
    TransportKind,
    Verdict,
)
from turingtongue.registry import ProviderSpec, Registry

__all__ = [
    "SCHEMA_VERSION",
    "CheckResult",
    "Checker",
    "ConfigurationError",
    "Diagnostic",
    "EnsemblePolicy",
    "ErrorCategory",
    "ProviderFailure",
    "ProviderResult",
    "ProviderSpec",
    "Registry",
    "Settings",
    "TransportKind",
    "TuringTongueError",
    "Verdict",
    "__version__",
    "check",
]
