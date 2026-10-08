<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# Project metrics

Generated 2026-10-08 08:15 UTC for version `0.7.1` at commit `5de654e` by [`scripts/metrics.py`](../scripts/metrics.py) — regenerate with
`uv run python scripts/metrics.py`. Counting tool: cloc (code lines exclude blanks and comments).

## Lines of code

| Area | Files | Code | Comment | Blank |
| --- | ---: | ---: | ---: | ---: |
| Library (src/turingtongue) | 47 | 3,884 | 542 | 709 |
| Tests (Python) | 32 | 2,657 | 152 | 692 |
| Test fixtures (JSON) | 12 | 166 | 0 | 0 |
| Helper scripts + pipeline | 15 | 1,211 | 227 | 188 |
| CI / container | 6 | 311 | 42 | 45 |
| Documentation (Markdown) | 23 | 2,286 | 19 | 398 |

- **Test-to-code ratio:** 0.68 lines of test code per line of library code (2,657 : 3,884); fixtures and scripts not counted.
- **Library structure:** 46 modules, 54 classes, 197 functions/methods; docstrings on 209/297 (70%) modules, classes and functions.

## Tests per tier

| Tier (pytest marker) | Tests | What it exercises |
| --- | ---: | --- |
| `unit` | 262 | single modules, no network; incl. in-process CLI, benchmark, browser fakes |
| `contract` | 49 | each provider adapter against sanitized documented responses (HTTP mocked) |
| `integration` | 46 | orchestrator + adapters + ensemble together, incl. adversarial Review B |
| `e2e` | 6 | real `python -m turingtongue` subprocesses |
| `network or paid or browser` | 1 | opt-in live tests, deselected by default |

Outside pytest: `scripts/e2e_clean_install.sh` (built wheel in a fresh venv) and
`scripts/docker_check.sh` (Docker image) run in every pipeline.

## Branch coverage of the library per tier

Statement + branch coverage of `src/turingtongue` when **only** that tier runs.
The e2e tier is measured inside its child processes (coverage subprocess patching),
so end-to-end coverage is real, not inferred.

| Tier | Coverage | Lines covered | Branches covered |
| --- | ---: | ---: | ---: |
| unit | 84.7 % | 2069/2383 | 404/538 |
| contract | 59.6 % | 1537/2383 | 203/538 |
| integration | 69.9 % | 1790/2383 | 251/538 |
| e2e | 51.2 % | 1369/2383 | 128/538 |
| all (combined) | 98.6 % | 2366/2383 | 513/538 |

The pipeline gate (`./localPipeline.sh`) enforces **≥ 95 %** combined branch coverage
on every commit; the per-tier numbers show how much each layer covers on its own.

## Complexity (radon)

- 247 functions/methods/classes analysed; average cyclomatic complexity **4.32**, maximum 31 (`render_verbose`).
- Rank distribution (A = simplest): A: 189, B: 31, C: 22, D: 4, E: 1.
- Most complex: `render_verbose` (31), `Checker.select` (24), `compute` (22), `combine` (22), `run` (21).
- Maintainability index: average 70.0, lowest 32.8 (radon scale 0–100, ≥ 20 = rank A).

## Quality gates (enforced on every commit and in CI)

ruff format + lint, mypy `--strict`, shellcheck, SPDX license headers, pytest with
≥ 95 % branch coverage, sdist/wheel build, `twine check --strict`, clean-wheel-install
e2e, pip-audit, Docker build + smoke — see [`localPipeline.sh`](../localPipeline.sh).
