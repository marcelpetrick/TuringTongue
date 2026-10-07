#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""Bump the SemVer version in pyproject.toml and refresh uv.lock.

Usage:
    scripts/bump_version.py patch   # 0.3.4 -> 0.3.5 (every commit)
    scripts/bump_version.py minor   # 0.3.4 -> 0.4.0 (major features)
    scripts/bump_version.py major   # 0.3.4 -> 1.0.0
    scripts/bump_version.py --show  # print current version
    scripts/bump_version.py minor --from-version 0.3.4  # always 0.4.0, however often run

The new version is printed on stdout. ``uv lock`` is run afterwards so the lock
file records the project's own version too (skip with ``--no-lock``).
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"
_VERSION_LINE = re.compile(r'^version = "(\d+)\.(\d+)\.(\d+)"$', re.MULTILINE)


def read_version(text: str) -> tuple[int, int, int]:
    """Return the ``[project]`` version triple found in pyproject text."""
    match = _VERSION_LINE.search(text)
    if match is None:
        raise ValueError("no 'version = \"X.Y.Z\"' line found in pyproject.toml")
    major, minor, patch = (int(part) for part in match.groups())
    return major, minor, patch


def bumped(current: tuple[int, int, int], part: str) -> tuple[int, int, int]:
    """Return ``current`` bumped by SemVer rules for ``part``."""
    major, minor, patch = current
    if part == "major":
        return major + 1, 0, 0
    if part == "minor":
        return major, minor + 1, 0
    if part == "patch":
        return major, minor, patch + 1
    raise ValueError(f"unknown part: {part}")


def apply(text: str, new: tuple[int, int, int]) -> str:
    """Replace the first version line in pyproject text with ``new``."""
    rendered = ".".join(str(n) for n in new)
    return _VERSION_LINE.sub(f'version = "{rendered}"', text, count=1)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("part", nargs="?", choices=["major", "minor", "patch"])
    parser.add_argument("--show", action="store_true", help="print the current version")
    parser.add_argument("--no-lock", action="store_true", help="do not run 'uv lock'")
    parser.add_argument(
        "--from-version",
        metavar="X.Y.Z",
        help="bump relative to this version instead of the current one (idempotent re-runs)",
    )
    args = parser.parse_args(argv)
    text = PYPROJECT.read_text(encoding="utf-8")
    current = read_version(text)
    if args.show or args.part is None:
        print(".".join(str(n) for n in current))
        return 0
    base = read_version(f'version = "{args.from_version}"') if args.from_version else current
    new = bumped(base, args.part)
    PYPROJECT.write_text(apply(text, new), encoding="utf-8")
    if not args.no_lock:
        subprocess.run(["uv", "lock", "--quiet"], check=True, cwd=PYPROJECT.parent)
    print(".".join(str(n) for n in new))
    return 0


if __name__ == "__main__":
    sys.exit(main())
