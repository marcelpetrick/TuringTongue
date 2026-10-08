<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# Project metrics

Generated 2026-10-08 12:03 UTC for version `0.7.6` at commit `0c676df` by [`scripts/metrics.py`](../scripts/metrics.py) — regenerate with
`uv run python scripts/metrics.py`. Counting tool: cloc (code lines exclude blanks and comments).

## Lines of code

| Area | Files | Code | Comment | Blank |
| --- | ---: | ---: | ---: | ---: |
| Library (src/turingtongue) | 47 | 3,881 | 545 | 723 |
| Tests (Python) | 33 | 2,703 | 154 | 707 |
| Test fixtures (JSON) | 12 | 166 | 0 | 0 |
| Helper scripts + pipeline | 15 | 1,211 | 227 | 188 |
| CI / container | 6 | 311 | 42 | 45 |
| Documentation (Markdown) | 23 | 2,363 | 19 | 399 |

- **Test-to-code ratio:** 0.70 lines of test code per line of library code (2,703 : 3,881); fixtures and scripts not counted.
- **Library structure:** 46 modules, 54 classes, 205 functions/methods; docstrings on 211/305 (69%) modules, classes and functions.

## Tests per tier

| Tier (pytest marker) | Tests | What it exercises |
| --- | ---: | --- |
| `unit` | 270 | single modules, no network; incl. in-process CLI, benchmark, browser fakes |
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
| unit | 85.3 % | 2092/2397 | 410/536 |
| contract | 59.8 % | 1550/2397 | 203/536 |
| integration | 70.1 % | 1803/2397 | 253/536 |
| e2e | 51.5 % | 1383/2397 | 127/536 |
| all (combined) | 99.1 % | 2389/2397 | 519/536 |

The pipeline gate (`./localPipeline.sh`) enforces **≥ 95 %** combined branch coverage
on every commit; the per-tier numbers show how much each layer covers on its own.

## Complexity (radon)

- 255 functions/methods/classes analysed; average cyclomatic complexity **4.22**, maximum 22 (`compute`).
- Rank distribution (A = simplest): A: 192, B: 38, C: 22, D: 3.
- Most complex: `compute` (22), `combine` (22), `run` (21), `PangramProvider._parse` (20), `CopyleaksProvider._detect` (20).
- Maintainability index: average 70.0, lowest 32.4 (radon scale 0–100, ≥ 20 = rank A).

## Quality gates (enforced on every commit and in CI)

ruff format + lint, mypy `--strict`, shellcheck, SPDX license headers, pytest with
≥ 95 % branch coverage, sdist/wheel build, `twine check --strict`, clean-wheel-install
e2e, pip-audit, Docker build + smoke — see [`localPipeline.sh`](../localPipeline.sh).
