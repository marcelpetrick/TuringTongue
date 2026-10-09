#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""Reject tracked repository paths whose components contain whitespace."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path, PurePosixPath


def tracked_paths(root: Path) -> list[str]:
    """Return tracked paths from Git without relying on quoted line output."""
    result = subprocess.run(
        ["git", "-C", os.fspath(root), "ls-files", "-z"],
        check=True,
        capture_output=True,
    )
    return [os.fsdecode(path) for path in result.stdout.split(b"\0") if path]


def has_whitespace_component(path: str) -> bool:
    """Return whether any POSIX path component contains Unicode whitespace."""
    return any(any(character.isspace() for character in part) for part in PurePosixPath(path).parts)


def invalid_paths(paths: list[str]) -> list[str]:
    """Return paths that violate the repository naming invariant."""
    return sorted(path for path in paths if has_whitespace_component(path))


def main(argv: list[str] | None = None) -> int:
    """Check the repository at the optional first argument and report violations."""
    args = sys.argv[1:] if argv is None else argv
    root = Path(args[0]) if args else Path(__file__).resolve().parents[1]
    try:
        offenders = invalid_paths(tracked_paths(root))
    except (OSError, subprocess.CalledProcessError) as error:
        print(f"unable to inspect tracked repository paths: {error}", file=sys.stderr)
        return 2

    for path in offenders:
        print(f"tracked path contains whitespace: {path!r}")
    return 1 if offenders else 0


if __name__ == "__main__":
    sys.exit(main())
