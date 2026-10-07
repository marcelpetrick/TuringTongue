# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""Load the benchmark corpus described by ``manifest.toml`` and verify every file."""

from __future__ import annotations

import hashlib
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from turingtongue.errors import ConfigurationError
from turingtongue.models import Verdict

LABEL_TRUTH: dict[str, Verdict | None] = {
    "HUMAN_RAW": Verdict.HUMAN,
    "HUMAN_GRAMMAR_CHECKED": Verdict.HUMAN,
    "AI_RAW": Verdict.AI,
    "AI_HUMAN_EDITED": Verdict.AI,
    "HUMAN_AI_ASSISTED": None,
    "MIXED": None,
}
"""Binary ground truth per label; mixed categories are excluded from binary metrics."""

SPLITS = ("calibration", "holdout")


@dataclass(frozen=True, slots=True)
class Sample:
    """One corpus text with its provenance."""

    id: str
    label: str
    text: str
    split: str
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def truth(self) -> Verdict | None:
        """Binary ground truth (None for mixed/assisted samples)."""
        return LABEL_TRUTH[self.label]


def load_corpus(directory: str | Path, *, split: str | None = None) -> list[Sample]:
    """Read ``manifest.toml`` in ``directory``; verify labels, splits and SHA-256."""
    root = Path(directory)
    manifest = root / "manifest.toml"
    try:
        data = tomllib.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ConfigurationError(f"cannot read corpus manifest {manifest}: {exc}") from exc
    if split not in (None, *SPLITS):
        raise ConfigurationError(f"unknown split '{split}' (use {', '.join(SPLITS)})")
    samples: list[Sample] = []
    seen: set[str] = set()
    for raw in data.get("samples", []):
        sample_id = str(raw["id"])
        if sample_id in seen:
            raise ConfigurationError(f"duplicate sample id {sample_id}")
        seen.add(sample_id)
        label = str(raw["label"])
        if label not in LABEL_TRUTH:
            raise ConfigurationError(f"{sample_id}: unknown label {label}")
        sample_split = str(raw.get("split", "holdout"))
        if sample_split not in SPLITS:
            raise ConfigurationError(f"{sample_id}: unknown split {sample_split}")
        path = root / str(raw["file"])
        content = path.read_bytes()
        if hashlib.sha256(content).hexdigest() != raw.get("sha256"):
            raise ConfigurationError(f"{sample_id}: SHA-256 mismatch for {path} (file changed?)")
        if split is not None and sample_split != split:
            continue
        metadata = {k: v for k, v in raw.items() if k not in {"id", "label", "split"}}
        samples.append(Sample(sample_id, label, content.decode("utf-8"), sample_split, metadata))
    if not samples:
        raise ConfigurationError(f"no samples selected from {manifest}")
    return samples
