<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# Project metrics

Generated 2026-10-08 12:11 UTC for version `0.7.11` at commit `99eb01d` by [`scripts/metrics.py`](../scripts/metrics.py) — regenerate with
`uv run python scripts/metrics.py`. Counting tool: cloc (code lines exclude blanks and comments).

## Lines of code

| Area | Files | Code | Comment | Blank |
| --- | ---: | ---: | ---: | ---: |
| Library (src/turingtongue) | 47 | 3,906 | 554 | 744 |
| Tests (Python) | 33 | 2,703 | 154 | 707 |
| Test fixtures (JSON) | 12 | 166 | 0 | 0 |
| Helper scripts + pipeline | 15 | 1,211 | 227 | 188 |
| CI / container | 6 | 311 | 42 | 45 |
| Documentation (Markdown) | 23 | 2,417 | 19 | 399 |

- **Test-to-code ratio:** 0.69 lines of test code per line of library code (2,703 : 3,906); fixtures and scripts not counted.
- **Library structure:** 46 modules, 55 classes, 216 functions/methods; docstrings on 220/317 (69%) modules, classes and functions.

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
| unit | 85.3 % | 2098/2405 | 401/524 |
| contract | 60.7 % | 1578/2405 | 201/524 |
| integration | 70.9 % | 1827/2405 | 249/524 |
| e2e | 52.1 % | 1403/2405 | 123/524 |
| all (combined) | 99.1 % | 2397/2405 | 507/524 |

The pipeline gate (`./localPipeline.sh`) enforces **≥ 95 %** combined branch coverage
on every commit; the per-tier numbers show how much each layer covers on its own.

## Complexity (radon)

- 268 functions/methods/classes analysed; average cyclomatic complexity **4.01**, maximum 17 (`WinstonProvider`).
- Rank distribution (A = simplest): A: 202, B: 43, C: 23.
- Most complex: `WinstonProvider` (17), `HiveProvider` (17), `WinstonProvider._detect` (16), `HiveProvider._detect` (16), `GPTZeroProvider` (15).
- Maintainability index: average 69.9, lowest 32.4 (radon scale 0–100, ≥ 20 = rank A).

## Quality gates (enforced on every commit and in CI)

ruff format + lint, mypy `--strict`, shellcheck, SPDX license headers, pytest with
≥ 95 % branch coverage, sdist/wheel build, `twine check --strict`, clean-wheel-install
e2e, pip-audit, Docker build + smoke — see [`localPipeline.sh`](../localPipeline.sh).
