# Helper scripts

Small, single-purpose scripts for tasks that repeat during development. All are
GPL-3.0-or-later and are run from any working directory (they `cd` to the repo root).

| Script | Purpose | Typical use |
| --- | --- | --- |
| [`../localPipeline.sh`](../localPipeline.sh) | The complete quality gate: locked env sync, license headers, format, lint, mypy, shellcheck, tests + ≥95 % coverage, sdist/wheel build, twine metadata check, clean-install e2e, dependency audit, Docker build + smoke. GitHub Actions runs exactly this script. | `./localPipeline.sh` · `--fast` for the inner loop · `--no-docker` · `--no-audit` |
| [`commit.sh`](commit.sh) | Bump version (patch by default, `--minor` for major features), run the full pipeline, commit with a Conventional Commit message and push. Refuses non-conventional messages and never commits a red tree. | `scripts/commit.sh "feat(core): add result model [T011]"` |
| [`bump_version.py`](bump_version.py) | SemVer bump of `pyproject.toml` + `uv lock` refresh. | `scripts/bump_version.py patch` · `--show` |
| [`plan_task.py`](plan_task.py) | Set a task status in `plan.md` (checkbox, Status, acceptance boxes, notes). | `scripts/plan_task.py T021 done --note "..."` |
| [`check_headers.py`](check_headers.py) | Fails when a `.py`/`.sh` file lacks the SPDX GPL-3.0-or-later + copyright header. | run by the pipeline |
| [`audit_dependencies.sh`](audit_dependencies.sh) | `pip-audit` over every locked dependency (runtime, extras, dev). Needs network. | run by the pipeline |
| [`e2e_clean_install.sh`](e2e_clean_install.sh) | Installs the built wheel into a fresh Python 3.14 venv outside the source tree and checks import location, CLI help/version, mock-provider smoke runs, exit codes, graceful missing credentials and the JSON schema. `TURINGTONGUE_E2E_LIVE=1` adds real-provider smoke runs (may cost credits). | run by the pipeline · `scripts/e2e_clean_install.sh [WHEEL]` |
| [`docker_check.sh`](docker_check.sh) | Builds the Docker image and smoke-tests it offline (version, non-root, mock verdicts, stdin, JSON without credentials). | run by the pipeline · `scripts/docker_check.sh [TAG]` |
| [`provider_health.py`](provider_health.py) | Live, opt-in health check: one short public-domain sample per *configured* provider; Markdown/JSON table. Provider failures are reported, not fatal. Used by the scheduled `provider-health` workflow. | `uv run python scripts/provider_health.py` |
