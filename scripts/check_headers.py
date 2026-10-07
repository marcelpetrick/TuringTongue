#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""Verify every tracked source file carries the GPL-3.0-or-later SPDX header.

Usage: scripts/check_headers.py [ROOT]

Checks ``*.py`` and ``*.sh`` files under src/, tests/, scripts/ and the repository
root (empty ``__init__.py`` files are exempt). Exits 1 and lists offenders when a
header is missing.
"""

from __future__ import annotations

import sys
from pathlib import Path

SPDX = "SPDX-License-Identifier: GPL-3.0-or-later"
COPYRIGHT = "Copyright (C)"
SEARCH_DIRS = ("src", "tests", "scripts")
HEADER_LINES = 5


def needs_header(path: Path) -> bool:
    """Return True when ``path`` is a non-empty source file that must be licensed."""
    return path.suffix in {".py", ".sh"} and path.stat().st_size > 0


def has_header(path: Path) -> bool:
    """Return True when the SPDX and copyright lines appear near the top of ``path``."""
    head = path.read_text(encoding="utf-8").splitlines()[:HEADER_LINES]
    joined = "\n".join(head)
    return SPDX in joined and COPYRIGHT in joined


def candidates(root: Path) -> list[Path]:
    """List all files under ``root`` that are subject to the header rule."""
    files = [p for p in root.glob("*") if p.is_file()]
    for directory in SEARCH_DIRS:
        files.extend(p for p in (root / directory).rglob("*") if p.is_file())
    return sorted(p for p in files if needs_header(p))


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    root = Path(args[0]) if args else Path(__file__).resolve().parents[1]
    missing = [p for p in candidates(root) if not has_header(p)]
    for path in missing:
        print(f"missing license header: {path.relative_to(root)}")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
