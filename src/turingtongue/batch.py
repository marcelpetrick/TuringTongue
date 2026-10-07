# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""Batch / corpus analysis of many files (vision §30), e.g. historical blog posts.

Files are checked one after another (no request bursts). Each row summarizes one
file; full per-file results can be written as JSONL.
"""

from __future__ import annotations

import csv
import json
import re
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path
from typing import Any, TextIO

from turingtongue.client import Checker, ProviderSelection
from turingtongue.errors import ConfigurationError
from turingtongue.models import CheckResult

DEFAULT_PATTERNS = ("*.txt", "*.md", "*.markdown")
CSV_COLUMNS = (
    "file",
    "date",
    "characters",
    "words",
    "verdict",
    "ensemble_evidence",
    "agreement",
    "providers_succeeded",
    "providers_failed",
    "wall_clock_ms",
    "credits_used",
    "model_versions",
)
_FRONT_MATTER_DATE = re.compile(r"^date:\s*[\"']?([^\"'\n]+)", re.MULTILINE)


def collect_files(
    paths: Sequence[str | Path], patterns: Sequence[str] = DEFAULT_PATTERNS
) -> list[Path]:
    """Expand files and directories (recursively, by pattern) into a sorted file list."""
    files: set[Path] = set()
    for item in paths:
        path = Path(item)
        if path.is_file():
            files.add(path)
        elif path.is_dir():
            for pattern in patterns:
                files.update(p for p in path.rglob(pattern) if p.is_file())
        else:
            raise ConfigurationError(f"not a file or directory: {path}")
    if not files:
        raise ConfigurationError("no input files found")
    return sorted(files)


def front_matter_date(text: str) -> str | None:
    """``date:`` from a leading YAML front-matter block, if present (read-only)."""
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    block = text[3:end] if end != -1 else ""
    match = _FRONT_MATTER_DATE.search(block)
    return match.group(1).strip() if match else None


def summarize(path: Path, text: str, result: CheckResult) -> dict[str, Any]:
    """One CSV/JSONL row for a file."""
    ok = [p for p in result.providers if p.error is None]
    credits = [p.cost.credits_used for p in ok if p.cost and p.cost.credits_used is not None]
    versions = [f"{p.provider_id}={p.model_version}" for p in result.providers if p.model_version]
    return {
        "file": str(path),
        "date": front_matter_date(text),
        "characters": result.input.characters,
        "words": result.input.words,
        "verdict": result.verdict.display,
        "ensemble_evidence": result.aggregate.evidence_score,
        "agreement": result.aggregate.agreement,
        "providers_succeeded": len(ok),
        "providers_failed": len(result.errors),
        "wall_clock_ms": round(result.timing.wall_clock_ms, 1),
        "credits_used": sum(credits) if credits else None,
        "model_versions": ";".join(versions),
    }


async def run_batch(
    checker: Checker,
    files: Iterable[Path],
    *,
    providers: ProviderSelection = None,
    transport: str = "any",
    on_result: Callable[[Path, dict[str, Any], CheckResult], None] | None = None,
) -> list[dict[str, Any]]:
    """Check files sequentially; unreadable/empty files become rows with an error verdict."""
    rows = []
    for path in files:
        try:
            text = path.read_bytes().decode("utf-8")
            result = await checker.acheck(text, providers=providers, transport=transport)
        except (UnicodeDecodeError, ConfigurationError) as exc:
            row = dict.fromkeys(CSV_COLUMNS)
            row.update(file=str(path), verdict="SKIPPED", model_versions=str(exc))
            rows.append(row)
            continue
        row = summarize(path, text, result)
        rows.append(row)
        if on_result is not None:
            on_result(path, row, result)
    return rows


def write_csv(rows: Iterable[dict[str, Any]], stream: TextIO) -> None:
    """Write rows with the documented column order."""
    writer = csv.DictWriter(stream, fieldnames=CSV_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)


def jsonl_line(path: Path, row: dict[str, Any], result: CheckResult) -> str:
    """Full JSONL record: summary row plus the complete versioned result."""
    return json.dumps({"summary": row, "result": result.to_dict()}, ensure_ascii=False)
