#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""Lines of code per area across the project history, with CI coverage, as an SVG chart.

For every first-parent commit of ``main`` this script counts non-blank, non-comment lines
per area, reads the package version, and looks up the branch coverage that the GitHub
Actions CI run of that commit printed. Results are cached in
``docs/history/measurements.json`` (keyed by commit SHA); the chart is written to
``docs/history/loc-history.svg`` and the latest numbers to ``docs/history/loc-current.md``.

The working tree is never touched: trees are listed with ``git ls-tree -r -z`` and blobs
are read through one ``git cat-file --batch`` process. Stdlib only; output is
deterministic (no timestamps), so an unchanged history redraws byte-identically.

Coverage: the newest *successful* CI run of each commit is searched for pytest-cov's
"Total coverage: NN.NN%" line. Commits without such a run (e.g. cancelled by a newer
push) have no value; the coverage line connects their neighbours. Use ``--no-github`` to
work offline from the cache.

Release markers: every ``v*`` tag is a dashed red line; the first release of each minor
version and the latest release are labelled. ``--pending-release vX.Y.Z`` draws the
marker for a release whose tag does not exist yet at the newest commit (used by
``scripts/release.sh`` so the release commit already shows itself).

Usage:
    scripts/history_chart.py                       # measure new commits, fetch coverage, redraw
    scripts/history_chart.py --no-github           # offline: do not query GitHub Actions
    scripts/history_chart.py --no-measure          # redraw from the cache only
    scripts/history_chart.py --pending-release v0.6.0
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "docs" / "history"
AREAS: tuple[str, ...] = (
    "library",
    "tests-unit",
    "tests-contract",
    "tests-integration",
    "tests-e2e",
    "tooling",
    "docs",
)
COLORS = {
    "library": "#1f6feb",
    "tests-unit": "#1a7f37",
    "tests-contract": "#2da44e",
    "tests-integration": "#57ab5a",
    "tests-e2e": "#94d3a2",
    "tooling": "#cf222e",
    "docs": "#6e7781",
}
HASH_COMMENT = {".py", ".sh", ".toml", ".yml", ".yaml", ".cfg", ".ini", ""}
EXCLUDED_PREFIXES = ("tests/fixtures/", "benchmark/corpus/", "docs/history/", "docs/images/")
EXCLUDED_FILES = {"uv.lock", "vision.md", "LICENSE"}
COVERAGE_RE = re.compile(r"Total coverage: (\d+(?:\.\d+)?)%")
VERSION_RE = re.compile(r'^version = "([^"]+)"', re.MULTILINE)


def area_of(path: str) -> str | None:
    """Area of a repository path, or None when the file is not counted."""
    if path in EXCLUDED_FILES or path.startswith(EXCLUDED_PREFIXES):
        return None
    suffix = Path(path).suffix
    if path.startswith("src/") and suffix == ".py":
        return "library"
    if path.startswith("tests/") and suffix == ".py":
        layer = path.split("/")[1] if path.count("/") >= 2 else ""
        return {
            "contract": "tests-contract",
            "integration": "tests-integration",
            "e2e": "tests-e2e",
        }.get(layer, "tests-unit")
    if suffix == ".md":
        return "docs"
    if (
        path.startswith(("scripts/", ".github/"))
        or path in {"localPipeline.sh", "Dockerfile", "pyproject.toml", ".dockerignore"}
        or (path.startswith("src/") and suffix == ".toml")
    ):
        return "tooling"
    return None


def count_lines(path: str, content: bytes) -> int:
    """Non-blank lines; for code also drop comment-only lines (``#``)."""
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        return 0
    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    if Path(path).suffix in HASH_COMMENT and Path(path).suffix != ".md":
        lines = [line for line in lines if not line.startswith("#")]
    return len(lines)


def git(*args: str) -> str:
    """Run git in the repository and return stdout."""
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout


class BlobReader:
    """One long-running ``git cat-file --batch`` process."""

    def __init__(self) -> None:
        self.proc = subprocess.Popen(
            ["git", "cat-file", "--batch"],
            cwd=ROOT,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )

    def read(self, sha: str) -> bytes:
        """Content of one blob."""
        if self.proc.stdin is None or self.proc.stdout is None:  # pragma: no cover
            raise RuntimeError("git cat-file pipes are not open")
        self.proc.stdin.write(f"{sha}\n".encode())
        self.proc.stdin.flush()
        header = self.proc.stdout.readline().split()
        size = int(header[2])
        data = self.proc.stdout.read(size)
        self.proc.stdout.read(1)
        return data

    def close(self) -> None:
        """Stop the git process."""
        if self.proc.stdin is not None:
            self.proc.stdin.close()
        self.proc.wait()


def measure(commit: str, reader: BlobReader) -> dict[str, Any]:
    """Line counts per area plus version for one commit."""
    counts = dict.fromkeys(AREAS, 0)
    version = None
    for entry in git("ls-tree", "-r", "-z", commit).split("\0"):
        if not entry:
            continue
        meta, path = entry.split("\t", 1)
        _, kind, sha = meta.split()
        if kind != "blob":
            continue
        if path == "pyproject.toml":
            match = VERSION_RE.search(reader.read(sha).decode("utf-8"))
            version = match.group(1) if match else None
        area = area_of(path)
        if area is not None:
            counts[area] += count_lines(path, reader.read(sha))
    return {"loc": counts, "version": version}


def github_coverage(shas: Iterable[str]) -> dict[str, float]:
    """Coverage printed by the newest successful CI run of each wanted commit."""
    wanted = set(shas)
    if not wanted:
        return {}
    try:
        listing = subprocess.run(
            [
                "gh",
                "run",
                "list",
                "--workflow",
                "ci.yml",
                "--branch",
                "main",
                "-L",
                "1000",
                "--json",
                "databaseId,headSha,conclusion,createdAt",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"warning: cannot list GitHub runs ({exc}); keeping cached values", file=sys.stderr)
        return {}
    runs = sorted(json.loads(listing), key=lambda r: r["createdAt"], reverse=True)
    found: dict[str, float] = {}
    for run in runs:
        sha = run["headSha"]
        if sha not in wanted or sha in found or run["conclusion"] != "success":
            continue
        log = subprocess.run(
            ["gh", "run", "view", str(run["databaseId"]), "--log"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        ).stdout
        match = COVERAGE_RE.search(log)
        if match:
            found[sha] = float(match.group(1))
    return found


def releases() -> dict[str, str]:
    """``{commit sha: tag}`` for every ``v*`` tag."""
    tags: dict[str, str] = {}
    for line in git(
        "tag", "--list", "v*", "--format=%(refname:short) %(objectname) %(*objectname)"
    ).splitlines():
        name, obj, peeled = [*line.split(), ""][:3]
        tags[peeled or obj] = name
    return tags


def _version_key(tag: str) -> tuple[int, ...]:
    return tuple(int(part) for part in re.findall(r"\d+", tag))


def nice_ceiling(value: float) -> float:
    """Smallest "nice" number (1, 1.2, 1.5, 2, 2.5, 3, 4, 5, 6, 8 x 10^k) >= ``value``."""
    if value <= 0:
        return 1.0
    magnitude = 10 ** (len(str(int(value))) - 1)
    for factor in (1.0, 1.2, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0):
        if factor * magnitude >= value:
            return float(factor * magnitude)
    return float(10 * magnitude)  # pragma: no cover - loop always returns


def el(name: str, text: str = "", **attrs: object) -> str:
    """One SVG element; ``stroke_width`` becomes ``stroke-width``."""
    rendered = " ".join(
        f'{key.rstrip("_").replace("_", "-")}="{escape(str(value), {'"': "&quot;"})}"'
        for key, value in attrs.items()
    )
    return f"<{name} {rendered}>{text}</{name}>" if text else f"<{name} {rendered}/>"


class Frame:
    """Plot geometry: maps commit index / line count / coverage to SVG coordinates."""

    width, height = 960, 440
    left, right, top, bottom = 70, 70, 50, 85
    coverage_floor = 80.0

    def __init__(self, n: int, ymax: float) -> None:
        self.n = n
        self.ymax = ymax
        self.w = self.width - self.left - self.right
        self.h = self.height - self.top - self.bottom

    def x(self, i: int) -> float:
        """Horizontal position of commit ``i``."""
        return self.left + (self.w * i / (self.n - 1) if self.n > 1 else self.w / 2)

    def y(self, value: float) -> float:
        """Vertical position of a line count."""
        return self.top + self.h - self.h * value / self.ymax

    def ycov(self, value: float) -> float:
        """Vertical position of a coverage percentage (80-100 %)."""
        return self.top + self.h - self.h * (value - self.coverage_floor) / 20


def _axes(f: Frame) -> list[str]:
    out = []
    for k in range(6):
        value = f.ymax * k / 5
        out.append(
            el(
                "line",
                x1=f.left,
                x2=f.left + f.w,
                y1=f"{f.y(value):.1f}",
                y2=f"{f.y(value):.1f}",
                stroke="#d0d7de",
                stroke_width=0.5,
            )
        )
        out.append(
            el(
                "text",
                f"{int(value):,}",
                x=f.left - 6,
                y=f"{f.y(value) + 4:.1f}",
                text_anchor="end",
                fill="#57606a",
            )
        )
        cov = f.coverage_floor + 4 * k
        out.append(
            el("text", f"{cov:g}%", x=f.left + f.w + 6, y=f"{f.ycov(cov) + 4:.1f}", fill="#bf3989")
        )
    return out


def _areas(f: Frame, points: Sequence[dict[str, Any]]) -> list[str]:
    out = []
    base = [0.0] * f.n
    for area in AREAS:
        upper = [base[i] + points[i]["loc"][area] for i in range(f.n)]
        outline = [f"{f.x(i):.1f},{f.y(upper[i]):.1f}" for i in range(f.n)]
        outline += [f"{f.x(i):.1f},{f.y(base[i]):.1f}" for i in reversed(range(f.n))]
        out.append(
            el(
                "polygon",
                f"<title>{area}</title>",
                points=" ".join(outline),
                fill=COLORS[area],
                fill_opacity=0.85,
            )
        )
        base = upper
    return out


def _releases(
    f: Frame, points: Sequence[dict[str, Any]], tags: dict[str, str], pending: str | None
) -> list[str]:
    markers = [(i, tags[p["sha"]]) for i, p in enumerate(points) if p["sha"] in tags]
    if pending and pending not in {tag for _, tag in markers}:
        markers.append((f.n - 1, pending))
    if not markers:
        return []
    latest = max(markers, key=lambda m: _version_key(m[1]))[1]
    out: list[str] = []
    labels: list[tuple[float, str]] = []
    minors: set[tuple[int, ...]] = set()
    for i, tag in markers:
        out.append(
            el(
                "line",
                x1=f"{f.x(i):.1f}",
                x2=f"{f.x(i):.1f}",
                y1=f.top,
                y2=f.top + f.h,
                stroke="#cf222e",
                stroke_width=0.8,
                stroke_dasharray="4,3",
            )
        )
        minor = _version_key(tag)[:2]
        if minor in minors and tag != latest:
            continue
        minors.add(minor)
        if labels and f.x(i) - labels[-1][0] < 40:
            if tag != latest:
                continue
            labels.pop()  # the latest release always keeps its label
        labels.append((f.x(i), tag))
    out += [
        el("text", escape(tag), x=f"{lx + 3:.1f}", y=f.top + 12, fill="#cf222e")
        for lx, tag in labels
    ]
    return out


def _coverage(f: Frame, points: Sequence[dict[str, Any]]) -> list[str]:
    measured = [(i, p["coverage"]) for i, p in enumerate(points) if p.get("coverage") is not None]
    if not measured:
        return []
    line = " ".join(f"{f.x(i):.1f},{f.ycov(c):.1f}" for i, c in measured)
    out = [el("polyline", points=line, fill="none", stroke="#bf3989", stroke_width=2)]
    out += [
        el(
            "circle",
            f"<title>{c:.2f}% @ {points[i]['sha'][:7]}</title>",
            cx=f"{f.x(i):.1f}",
            cy=f"{f.ycov(c):.1f}",
            r=2.5,
            fill="#bf3989",
        )
        for i, c in measured
    ]
    return out


def _frame_and_legend(f: Frame) -> list[str]:
    out = [
        el("rect", x=f.left, y=f.top, width=f.w, height=f.h, fill="none", stroke="#57606a"),
        el(
            "text",
            f"commits on main (oldest → newest, {f.n} total)",
            x=f.left + f.w / 2,
            y=f.top + f.h + 18,
            text_anchor="middle",
            fill="#57606a",
        ),
        el(
            "text",
            "lines (non-blank, non-comment)",
            text_anchor="middle",
            fill="#57606a",
            transform=f"translate(16,{f.top + f.h / 2}) rotate(-90)",
        ),
        el(
            "text",
            "CI branch coverage",
            text_anchor="middle",
            fill="#bf3989",
            transform=f"translate({f.width - 14},{f.top + f.h / 2}) rotate(90)",
        ),
    ]
    for k, area in enumerate([*AREAS, "coverage"]):
        lx, ly = f.left + (k % 4) * 200, f.top + f.h + 40 + (k // 4) * 18
        out.append(
            el("rect", x=lx, y=ly - 9, width=12, height=10, fill=COLORS.get(area, "#bf3989"))
        )
        out.append(el("text", area, x=lx + 18, y=ly, fill="#24292f"))
    return out


def render_svg(points: Sequence[dict[str, Any]], tags: dict[str, str], pending: str | None) -> str:
    """Stacked area chart (lines per area) with a coverage line on the right axis."""
    f = Frame(len(points), nice_ceiling(max(sum(p["loc"].values()) for p in points) * 1.05))
    head = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{f.width}" height="{f.height}" '
        f'viewBox="0 0 {f.width} {f.height}" font-family="sans-serif" font-size="11">'
    )
    title = "TuringTongue — lines of code per area and CI coverage per commit"
    body = [
        head,
        el("rect", width=f.width, height=f.height, fill="#ffffff"),
        el("text", title, x=f.left, y=22, font_size=15, font_weight="bold", fill="#24292f"),
        *_axes(f),
        *_areas(f, points),
        *_releases(f, points, tags, pending),
        *_coverage(f, points),
        *_frame_and_legend(f),
        "</svg>",
    ]
    return "\n".join(body) + "\n"


def render_current(point: dict[str, Any]) -> str:
    """Markdown table for the newest commit."""
    loc = point["loc"]
    total = sum(loc.values())
    rows = [f"| {area} | {loc[area]:,} | {loc[area] / total:.0%} |" for area in AREAS]
    tests = sum(v for k, v in loc.items() if k.startswith("tests-"))
    coverage = point.get("coverage")
    shown = f"{coverage:.2f} %" if coverage is not None else "not available"
    return "\n".join(
        [
            "<!-- SPDX-License-Identifier: GPL-3.0-or-later -->",
            "# Lines of code — current",
            "",
            f"Commit `{point['sha'][:7]}`, version `{point.get('version')}`. Generated by",
            "[`scripts/history_chart.py`](../../scripts/history_chart.py); "
            "non-blank, non-comment lines.",
            "",
            "| Area | Lines | Share |",
            "| --- | ---: | ---: |",
            *rows,
            f"| **total** | **{total:,}** | |",
            "",
            f"- Test lines per library line: {tests / max(1, loc['library']):.2f}",
            f"- CI branch coverage of this commit: {shown}",
            "",
        ]
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--no-github", action="store_true", help="do not query GitHub Actions")
    parser.add_argument("--no-measure", action="store_true", help="redraw from the cache only")
    parser.add_argument("--pending-release", metavar="TAG", help="marker for an untagged release")
    parser.add_argument("--ref", default="main")
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    args = parser.parse_args(argv)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    cache_path = args.out_dir / "measurements.json"
    cache: dict[str, Any] = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    commits = git("rev-list", "--first-parent", "--reverse", args.ref).split()
    if not args.no_measure:
        reader = BlobReader()
        try:
            for sha in commits:
                if sha not in cache:
                    cache[sha] = measure(sha, reader)
        finally:
            reader.close()
        if not args.no_github:
            missing = [s for s in commits if cache.get(s, {}).get("coverage") is None]
            for sha, value in github_coverage(missing).items():
                cache[sha]["coverage"] = value
    points = [{"sha": sha, **cache[sha]} for sha in commits if sha in cache]
    if not points:
        print("nothing to draw", file=sys.stderr)
        return 1
    ordered = {sha: cache[sha] for sha in commits if sha in cache}
    cache_path.write_text(json.dumps(ordered, indent=1, sort_keys=False) + "\n", encoding="utf-8")
    (args.out_dir / "loc-history.svg").write_text(
        render_svg(points, releases(), args.pending_release), encoding="utf-8"
    )
    (args.out_dir / "loc-current.md").write_text(render_current(points[-1]), encoding="utf-8")
    print(f"{len(points)} commits drawn → {args.out_dir / 'loc-history.svg'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
