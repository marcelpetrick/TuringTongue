# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""Benchmark metrics per provider and for the ensemble (vision §10.5).

* Only samples with binary ground truth (HUMAN/AI) enter classification metrics.
* A provider "abstains" when its evidence is within ±0.05 or it failed; the ensemble
  abstains with NO_VERDICT. Abstentions are reported, not counted as errors.
* ROC-AUC is rank-based on the evidence score (valid for any monotonic score).
* Brier/calibration metrics are deliberately NOT computed: no provider score here
  has a defensible probability interpretation.
* Latency percentiles are only reported when there are enough observations.
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass, field
from typing import Any

ENSEMBLE = "ensemble"
NEUTRAL = 0.05
PERCENTILE_MIN_SAMPLES = {50: 2, 90: 10, 95: 20, 99: 100}


@dataclass(slots=True)
class Scores:
    """Metrics for one provider (or the ensemble)."""

    name: str
    samples: int = 0
    tp: int = 0
    fp: int = 0
    tn: int = 0
    fn: int = 0
    abstained: int = 0
    failed: int = 0
    accuracy: float | None = None
    balanced_accuracy: float | None = None
    precision: float | None = None
    recall: float | None = None
    specificity: float | None = None
    false_positive_rate: float | None = None
    false_negative_rate: float | None = None
    f1: float | None = None
    abstention_rate: float | None = None
    coverage: float | None = None
    failure_rate: float | None = None
    roc_auc: float | None = None
    latency_ms: dict[str, float | None] = field(default_factory=dict)
    credits_per_sample: float | None = None
    credits_per_1000_words: float | None = None
    model_versions: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        """Plain data for JSON reports."""
        return asdict(self)


def _ratio(numerator: float, denominator: float) -> float | None:
    return numerator / denominator if denominator else None


def percentile(values: Sequence[float], pct: int) -> float | None:
    """Nearest-rank percentile; None when there are too few values to be meaningful."""
    if len(values) < PERCENTILE_MIN_SAMPLES.get(pct, 1):
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(pct / 100 * len(ordered)))
    return ordered[rank - 1]


def roc_auc(positives: Sequence[float], negatives: Sequence[float]) -> float | None:
    """Mann-Whitney AUC: P(score_AI > score_HUMAN), ties count half."""
    if not positives or not negatives:
        return None
    wins = 0.0
    for p in positives:
        for n in negatives:
            wins += 1.0 if p > n else 0.5 if p == n else 0.0
    return wins / (len(positives) * len(negatives))


def _finish(
    s: Scores,
    latencies: list[float],
    auc_pos: list[float],
    auc_neg: list[float],
    credits: list[float],
    words: int,
) -> Scores:
    decided = s.tp + s.fp + s.tn + s.fn
    s.accuracy = _ratio(s.tp + s.tn, decided)
    s.precision = _ratio(s.tp, s.tp + s.fp)
    s.recall = _ratio(s.tp, s.tp + s.fn)
    s.specificity = _ratio(s.tn, s.tn + s.fp)
    s.false_positive_rate = _ratio(s.fp, s.fp + s.tn)
    s.false_negative_rate = _ratio(s.fn, s.fn + s.tp)
    if s.recall is not None and s.specificity is not None:
        s.balanced_accuracy = (s.recall + s.specificity) / 2
    if s.precision and s.recall:
        s.f1 = 2 * s.precision * s.recall / (s.precision + s.recall)
    s.abstention_rate = _ratio(s.abstained, s.samples)
    s.coverage = _ratio(decided, s.samples)
    s.failure_rate = _ratio(s.failed, s.samples)
    s.roc_auc = roc_auc(auc_pos, auc_neg)
    s.latency_ms = {
        "mean": statistics.fmean(latencies) if latencies else None,
        **{f"p{p}": percentile(latencies, p) for p in PERCENTILE_MIN_SAMPLES},
    }
    if credits:
        s.credits_per_sample = sum(credits) / len(credits)
        s.credits_per_1000_words = sum(credits) / words * 1000 if words else None
    return s


def _tally(s: Scores, truth: str, predicted: str | None) -> None:
    if predicted is None:
        s.abstained += 1
    elif predicted == "ai":
        if truth == "ai":
            s.tp += 1
        else:
            s.fp += 1
    elif truth == "human":
        s.tn += 1
    else:
        s.fn += 1


def compute(records: Iterable[dict[str, Any]]) -> list[Scores]:
    """Metrics for the ensemble and every provider seen in ``records``."""
    binary = [r for r in records if r.get("truth") in {"ai", "human"}]
    ensemble = Scores(ENSEMBLE)
    providers: dict[str, Scores] = {}
    lat: dict[str, list[float]] = {ENSEMBLE: []}
    pos: dict[str, list[float]] = {ENSEMBLE: []}
    neg: dict[str, list[float]] = {ENSEMBLE: []}
    cred: dict[str, list[float]] = {ENSEMBLE: []}
    words: dict[str, int] = {ENSEMBLE: 0}
    for record in binary:
        truth = record["truth"]
        result = record["result"]
        ensemble.samples += 1
        verdict = result["verdict"]
        _tally(ensemble, truth, None if verdict == "no_verdict" else verdict)
        lat[ENSEMBLE].append(result["timing"]["wall_clock_ms"])
        evidence = result["aggregate"]["evidence_score"]
        if evidence is not None:
            (pos if truth == "ai" else neg)[ENSEMBLE].append(evidence)
        for p in result["providers"]:
            pid = p["provider_id"]
            s = providers.setdefault(pid, Scores(pid))
            for bucket in (lat, pos, neg, cred):
                bucket.setdefault(pid, [])
            words.setdefault(pid, 0)
            s.samples += 1
            ev = p["normalized_evidence"]
            if p["status"] != "ok" or ev is None:
                s.failed += p["status"] != "ok"
                s.abstained += 1
                continue
            _tally(s, truth, None if abs(ev) <= NEUTRAL else ("ai" if ev > 0 else "human"))
            (pos if truth == "ai" else neg)[pid].append(ev)
            if p["latency_ms"] is not None:
                lat[pid].append(p["latency_ms"])
            used = (p.get("cost") or {}).get("credits_used")
            if used is not None:
                cred[pid].append(used)
                words[pid] += record["words"]
            version = " ".join(x for x in (p.get("model"), p.get("model_version")) if x)
            if version and version not in s.model_versions:
                s.model_versions.append(version)
    results = [_finish(ensemble, lat[ENSEMBLE], pos[ENSEMBLE], neg[ENSEMBLE], [], 0)]
    for pid, s in sorted(providers.items()):
        results.append(_finish(s, lat[pid], pos[pid], neg[pid], cred[pid], words[pid]))
    return results
