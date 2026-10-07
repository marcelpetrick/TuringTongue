# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from scripts import history_chart as hc

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("path", "area"),
    [
        ("src/turingtongue/client.py", "library"),
        ("src/turingtongue/data/providers.toml", "tooling"),
        ("tests/unit/test_x.py", "tests-unit"),
        ("tests/benchmark/test_b.py", "tests-unit"),
        ("tests/conftest.py", "tests-unit"),
        ("tests/contract/test_s.py", "tests-contract"),
        ("tests/integration/test_c.py", "tests-integration"),
        ("tests/e2e/test_cli.py", "tests-e2e"),
        ("tests/fixtures/sapling/ok.json", None),
        ("scripts/commit.sh", "tooling"),
        (".github/workflows/ci.yml", "tooling"),
        ("localPipeline.sh", "tooling"),
        ("Dockerfile", "tooling"),
        ("README.md", "docs"),
        ("docs/adr/0001.md", "docs"),
        ("vision.md", None),
        ("uv.lock", None),
        ("benchmark/corpus/human/walden.txt", None),
        ("docs/history/loc-current.md", None),
        ("docs/images/x.png", None),
    ],
)
def test_area_of(path: str, area: str | None) -> None:
    assert hc.area_of(path) == area


def test_count_lines() -> None:
    code = b"# SPDX\n\nimport x  # trailing\n   # indented comment\nx = 1\n"
    assert hc.count_lines("a.py", code) == 2
    assert hc.count_lines("a.md", b"# Heading\n\ntext\n") == 2
    assert hc.count_lines("a.py", b"\xff\xfe") == 0


@pytest.mark.parametrize(
    ("value", "nice"), [(0, 1), (9327, 10000), (8100, 10000), (1050, 1200), (7, 8), (3.2, 4)]
)
def test_nice_ceiling(value: float, nice: float) -> None:
    assert hc.nice_ceiling(value) == nice


def test_el_escapes_and_dashes() -> None:
    assert (
        hc.el("text", "a", font_size=3, fill='x"y')
        == '<text font-size="3" fill="x&quot;y">a</text>'
    )
    assert hc.el("rect", width=1) == '<rect width="1"/>'


def _points() -> list[dict[str, Any]]:
    loc = dict.fromkeys(hc.AREAS, 10)
    return [
        {"sha": "a" * 40, "loc": loc, "version": "0.1.0", "coverage": 97.5},
        {"sha": "b" * 40, "loc": {**loc, "library": 50}, "version": "0.1.1", "coverage": None},
        {"sha": "c" * 40, "loc": {**loc, "library": 80}, "version": "0.2.0", "coverage": 98.25},
    ]


def test_render_svg_and_markers() -> None:
    svg = hc.render_svg(_points(), {"a" * 40: "v0.1.0", "b" * 40: "v0.1.1"}, "v0.2.0")
    assert svg.startswith("<svg")
    assert svg.endswith("</svg>\n")
    assert svg.count('stroke-dasharray="4,3"') == 3
    assert ">v0.1.0<" in svg
    assert ">v0.2.0<" in svg
    assert ">v0.1.1<" not in svg  # not the first of its minor, not the latest
    assert "98.25% @ ccccccc" in svg
    assert svg.count("<polygon") == len(hc.AREAS)
    single = hc.render_svg(_points()[:1], {}, None)
    assert "<polyline" in single


def test_render_svg_without_coverage_or_releases() -> None:
    points = [{**p, "coverage": None} for p in _points()]
    svg = hc.render_svg(points, {}, None)
    assert "<polyline" not in svg
    assert "stroke-dasharray" not in svg


def test_render_current() -> None:
    text = hc.render_current(_points()[-1])
    assert "| library | 80 |" in text
    assert "98.25 %" in text
    assert "not available" in hc.render_current(_points()[1])


def test_measure_head_and_releases() -> None:
    head = hc.git("rev-parse", "HEAD").strip()
    reader = hc.BlobReader()
    try:
        measured = hc.measure(head, reader)
    finally:
        reader.close()
    assert measured["loc"]["library"] > 1000
    assert measured["version"]
    assert all(tag.startswith("v") for tag in hc.releases().values())


def test_github_coverage(monkeypatch: pytest.MonkeyPatch) -> None:
    runs = [
        {"databaseId": 1, "headSha": "s1", "conclusion": "success", "createdAt": "2026-01-02"},
        {"databaseId": 2, "headSha": "s1", "conclusion": "success", "createdAt": "2026-01-01"},
        {"databaseId": 3, "headSha": "s2", "conclusion": "cancelled", "createdAt": "2026-01-01"},
        {"databaseId": 4, "headSha": "s3", "conclusion": "success", "createdAt": "2026-01-01"},
        {"databaseId": 5, "headSha": "other", "conclusion": "success", "createdAt": "2026-01-01"},
    ]
    logs = {"1": "x Total coverage: 98.30%", "4": "no coverage line"}
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        calls.append(cmd)
        out = json.dumps(runs) if cmd[2] == "list" else logs.get(cmd[3], "")
        return subprocess.CompletedProcess(cmd, 0, out, "")

    monkeypatch.setattr("scripts.history_chart.subprocess.run", fake_run)
    assert hc.github_coverage(["s1", "s2", "s3"]) == {"s1": 98.3}
    assert hc.github_coverage([]) == {}
    assert sum(1 for c in calls if c[2] == "view") == 2


def test_github_coverage_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(*_: object, **__: object) -> None:
        raise OSError("no gh")

    monkeypatch.setattr("scripts.history_chart.subprocess.run", broken)
    assert hc.github_coverage(["s1"]) == {}


def test_main_from_cache(tmp_path: Path) -> None:
    head = hc.git("rev-parse", "HEAD").strip()
    cache = {head: {"loc": dict.fromkeys(hc.AREAS, 5), "version": "9.9.9", "coverage": 99.0}}
    (tmp_path / "measurements.json").write_text(json.dumps(cache))
    args = ["--no-measure", "--ref", "HEAD", "--out-dir", str(tmp_path)]
    assert hc.main([*args, "--pending-release", "v9.9.9"]) == 0
    assert ">v9.9.9<" in (tmp_path / "loc-history.svg").read_text()
    assert "9.9.9" in (tmp_path / "loc-current.md").read_text()
    assert hc.main(["--no-measure", "--ref", "HEAD", "--out-dir", str(tmp_path / "empty")]) == 1
