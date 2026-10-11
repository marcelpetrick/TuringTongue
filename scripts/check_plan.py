#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""Reject inconsistent task state in the durable execution ledger."""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

TASK_RE = re.compile(r"^- \[(?P<checked>[ x])\] (?P<task_id>T\d+)\b")
STATUS_RE = re.compile(r"^  - Status: (?P<status>\S+)\s*$")
ACCEPTANCE_ITEM_RE = re.compile(r"^    - \[(?P<checked>[ x])\]")
VALID_STATUSES = frozenset({"todo", "in_progress", "done", "blocked", "dropped"})


@dataclass
class Task:
    """State parsed from one plan task block."""

    task_id: str
    line_number: int
    checked: bool
    statuses: list[tuple[str, int]] = field(default_factory=list)
    acceptance_heading: bool = False
    acceptance: list[tuple[bool, int]] = field(default_factory=list)


def parse_tasks(text: str) -> list[Task]:
    """Parse task state without interpreting prose or nested notes."""
    tasks: list[Task] = []
    current: Task | None = None
    in_acceptance = False

    for line_number, line in enumerate(text.splitlines(), start=1):
        task_match = TASK_RE.match(line)
        if task_match:
            current = Task(
                task_id=task_match.group("task_id"),
                line_number=line_number,
                checked=task_match.group("checked") == "x",
            )
            tasks.append(current)
            in_acceptance = False
            continue
        if current is None:
            continue

        status_match = STATUS_RE.match(line)
        if status_match:
            current.statuses.append((status_match.group("status"), line_number))
            in_acceptance = False
            continue
        if line == "  - Acceptance:":
            current.acceptance_heading = True
            in_acceptance = True
            continue
        if line.startswith("  - "):
            in_acceptance = False
            continue
        if in_acceptance and (item_match := ACCEPTANCE_ITEM_RE.match(line)):
            current.acceptance.append((item_match.group("checked") == "x", line_number))

    return tasks


def validate(text: str) -> list[str]:
    """Return deterministic, line-oriented ledger consistency errors."""
    errors: list[str] = []
    seen: dict[str, int] = {}
    tasks = parse_tasks(text)
    if not tasks:
        return ["plan contains no T-numbered tasks"]

    for task in tasks:
        if first_line := seen.get(task.task_id):
            errors.append(
                f"line {task.line_number}: duplicate {task.task_id} "
                f"(first declared on line {first_line})"
            )
        else:
            seen[task.task_id] = task.line_number

        if len(task.statuses) != 1:
            errors.append(
                f"line {task.line_number}: {task.task_id} must have exactly one Status line "
                f"(found {len(task.statuses)})"
            )
            continue

        status, status_line = task.statuses[0]
        if status not in VALID_STATUSES:
            errors.append(f"line {status_line}: {task.task_id} has unknown status {status!r}")
            continue

        expected_checked = status == "done"
        if task.checked != expected_checked:
            expected = "checked" if expected_checked else "unchecked"
            errors.append(
                f"line {task.line_number}: {task.task_id} with status {status!r} must be {expected}"
            )

        if not task.acceptance_heading or not task.acceptance:
            errors.append(f"line {task.line_number}: {task.task_id} has no acceptance criteria")
        elif status == "done":
            for checked, line_number in task.acceptance:
                if not checked:
                    errors.append(
                        f"line {line_number}: completed {task.task_id} has unchecked acceptance"
                    )

    return errors


def main(argv: list[str] | None = None) -> int:
    """Check plan.md or an explicitly supplied ledger path."""
    args = sys.argv[1:] if argv is None else argv
    path = Path(args[0]) if args else Path(__file__).resolve().parents[1] / "plan.md"
    try:
        errors = validate(path.read_text(encoding="utf-8"))
    except OSError as exception:
        print(f"unable to read execution ledger {path}: {exception}", file=sys.stderr)
        return 2

    for message in errors:
        print(f"{path}: {message}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
