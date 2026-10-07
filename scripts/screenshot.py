#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""Capture real CLI output as PNG for the README (SVG if rsvg-convert is missing).

Usage: scripts/screenshot.py [OUT_DIR]   (default: docs/images)

Runs the actual CLI code paths in-process with a recording rich console: the verbose
report of a check (mock provider + every real provider, which are unconfigured in a
credential-free environment) and the ``providers`` listing.
"""

from __future__ import annotations

import io
import shutil
import subprocess
import sys
from pathlib import Path

from rich.console import Console

from turingtongue import Checker, Settings
from turingtongue.cli.output import render_providers, render_verbose

TEXT = (
    "It was on a dreary night of November that I beheld the accomplishment of my toils. "
    "With an anxiety that almost amounted to agony, I collected the instruments of life "
    "around me, that I might infuse a spark of being into the lifeless thing that lay at "
    "my feet."
)


def capture(out_dir: Path) -> list[Path]:
    """Write verbose-check and providers screenshots; return the written files."""
    out_dir.mkdir(parents=True, exist_ok=True)
    checker = Checker(Settings(env={"TURINGTONGUE_NO_DOTENV": "1"}))
    written = []
    console = Console(
        record=True,
        width=150,
        force_terminal=True,
        color_system="truecolor",
        highlight=False,
        file=io.StringIO(),
    )
    console.print("$ turingtongue check frankenstein.txt --verbose -p mock -p all\n", style="bold")
    render_verbose(checker.check(TEXT, providers=["mock", "all"]), console)
    written.append(out_dir / "verbose-check.svg")
    console.save_svg(str(written[-1]), title="turingtongue check --verbose")
    console = Console(
        record=True,
        width=150,
        force_terminal=True,
        color_system="truecolor",
        highlight=False,
        file=io.StringIO(),
    )
    console.print("$ turingtongue providers\n", style="bold")
    render_providers(checker.registry, checker.settings.env, console)
    written.append(out_dir / "providers.svg")
    console.save_svg(str(written[-1]), title="turingtongue providers")
    converter = shutil.which("rsvg-convert")
    if converter:
        for svg in list(written):
            png = svg.with_suffix(".png")
            subprocess.run([converter, "-z", "1.5", "-o", str(png), str(svg)], check=True)
            svg.unlink()
            written.remove(svg)
            written.append(png)
    return written


if __name__ == "__main__":
    for path in capture(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("docs/images")):
        print(path)
