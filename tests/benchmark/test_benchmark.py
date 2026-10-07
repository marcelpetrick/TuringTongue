# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from turingtongue import Checker, ConfigurationError, Settings, Verdict
from turingtongue.benchmark import corpus, metrics, report, runner

pytestmark = pytest.mark.unit
REPO_CORPUS = Path(__file__).parents[2] / "benchmark" / "corpus"


def test_repository_corpus_is_consistent() -> None:
    samples = corpus.load_corpus(REPO_CORPUS)
    labels = {s.label for s in samples}
    assert {"HUMAN_RAW", "AI_RAW", "MIXED"} <= labels
    assert sum(s.truth is Verdict.HUMAN for s in samples) >= 5
    assert sum(s.truth is Verdict.AI for s in samples) >= 5
    families = {s.metadata["model_family"] for s in samples if s.label == "AI_RAW"}
    assert len(families) >= 3
    for s in samples:
        if s.label == "AI_RAW":
            assert {"model", "tool", "prompt_sha256", "created", "human_edits"} <= s.metadata.keys()
            assert (
                hashlib.sha256(s.metadata["prompt"].encode()).hexdigest()
                == s.metadata["prompt_sha256"]
            )
        if s.label == "HUMAN_RAW":
            assert {"source_url", "license", "published"} <= s.metadata.keys()
    holdout = corpus.load_corpus(REPO_CORPUS, split="holdout")
    assert 0 < len(holdout) < len(samples)


def _mini_corpus(tmp_path: Path, manifest_extra: str = "", content: str = "Hello world.") -> Path:
    (tmp_path / "a.txt").write_text(content, encoding="utf-8")
    digest = hashlib.sha256(content.encode()).hexdigest()
    (tmp_path / "manifest.toml").write_text(
        f'[[samples]]\nid = "a"\nlabel = "HUMAN_RAW"\nfile = "a.txt"\nsha256 = "{digest}"\n'
        f'split = "holdout"\n{manifest_extra}',
        encoding="utf-8",
    )
    return tmp_path


@pytest.mark.parametrize(
    ("extra", "message"),
    [
        ('[[samples]]\nid = "a"\nlabel = "HUMAN_RAW"\nfile = "a.txt"\n', "duplicate"),
        ('[[samples]]\nid = "b"\nlabel = "WEIRD"\nfile = "a.txt"\n', "unknown label"),
        ('[[samples]]\nid = "c"\nlabel = "AI_RAW"\nfile = "a.txt"\nsplit = "x"\n', "unknown split"),
        ('[[samples]]\nid = "d"\nlabel = "AI_RAW"\nfile = "a.txt"\nsha256 = "00"\n', "SHA-256"),
    ],
)
def test_corpus_validation(tmp_path: Path, extra: str, message: str) -> None:
    with pytest.raises(ConfigurationError, match=message):
        corpus.load_corpus(_mini_corpus(tmp_path, extra))


def test_corpus_misc_errors(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match="cannot read"):
        corpus.load_corpus(tmp_path)
    root = _mini_corpus(tmp_path)
    with pytest.raises(ConfigurationError, match="unknown split"):
        corpus.load_corpus(root, split="train")
    with pytest.raises(ConfigurationError, match="no samples"):
        corpus.load_corpus(root, split="calibration")


async def test_runner_roundtrip(tmp_path: Path) -> None:
    samples = corpus.load_corpus(_mini_corpus(tmp_path))
    seen: list[str] = []
    records = await runner.run_samples(
        Checker(Settings(env={})),
        samples,
        providers=["mock"],
        progress=lambda i, n, s: seen.append(s.id),
    )
    assert seen == ["a"]
    assert records[0]["truth"] == "human"
    path = runner.write_records(records, tmp_path / "out")
    second = runner.write_records(records, tmp_path / "out")
    assert path != second
    assert runner.read_records(path) == json.loads(json.dumps(records))


def _record(
    truth: str | None, verdict: str, evidence: float | None, providers: list[dict[str, Any]]
) -> dict[str, Any]:
    return {
        "truth": truth,
        "words": 100,
        "result": {
            "verdict": verdict,
            "aggregate": {"evidence_score": evidence, "weights_version": "v0"},
            "timing": {"wall_clock_ms": 10.0},
            "providers": providers,
        },
    }


def _p(
    pid: str, ev: float | None, status: str = "ok", credits: float | None = None
) -> dict[str, Any]:
    return {
        "provider_id": pid,
        "status": status,
        "normalized_evidence": ev,
        "latency_ms": 5.0,
        "cost": {"credits_used": credits} if credits is not None else None,
        "model": "m",
        "model_version": "1",
    }


def test_metrics() -> None:
    records = [
        _record("ai", "ai", 0.8, [_p("x", 0.8, credits=10), _p("y", None, "failed")]),
        _record("ai", "no_verdict", 0.0, [_p("x", 0.01), _p("y", -0.5)]),
        _record("human", "human", -0.7, [_p("x", -0.7), _p("y", 0.6)]),
        _record("human", "ai", 0.3, [_p("x", 0.3), _p("y", -0.9)]),
        _record(None, "ai", 0.9, [_p("x", 0.9)]),
    ]
    ensemble, x, y = metrics.compute(records)
    assert (ensemble.name, ensemble.samples) == ("ensemble", 4)
    assert (ensemble.tp, ensemble.fn, ensemble.tn, ensemble.fp, ensemble.abstained) == (
        1,
        0,
        1,
        1,
        1,
    )
    assert ensemble.accuracy == pytest.approx(2 / 3)
    assert ensemble.false_positive_rate == 0.5
    assert ensemble.roc_auc == pytest.approx(0.75)
    assert ensemble.latency_ms["p50"] == 10.0
    assert ensemble.latency_ms["p99"] is None
    assert x.abstained == 1
    assert x.credits_per_sample == 10
    assert x.credits_per_1000_words == 100
    assert x.model_versions == ["m 1"]
    assert y.failed == 1
    assert y.failure_rate == 0.25
    assert y.f1 is None


def test_metric_helpers() -> None:
    assert metrics.roc_auc([], [1.0]) is None
    assert metrics.roc_auc([0.5], [0.5]) == 0.5
    assert metrics.percentile([3.0, 1.0, 2.0], 50) == 2.0
    assert metrics.percentile(list(map(float, range(10))), 90) == 8.0


def test_report_rendering() -> None:
    scores = metrics.compute([_record("ai", "ai", 0.8, [_p("x", 0.8)])])
    meta = {"generated": "now", "samples": 1}
    markdown = report.to_markdown(scores, meta=meta)
    assert "| ensemble | 1 | 100% |" in markdown
    assert "not accuracy claims" in markdown
    assert json.loads(report.to_json(scores, meta=meta))["scores"][1]["name"] == "x"


def test_copy_of_repo_corpus_detects_tampering(tmp_path: Path) -> None:
    shutil.copytree(REPO_CORPUS, tmp_path / "c")
    (tmp_path / "c" / "human" / "walden.txt").write_text("tampered", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="SHA-256"):
        corpus.load_corpus(tmp_path / "c")
