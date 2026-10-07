# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""Single source of the installed package version (read from package metadata)."""

from importlib.metadata import PackageNotFoundError, version


def _read_version() -> str:
    try:
        return version("turingtongue")
    except PackageNotFoundError:  # pragma: no cover - only when running from a raw checkout
        return "0.0.0+unknown"


__version__ = _read_version()
