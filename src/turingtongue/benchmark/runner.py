# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""Run a corpus through the checker, one sample at a time (no request bursts).

Results are appended to a new timestamped JSONL file and never overwrite earlier
runs: a provider's answer changing over time is an observation, not a bug.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from turingtongue.benchmark.corpus import Sample
from turingtongue.client import Checker, ProviderSelection


async def run_samples(
    checker: Checker,
    samples: Sequence[Sample],
    *,
    providers: ProviderSelection = None,
    transport: str = "any",
    progress: Callable[[int, int, Sample], None] | None = None,
) -> list[dict[str, Any]]:
    """Check every sample sequentially and return one record per sample."""
    records = []
    for index, sample in enumerate(samples, start=1):
        if progress is not None:
            progress(index, len(samples), sample)
        result = await checker.acheck(sample.text, providers=providers, transport=transport)
        records.append(
            {
                "sample_id": sample.id,
                "label": sample.label,
                "truth": sample.truth.value if sample.truth else None,
                "split": sample.split,
                "language": sample.metadata.get("language"),
                "words": result.input.words,
                "result": result.to_dict(),
            }
        )
    return records


def write_records(records: Iterable[dict[str, Any]], out_dir: str | Path) -> Path:
    """Write records to ``results-<UTC timestamp>.jsonl`` in ``out_dir`` (never overwrites)."""
    directory = Path(out_dir)
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    path = directory / f"results-{stamp}.jsonl"
    with path.open("x", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return path


def read_records(path: str | Path) -> list[dict[str, Any]]:
    """Load records written by :func:`write_records`."""
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]
