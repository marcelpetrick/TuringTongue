<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# Implementation report

Date: 2026-10-07 · Version: see `pyproject.toml` · Ledger: [`plan.md`](plan.md)

## What was built

A Python 3.14 library + CLI (`turingtongue`) that sends a text **unchanged** to existing
AI-text detection APIs, normalizes their answers to one evidence axis (−1 human … +1 AI),
and combines them with a documented weighted mixture-of-experts into `HUMAN`, `AI` or
`NO_VERDICT`, with a verbose report and versioned JSON (`schema_version 1.0`).

- 8 API adapters + offline mock test double; machine-readable registry (`data/providers.toml`).
- Exact-prefix size-limit handling (characters / UTF-8 bytes / words) with coverage.
- Async orchestrator: default / all / named selection, transport filter (api / browser /
  mock), global + per-provider concurrency caps, per-provider timeout, overall deadline,
  partial success, failures as categorized data, secret redaction.
- Bounded jittered retries honouring `Retry-After`; provider-specific error semantics.
- CLI `check` / `providers` / `batch` / `benchmark`, exit codes 0 / 2 / 3 / 4.
- Benchmark corpus (17 provenance-pinned samples), sequential runner, metrics, reports.
- Optional Playwright browser framework with a terms-of-service gate (no site adapter).
- Docs: provider matrix, human-vs-AI signals research, architecture, privacy,
  benchmarking, performance, releasing, 4 ADRs, `AGENTS.md`, `plan.md`.
- Tooling: `localPipeline.sh` (mirrored 1:1 by GitHub Actions), helper scripts, Docker
  image on GHCR, tag-driven GitHub Release, PyPA-style hardened release (protected tags, provenance, approval-gated Trusted Publishing; enabled by one owner step), opt-in
  live E2E workflow with credential bootstrap (ADR 0006), Dependabot.

## Provider status

| Provider | Adapter | Tested against | Default | Notes |
| --- | --- | --- | --- | --- |
| Sapling | ✅ | documented examples (contract) | on | free trial key gives real results |
| GPTZero | ✅ | documented examples | on | 50k-char exact prefix (provider truncates silently) |
| Pangram | ✅ | documented examples | on | async submit + poll; `model` always sent |
| Copyleaks | ✅ | documented examples | on | token cache; **sandbox = mock results, excluded** |
| Winston AI | ✅ | documented schema (no official example) | on | human score inverted |
| Originality.ai | ✅ | documented examples | on | Enterprise plan; auto top-up warning |
| Hive | ✅ | documented examples (two envelope shapes) | on | sales-provisioned project |
| ZeroGPT | ✅ | synthetic fixture from schema | **off** | docs lack example responses |
| Browser (any site) | framework only | fake page | — | all candidates' ToS forbid automation (ADR 0003) |

**Real vs mocked:** every adapter is contract-tested offline; **none has been exercised
against the live service** because no API credentials exist in the development
environment. This is the main credential blocker (see below).

## Tests and gates

- `./localPipeline.sh` green: license headers, ruff format + lint, mypy `--strict`,
  shellcheck, 311 tests (unit, contract, integration incl. adversarial Review B, e2e,
  benchmark) with **98 % branch coverage** (gate ≥ 95 %), sdist/wheel build, twine
  `--strict`, clean-wheel-install e2e, pip-audit (no known vulnerabilities), Docker
  build + offline smoke. GitHub Actions CI and Docker workflows green.
- Opt-in only: `network`, `paid`, `browser` markers; `TURINGTONGUE_E2E_LIVE=1`;
  `Live E2E` workflow: init → ≤ 2 provider attempts → cleanup, weekly/on demand
  and in releases when `E2E_PROVIDERS` is non-empty (secrets, never on PRs). Copyleaks
  sandbox checks live API plumbing with simulated classifications; it does not complete
  T118's real, non-sandbox validation of at least three providers and benchmark drift.

## Clean-install result

`scripts/e2e_clean_install.sh`: fresh Python 3.14 venv, built wheel installed, import
proven to come from site-packages (no source leakage), `--help` / `--version`,
mock-provider HUMAN / AI runs, stdin, exit codes 2 / 3, graceful `NOT_CONFIGURED`, JSON
schema keys — **OK**. Live smoke step skipped (no credentials).

## Benchmark summary

Only the offline mock run was possible (pipeline validation; the mock always answers
HUMAN → 50 % accuracy, 0 % recall — meaningless for detector quality by design). The
real provider comparison (`turingtongue benchmark -p … --yes`) awaits API keys.

## Wall-clock / profiling

Offline profiling with five real adapters and 300 ms simulated latency: serial 1519 ms,
`max_concurrency=2` 917 ms, `4` 613 ms; own overhead ≈ 3–4 ms per provider. No
optimization beyond concurrency is justified ([docs/performance.md](docs/performance.md)).

## Reviews

- **Review A** (`/reviewBranch`, whole project): 7 findings — raw captures echoing input
  (Sapling, Pangram), loop-id-keyed semaphores, unclamped Pangram polling, rich markup
  injection from provider strings, CLI `--timeout` precedence, `weights_version` hiding
  overrides, `commit.sh` over-staging. All fixed with regression tests.
- **Review B** (adversarial, `tests/integration/test_adversarial.py`): clean install,
  missing credentials, one provider down, rate limit, disagreement (conflicted
  NO_VERDICT), short / huge text, Unicode confusables, non-English, schema variation,
  timeouts, all providers failing, JSON stability, minimal default CLI — all pass; no
  new defects.

## Known limitations

- No live validation of any adapter; response-shape assumptions come from docs and may
  drift (ambiguities are marked in `docs/providers.md`; drift surfaces as `SCHEMA_CHANGED`).
- Provider "characters" are treated as Unicode code points (no provider defines it).
- Ensemble weights are equal (v0); confidence semantics differ by vendor.
- Benchmark corpus is tiny and non-representative (historic literature as human side).
- Some commits bundle two tasks (e.g. batch shipped with the benchmark commit; ADRs with
  the browser commit) — traceable via `git log --grep`, noted in `plan.md`.

## Credential / terms blockers

- API keys for all eight providers (owner-supplied; put them in `.env` or repo secrets).
- Originality.ai and Hive require enterprise/sales-provisioned accounts.
- Browser automation: all reviewed sites' terms forbid it → no site adapter.
- PyPI: workflow and `pypi` environment ready, name `turingtongue` free; publication waits
  for the owner to add the pending publisher on PyPI and set `PYPI_PUBLISH=true`.

## Deviations from the vision

- **External APIs only** (owner decision, [ADR 0005](docs/adr/0005-external-apis-only.md)):
  the optional future local/heuristic detector of vision §2.1 will not be built; a brief
  uncommitted Binoculars prototype was discarded.

- `AI_HUMAN_EDITED` / `HUMAN_AI_ASSISTED` corpus categories are not populated (no human
  editor available in an autonomous run); one constructed `MIXED` sample exists.
- Llama could not be used for corpus generation (local runtime lacks the `mllama`
  architecture); MiniCPM-V (Qwen2-based) was used, so the corpus has three model families.
- Sub-agents were used for the two research deliverables; adapters were implemented by
  the orchestrator sequentially to avoid merge conflicts on shared files.

## Exact next tasks

1. Add API keys and run `TURINGTONGUE_E2E_LIVE=1 scripts/e2e_clean_install.sh`, then
   `turingtongue benchmark --yes`; update `docs/providers.md` integration status and add
   any drift as regression fixtures.
2. Re-verify ZeroGPT live; enable by default if the schema holds.
3. Add the owner's pre-2022 blog posts (with permission) and edited/assisted samples.
4. Consider learned weights only from the `calibration` split once data suffices.
5. Add the PyPI pending publisher, `gh variable set PYPI_PUBLISH --body true`, re-run the release.

## Release readiness

Ready for a GitHub release (wheel, sdist, GHCR image). Not yet validated against live
providers; results must be read as indicators, not proof.
