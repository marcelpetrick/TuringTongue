<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# Project metrics

Generated 2026-10-07 16:08 UTC for version `0.6.3` at commit `113c5e2` by [`scripts/metrics.py`](../scripts/metrics.py) — regenerate with
`uv run python scripts/metrics.py`. Counting tool: cloc (code lines exclude blanks and comments).

## Lines of code

| Area | Files | Code | Comment | Blank |
| --- | ---: | ---: | ---: | ---: |
| Library (src/turingtongue) | 41 | 3,439 | 473 | 616 |
| Tests (Python) | 32 | 2,480 | 151 | 656 |
| Test fixtures (JSON) | 12 | 166 | 0 | 0 |
| Helper scripts + pipeline | 15 | 1,248 | 221 | 197 |
| CI / container | 6 | 280 | 37 | 42 |
| Documentation (Markdown) | 21 | 2,187 | 17 | 377 |

- **Test-to-code ratio:** 0.72 lines of test code per line of library code (2,480 : 3,439); fixtures and scripts not counted.
- **Library structure:** 40 modules, 48 classes, 172 functions/methods; docstrings on 179/260 (69%) modules, classes and functions.

## Tests per tier

| Tier (pytest marker) | Tests | What it exercises |
| --- | ---: | --- |
| `unit` | 264 | single modules, no network; incl. in-process CLI, benchmark, browser fakes |
| `contract` | 49 | each provider adapter against sanitized documented responses (HTTP mocked) |
| `integration` | 31 | orchestrator + adapters + ensemble together, incl. adversarial Review B |
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
| unit | 91.0 % | 1947/2092 | 406/494 |
| contract | 62.5 % | 1415/2092 | 201/494 |
| integration | 62.5 % | 1427/2092 | 189/494 |
| e2e | 52.8 % | 1238/2092 | 127/494 |
| all (combined) | 98.4 % | 2075/2092 | 470/494 |

The pipeline gate (`./localPipeline.sh`) enforces **≥ 95 %** combined branch coverage
on every commit; the per-tier numbers show how much each layer covers on its own.

## Complexity (radon)

- 217 functions/methods/classes analysed; average cyclomatic complexity **4.49**, maximum 31 (`render_verbose`).
- Rank distribution (A = simplest): A: 163, B: 29, C: 21, D: 3, E: 1.
- Most complex: `render_verbose` (31), `Checker.select` (24), `compute` (22), `combine` (22), `run` (20).
- Maintainability index: average 69.5, lowest 33.4 (radon scale 0–100, ≥ 20 = rank A).

## Quality gates (enforced on every commit and in CI)

ruff format + lint, mypy `--strict`, shellcheck, SPDX license headers, pytest with
≥ 95 % branch coverage, sdist/wheel build, `twine check --strict`, clean-wheel-install
e2e, pip-audit, Docker build + smoke — see [`localPipeline.sh`](../localPipeline.sh).
