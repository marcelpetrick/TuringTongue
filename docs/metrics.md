<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# Project metrics

Generated 2026-10-09 07:46 UTC for version `0.7.18` at commit `fe06eea` by [`scripts/metrics.py`](../scripts/metrics.py) — regenerate with
`uv run python scripts/metrics.py`. Counting tool: cloc (code lines exclude blanks and comments).

## Lines of code

| Area | Files | Code | Comment | Blank |
| --- | ---: | ---: | ---: | ---: |
| Library (src/turingtongue) | 47 | 4,308 | 575 | 773 |
| Tests (Python) | 33 | 3,015 | 154 | 758 |
| Test fixtures (JSON) | 12 | 166 | 0 | 0 |
| Helper scripts + pipeline | 17 | 1,301 | 249 | 206 |
| CI / container | 6 | 313 | 45 | 45 |
| Documentation (Markdown) | 23 | 2,563 | 19 | 406 |

- **Test-to-code ratio:** 0.70 lines of test code per line of library code (3,015 : 4,308); fixtures and scripts not counted.
- **Library structure:** 46 modules, 55 classes, 228 functions/methods; docstrings on 227/329 (69%) modules, classes and functions.

## Tests per tier

| Tier (pytest marker) | Tests | What it exercises |
| --- | ---: | --- |
| `unit` | 280 | single modules, no network; incl. in-process CLI, benchmark, browser fakes |
| `contract` | 50 | each provider adapter against sanitized documented responses (HTTP mocked) |
| `integration` | 54 | orchestrator + adapters + ensemble together, incl. adversarial Review B |
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
| unit | 79.2 % | 2156/2631 | 407/606 |
| contract | 56.2 % | 1615/2631 | 204/606 |
| integration | 71.8 % | 2014/2631 | 311/606 |
| e2e | 48.1 % | 1434/2631 | 123/606 |
| all (combined) | 97.1 % | 2577/2631 | 567/606 |

The pipeline gate (`./localPipeline.sh`) enforces **≥ 95 %** combined branch coverage
on every commit; the per-tier numbers show how much each layer covers on its own.

## Complexity (radon)

- 280 functions/methods/classes analysed; average cyclomatic complexity **4.18**, maximum 18 (`run_e2e`).
- Rank distribution (A = simplest): A: 206, B: 48, C: 26.
- Most complex: `run_e2e` (18), `_zerogpt_key` (18), `WinstonProvider` (17), `HiveProvider` (17), `WinstonProvider._detect` (16).
- Maintainability index: average 68.4, lowest 32.4 (radon scale 0–100, ≥ 20 = rank A).

## Quality gates (enforced on every commit and in CI)

ruff format + lint, mypy `--strict`, shellcheck, SPDX license headers, pytest with
≥ 95 % branch coverage, sdist/wheel build, `twine check --strict`, clean-wheel-install
e2e, pip-audit, Docker build + smoke — see [`localPipeline.sh`](../localPipeline.sh).
