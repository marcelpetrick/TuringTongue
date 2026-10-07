#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""Collect code metrics and write ``docs/metrics.md``.

Usage: scripts/metrics.py [--out docs/metrics.md] [--no-coverage]

Measures, from the working tree:

* lines of code per area (cloc: code / comment / blank) — library, tests, fixtures,
  scripts, CI, docs — and test-to-code ratios;
* library structure (modules, classes, functions) and cyclomatic complexity (radon via
  ``uvx``; skipped when unavailable);
* number of tests per tier (pytest markers);
* branch coverage per tier **and** combined, using coverage.py with subprocess
  patching so the end-to-end tier (which runs ``python -m turingtongue`` in child
  processes) is measured too.

Needs ``cloc`` on PATH. Coverage runs use a private rc file and temp data files, so the
regular pipeline coverage settings are untouched.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TIERS = ("unit", "contract", "integration", "e2e")
AREAS: dict[str, list[str]] = {
    "Library (src/turingtongue)": ["src/turingtongue"],
    "Tests (Python)": ["tests"],
    "Test fixtures (JSON)": ["tests/fixtures"],
    "Helper scripts + pipeline": ["scripts", "localPipeline.sh"],
    "CI / container": [".github", "Dockerfile"],
    "Documentation (Markdown)": [
        "docs",
        "README.md",
        "AGENTS.md",
        "IMPLEMENTATION_REPORT.md",
        "scripts/README.md",
        "benchmark/corpus/README.md",
    ],
}
COVERAGE_RC = """
[run]
branch = True
source = turingtongue
parallel = True
patch = subprocess
data_file = {data}

[report]
exclude_also =
    if TYPE_CHECKING:
    raise NotImplementedError
    @overload
"""


def run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
    """Run a command in the repo root and capture text output."""
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=False, **kwargs)


def cloc(paths: list[str], *, include: str | None = None) -> dict[str, int]:
    """Totals (files, blank, comment, code) for the given paths via cloc."""
    cmd = ["cloc", "--json", "--quiet", "--exclude-dir=__pycache__,fixtures,images"]
    if include:
        cmd.append(f"--include-lang={include}")
    if paths == ["tests/fixtures"]:
        cmd = ["cloc", "--json", "--quiet", "--include-lang=JSON"]
    out = run([*cmd, *paths]).stdout
    total = json.loads(out).get("SUM", {}) if out.strip() else {}
    return {k: int(total.get(k, 0)) for k in ("nFiles", "blank", "comment", "code")}


def structure() -> dict[str, int]:
    """Count library modules, classes, functions and public functions with AST."""
    counts = {"modules": 0, "classes": 0, "functions": 0, "docstrings": 0, "documentable": 0}
    for path in sorted((ROOT / "src" / "turingtongue").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        counts["modules"] += 1
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                counts["classes"] += 1
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                counts["functions"] += 1
            if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
                if isinstance(node, ast.Module) and not tree.body:
                    continue
                counts["documentable"] += 1
                counts["docstrings"] += ast.get_docstring(node) is not None
    return counts


def complexity() -> dict[str, Any] | None:
    """Cyclomatic complexity summary via radon (None when uvx/radon is unavailable)."""
    if shutil.which("uvx") is None:
        return None
    done = run(["uvx", "--quiet", "radon", "cc", "-j", "src/turingtongue"])
    if done.returncode != 0 or not done.stdout.strip():
        return None
    blocks = [
        b for items in json.loads(done.stdout).values() if isinstance(items, list) for b in items
    ]
    scores = sorted(
        (
            b["complexity"],
            f"{b.get('classname', '') + '.' if b.get('classname') else ''}{b['name']}",
        )
        for b in blocks
    )
    grades: dict[str, int] = {}
    for b in blocks:
        grades[b["rank"]] = grades.get(b["rank"], 0) + 1
    mi = run(["uvx", "--quiet", "radon", "mi", "-j", "src/turingtongue"])
    mi_values = [v["mi"] for v in json.loads(mi.stdout).values()] if mi.returncode == 0 else []
    return {
        "blocks": len(scores),
        "average": sum(s for s, _ in scores) / len(scores),
        "max": scores[-1],
        "top": scores[-5:][::-1],
        "grades": dict(sorted(grades.items())),
        "mi_min": min(mi_values) if mi_values else None,
        "mi_avg": sum(mi_values) / len(mi_values) if mi_values else None,
    }


def test_counts() -> dict[str, int]:
    """Number of collected tests per marker tier (plus the opt-in ones)."""
    counts = {}
    for tier in (*TIERS, "network or paid or browser"):
        out = (
            run(
                [sys.executable, "-m", "pytest", "--co", "-q", "-p", "no:cacheprovider", "-m", tier]
            )
            .stdout.strip()
            .splitlines()
        )
        last = out[-1] if out else ""
        counts[tier] = int(last.split("/")[0].split()[0]) if last and last[0].isdigit() else 0
    return counts


def coverage_for(marker: str | None, rc: Path, data: Path) -> dict[str, Any]:
    """Branch coverage of the library when only ``marker`` tests run (None = all)."""
    for stale in data.parent.glob(data.name + "*"):
        stale.unlink()
    env = {**os.environ, "COVERAGE_RCFILE": str(rc)}
    select = ["-m", marker] if marker else []
    run(
        [
            sys.executable,
            "-m",
            "coverage",
            "run",
            f"--rcfile={rc}",
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            *select,
        ],
        env=env,
    )
    run([sys.executable, "-m", "coverage", "combine", f"--rcfile={rc}"], env=env)
    report = run([sys.executable, "-m", "coverage", "json", f"--rcfile={rc}", "-o", "-"], env=env)
    totals = json.loads(report.stdout)["totals"]
    return {
        "percent": totals["percent_covered"],
        "statements": totals["num_statements"],
        "covered_lines": totals["covered_lines"],
        "branches": totals["num_branches"],
        "covered_branches": totals["covered_branches"],
    }


def coverage_matrix() -> dict[str, dict[str, Any]]:
    """Coverage per tier and combined, in a private temp directory."""
    with tempfile.TemporaryDirectory() as tmp:
        data = Path(tmp) / ".coverage"
        rc = Path(tmp) / "coveragerc"
        rc.write_text(COVERAGE_RC.format(data=data), encoding="utf-8")
        results = {tier: coverage_for(tier, rc, data) for tier in TIERS}
        results["all (combined)"] = coverage_for(None, rc, data)
    return results


def render(metrics: dict[str, Any]) -> str:
    """Markdown document."""
    loc = metrics["loc"]
    lib = loc["Library (src/turingtongue)"]["code"]
    tests = loc["Tests (Python)"]["code"]
    lines = [
        "<!-- SPDX-License-Identifier: GPL-3.0-or-later -->",
        "# Project metrics",
        "",
        f"Generated {metrics['generated']} for version `{metrics['version']}` at commit "
        f"`{metrics['commit']}` by [`scripts/metrics.py`](../scripts/metrics.py) — regenerate with",
        "`uv run python scripts/metrics.py`. Counting tool: cloc "
        "(code lines exclude blanks and comments).",
        "",
        "## Lines of code",
        "",
        "| Area | Files | Code | Comment | Blank |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for area, c in loc.items():
        lines.append(
            f"| {area} | {c['nFiles']} | {c['code']:,} | {c['comment']:,} | {c['blank']:,} |"
        )
    s = metrics["structure"]
    lines += [
        "",
        f"- **Test-to-code ratio:** {tests / lib:.2f} lines of test code per line of library code "
        f"({tests:,} : {lib:,}); fixtures and scripts not counted.",
        f"- **Library structure:** {s['modules']} modules, {s['classes']} classes, "
        f"{s['functions']} functions/methods; docstrings on {s['docstrings']}/{s['documentable']} "
        f"({s['docstrings'] / s['documentable']:.0%}) modules, classes and functions.",
        "",
        "## Tests per tier",
        "",
        "| Tier (pytest marker) | Tests | What it exercises |",
        "| --- | ---: | --- |",
    ]
    meaning = {
        "unit": "single modules, no network; incl. in-process CLI, benchmark, browser fakes",
        "contract": "each provider adapter against sanitized documented responses (HTTP mocked)",
        "integration": "orchestrator + adapters + ensemble together, incl. adversarial Review B",
        "e2e": "real `python -m turingtongue` subprocesses",
        "network or paid or browser": "opt-in live tests, deselected by default",
    }
    for tier, n in metrics["tests"].items():
        lines.append(f"| `{tier}` | {n} | {meaning[tier]} |")
    lines += [
        "",
        "Outside pytest: `scripts/e2e_clean_install.sh` (built wheel in a fresh venv) and",
        "`scripts/docker_check.sh` (Docker image) run in every pipeline.",
        "",
        "## Branch coverage of the library per tier",
        "",
        "Statement + branch coverage of `src/turingtongue` when **only** that tier runs.",
        "The e2e tier is measured inside its child processes (coverage subprocess patching),",
        "so end-to-end coverage is real, not inferred.",
        "",
        "| Tier | Coverage | Lines covered | Branches covered |",
        "| --- | ---: | ---: | ---: |",
    ]
    for tier, c in metrics["coverage"].items():
        lines.append(
            f"| {tier} | {c['percent']:.1f} % | {c['covered_lines']}/{c['statements']} "
            f"| {c['covered_branches']}/{c['branches']} |"
        )
    lines += [
        "",
        "The pipeline gate (`./localPipeline.sh`) enforces **≥ 95 %** combined branch coverage",
        "on every commit; the per-tier numbers show how much each layer covers on its own.",
    ]
    cx = metrics.get("complexity")
    if cx:
        top = ", ".join(f"`{name}` ({score})" for score, name in cx["top"])
        grades = ", ".join(f"{g}: {n}" for g, n in cx["grades"].items())
        lines += [
            "",
            "## Complexity (radon)",
            "",
            f"- {cx['blocks']} functions/methods/classes analysed; average cyclomatic complexity "
            f"**{cx['average']:.2f}**, maximum {cx['max'][0]} (`{cx['max'][1]}`).",
            f"- Rank distribution (A = simplest): {grades}.",
            f"- Most complex: {top}.",
            f"- Maintainability index: average {cx['mi_avg']:.1f}, lowest {cx['mi_min']:.1f} "
            "(radon scale 0–100, ≥ 20 = rank A).",
        ]
    lines += [
        "",
        "## Quality gates (enforced on every commit and in CI)",
        "",
        "ruff format + lint, mypy `--strict`, shellcheck, SPDX license headers, pytest with",
        "≥ 95 % branch coverage, sdist/wheel build, `twine check --strict`, clean-wheel-install",
        "e2e, pip-audit, Docker build + smoke — see [`localPipeline.sh`](../localPipeline.sh).",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=ROOT / "docs" / "metrics.md")
    parser.add_argument("--no-coverage", action="store_true", help="skip the coverage runs")
    args = parser.parse_args(argv)
    if shutil.which("cloc") is None:
        print("cloc is required (e.g. 'pacman -S cloc' / 'apt install cloc')", file=sys.stderr)
        return 2
    metrics: dict[str, Any] = {
        "generated": datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
        "version": run([sys.executable, "scripts/bump_version.py", "--show"]).stdout.strip(),
        "commit": run(["git", "rev-parse", "--short", "HEAD"]).stdout.strip(),
        "loc": {area: cloc(paths) for area, paths in AREAS.items()},
        "structure": structure(),
        "complexity": complexity(),
        "tests": test_counts(),
        "coverage": {} if args.no_coverage else coverage_matrix(),
    }
    args.out.write_text(render(metrics), encoding="utf-8")
    print(args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
