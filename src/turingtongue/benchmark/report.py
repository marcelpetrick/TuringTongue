# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""Render benchmark metrics as Markdown (for humans) and JSON (for diffing runs)."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from turingtongue.benchmark.metrics import Scores

CAVEAT = (
    "Small, non-representative corpus: these numbers are smoke tests of the pipeline and "
    "rough provider comparisons, not accuracy claims. Brier/calibration metrics are not "
    "computed because no score has a defensible probability interpretation."
)


def _f(value: float | None, pct: bool = False) -> str:
    if value is None:
        return "—"
    return f"{value:.0%}" if pct else f"{value:.2f}"


def to_markdown(scores: Sequence[Scores], *, meta: dict[str, Any]) -> str:
    """Markdown report with a summary table and confusion matrices."""
    lines = [
        "# Benchmark report",
        "",
        f"- Generated: {meta.get('generated', '—')}",
        f"- Package version: {meta.get('package_version', '—')}",
        f"- Corpus samples: {meta.get('samples', '—')} (binary-truth samples are scored)",
        f"- Weights: {meta.get('weights_version', '—')}",
        "",
        f"> {CAVEAT}",
        "",
        "| Name | n | Acc | Bal. acc | Precision | Recall | Specificity | FPR | FNR | F1 "
        "| Abstain | Fail | ROC-AUC | p50 ms | mean ms | credits/1k words |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: "
        "| ---: | ---: | ---: | ---: |",
    ]
    for s in scores:
        lines.append(
            f"| {s.name} | {s.samples} | {_f(s.accuracy, True)} | {_f(s.balanced_accuracy, True)} "
            f"| {_f(s.precision, True)} | {_f(s.recall, True)} | {_f(s.specificity, True)} "
            f"| {_f(s.false_positive_rate, True)} | {_f(s.false_negative_rate, True)} "
            f"| {_f(s.f1)} | {_f(s.abstention_rate, True)} | {_f(s.failure_rate, True)} "
            f"| {_f(s.roc_auc)} | {_f(s.latency_ms.get('p50'))} | {_f(s.latency_ms.get('mean'))} "
            f"| {_f(s.credits_per_1000_words)} |"
        )
    lines += ["", "## Confusion matrices (rows = truth, columns = prediction)", ""]
    for s in scores:
        versions = ", ".join(s.model_versions) or "—"
        lines += [
            f"### {s.name}",
            "",
            f"Model/version seen: {versions}",
            "",
            "| | predicted AI | predicted HUMAN |",
            "| --- | ---: | ---: |",
            f"| truth AI | {s.tp} | {s.fn} |",
            f"| truth HUMAN | {s.fp} | {s.tn} |",
            "",
            f"Abstained: {s.abstained} · failed: {s.failed}",
            "",
        ]
    return "\n".join(lines)


def to_json(scores: Sequence[Scores], *, meta: dict[str, Any]) -> str:
    """JSON report (stable keys) for machine comparison of runs."""
    return json.dumps(
        {"meta": meta, "caveat": CAVEAT, "scores": [s.as_dict() for s in scores]}, indent=2
    )
