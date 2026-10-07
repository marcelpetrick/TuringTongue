#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""Set the status of a task in plan.md (checkbox, Status line, acceptance boxes, notes).

Usage:
    scripts/plan_task.py T021 in_progress
    scripts/plan_task.py T021 done --note "fixtures from official docs"
    scripts/plan_task.py T054 blocked --note "API undocumented"

``done`` ticks the task and all its acceptance checkboxes; other statuses untick them.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

PLAN = Path(__file__).resolve().parents[1] / "plan.md"
STATUSES = ("todo", "in_progress", "done", "blocked")


def update(text: str, task_id: str, status: str, note: str | None) -> str:
    """Return plan text with ``task_id`` set to ``status`` (and ``note`` if given)."""
    start = re.search(rf"^- \[[ x]\] {re.escape(task_id)} — ", text, re.MULTILINE)
    if start is None:
        raise KeyError(f"task {task_id} not found")
    nxt = re.search(r"^(- \[|## )", text[start.end() :], re.MULTILINE)
    end = start.end() + nxt.start() if nxt else len(text)
    block = text[start.start() : end]
    box = "x" if status == "done" else " "
    block = re.sub(r"^- \[[ x]\]", f"- [{box}]", block, count=1)
    block = re.sub(r"^(    - )\[[ x]\]", rf"\g<1>[{box}]", block, flags=re.MULTILINE)
    block = re.sub(r"(  - Status: )\S+", rf"\g<1>{status}", block, count=1)
    if note is not None:
        block = re.sub(r"(  - Notes: ).*", lambda m: m.group(1) + note, block, count=1)
    return text[: start.start()] + block + text[end:]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("task_id")
    parser.add_argument("status", choices=STATUSES)
    parser.add_argument("--note")
    parser.add_argument("--plan", type=Path, default=PLAN)
    args = parser.parse_args(argv)
    text = args.plan.read_text(encoding="utf-8")
    args.plan.write_text(update(text, args.task_id, args.status, args.note), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
