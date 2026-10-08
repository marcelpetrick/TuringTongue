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
| [`live_e2e.sh`](live_e2e.sh) | Live E2E against real providers: `init` (credential bootstrap) → `e2e` (≤ 2 requests, sandbox where available) → `cleanup` (always, via trap). Exit 0 pass · 1 fail · 3 manual credential required. Used by the Live E2E and Release workflows. | `scripts/live_e2e.sh copyleaks` |
| [`release.sh`](release.sh) | Cut a release: requires a clean, pushed `main`; refreshes and commits the history chart (`--no-chart` to skip), tags `v<version>` and pushes it, triggering the Release and Docker workflows. | `scripts/release.sh` |
| [`profile_concurrency.py`](profile_concurrency.py) | Offline profiling: five real adapters against mocked endpoints with simulated latency; reports wall clock vs latency sum vs overhead for `max_concurrency` 1/2/4. Numbers recorded in `docs/performance.md`. | `uv run python scripts/profile_concurrency.py` |
| [`metrics.py`](metrics.py) | Lines of code per area (cloc), library structure, radon complexity, tests per tier and branch coverage per tier incl. end-to-end subprocesses; writes `docs/metrics.md`. Needs `cloc`. | `uv run python scripts/metrics.py` |
| [`history_chart.py`](history_chart.py) | Lines of code per area at every commit on `main` plus CI coverage per commit (from GitHub Actions logs) and release markers → `docs/history/loc-history.svg`, `loc-current.md`, cached `measurements.json`. Stdlib only, reads git objects, never the working tree. | `uv run python scripts/history_chart.py` · `--no-github` · `--no-measure` |
| [`setup_credentials.sh`](setup_credentials.sh) | After the one-time signup: paste a provider's key with hidden input → gitignored `.env` (0600); `--github` also sets the repo secrets and adds the provider to `E2E_PROVIDERS`; `--test` runs the live E2E. Never echoes or logs values. | `scripts/setup_credentials.sh sapling --github --test` |
