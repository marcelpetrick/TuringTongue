<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# AGENTS.md — operating guide for every agent working on TuringTongue

## Core mantra

> **Functionality first. Make it correct, observable, testable, and resumable. Optimize only after profiling identifies a real bottleneck.**

## What this project is

A local Python 3.14+ library (`turingtongue`) plus CLI that sends a text, **unchanged**, to several
existing AI-text detection services, normalizes their incompatible answers and combines them with a
transparent weighted mixture-of-experts into `HUMAN`, `AI` or `NO_VERDICT`. The authoritative
requirements live in [`vision.md`](vision.md); the execution ledger is [`plan.md`](plan.md).

## Startup / crash-recovery protocol (mandatory)

1. read `vision.md`;
2. read `AGENTS.md` (this file);
3. read `plan.md`;
4. `git status`;
5. `git log --oneline -20`;
6. find tasks with `Status: in_progress` in `plan.md`;
7. inspect the working tree **before** discarding anything — never assume uncommitted work is disposable;
8. resume or safely roll back the incomplete task;
9. update that task's notes if the previous run left ambiguous state;
10. continue with the next dependency-ready task.

## Working rules

- Read `vision.md`, `AGENTS.md`, `plan.md`, `git status`, and recent `git log` before modifying code.
- Never overwrite unrelated uncommitted user work.
- One logical concern per commit; Conventional Commits; include the plan task ID, e.g.
  `feat(provider): add Sapling adapter [T021]`. Map tasks to commits with `git log --grep='T021'`.
- Commit **only** through `scripts/commit.sh` — it bumps the version (patch per commit, `--minor` for
  major features), runs `./localPipeline.sh` and refuses to commit a red tree, then pushes.
- Work directly on `main`; push continuously.
- Update tests in the same logical task as the behavior they verify. Coverage must stay ≥ 95 %.
- Do not mark a task done until its acceptance criteria pass; update `plan.md` in the same commit.
- Keep network / paid / browser tests opt-in (pytest markers `network`, `paid`, `browser`).
- Never commit credentials. `.env` is gitignored; `.env.example` holds placeholders only.
- Never hide provider failures — failures are data (`ProviderError` with a category).
- API first, browser fallback second; no quota evasion, no CAPTCHA bypass, no identity rotation.
- **External APIs only — no own or local detector** (ADR 0005).
- **Do not preprocess the submitted text.** No stripping, normalizing, rewriting. Only an exact prefix
  may be submitted when a provider's documented hard limit requires it, and it is marked `truncated`.
- Document provider facts with a verification date in `docs/providers.md`.
- Keep `plan.md` current so another agent can resume after a crash.
- Run the smallest relevant test set while developing (`./localPipeline.sh --fast`, or `uv run pytest tests/unit`)
  and the full gate before every commit (done by `scripts/commit.sh`).
- After a sub-agent returns, review its diff and run the tests instead of trusting its summary.
- Every source file carries the SPDX `GPL-3.0-or-later` header (`scripts/check_headers.py` enforces it).
- Repository file and directory names must not contain whitespace. Keep the path check in the local/CI
  pipeline green when adding or renaming files.
- Prefer `scripts/commit.sh --only <path>…` so a commit contains exactly one task's files;
  plain `scripts/commit.sh` stages everything and prints the staged list — check it.
- Use `scripts/plan_task.py Txxx <status> --note "…"` to update `plan.md`.

## Accounts, credentials and publishing

- **Live end-to-end tests are required** (owner decision 2026-10-08, ADR 0006): real-service
  validation runs through `turingtongue init <p> --mode e2e --acquire-credential` → `turingtongue e2e <p>` →
  `turingtongue cleanup <p>` (`scripts/live_e2e.sh`, workflow `Live E2E`, and inside every
  release when `vars.E2E_PROVIDERS` is set). First provider: **Copyleaks** (machine-issued
  48 h token via the official login API + free sandbox). Keep the request budget
  (≤ 2 per run), never fall back to the mock in a live run, never print secrets.
- **Automate credentials only through provider-supported mechanisms** (preference:
  environment → sandbox → machine-issued token → OAuth → owned ephemeral identity →
  CI secret → manual; declared per provider as `bootstrap` in `data/providers.toml`).
  No provider supports machine-driven *account registration*, so agents never script
  website signups, CAPTCHAs, email verification or mass accounts; such providers report
  `manual-credential-required` with exact steps. Long-lived account secrets live only in
  `.env` (gitignored) or GitHub secrets.
- Credential acquisition is always deliberate: remote token/key issuance requires the explicit
  `--acquire-credential` CLI flag and provider-specific official API support. The flag may exchange
  an existing account secret for a token or issue a key inside an existing human-created account;
  it never authorizes automated account signup, CAPTCHA/email-verification automation, trial
  cycling, or undocumented/private endpoints.
- **No "free, no signup" web UIs.** They are not APIs; calling their private endpoints is
  scraping/quota evasion (vision §2.3). Research is recorded in `docs/providers.md` §6.
- **External detection APIs only** (owner decision, ADR 0005): never add a self-developed
  check, heuristic score, or local/offline model detector (no Binoculars, perplexity
  scoring, torch/transformers, GPU/CPU inference) — not even as an optional extra.
  The `mock` provider is a test double only and must never analyse text.
- Releases: `scripts/release.sh` tags `v<version>`; the Release workflow publishes the
  GitHub Release and — once the owner has registered the PyPI pending publisher and set
  `PYPI_PUBLISH=true` — uploads to PyPI via Trusted Publishing from the protected `pypi`
  environment after the owner approves. Follow the PyPA guide and `docs/releasing.md`
  (industry practice, not individual example repos); never add a long-lived PyPI token.

## Measuring

- `uv run python scripts/metrics.py` regenerates `docs/metrics.md` (LOC, tests per tier,
  per-tier and end-to-end subprocess coverage, complexity); update the README summary
  table when the numbers change noticeably.
- `uv run python scripts/history_chart.py` redraws the project history chart
  (`docs/history/`); `scripts/release.sh` does this automatically for every release.

## Layout

| Path | Content |
| --- | --- |
| `src/turingtongue/` | library: models, errors, config, registry, ensemble, client |
| `src/turingtongue/providers/` | one adapter per detection service (API) |
| `src/turingtongue/browser/` | optional Playwright fallback framework (`[browser]` extra) |
| `src/turingtongue/normalization/` | score/label/confidence/limit normalization |
| `src/turingtongue/benchmark/` | corpus loading, runner, metrics, report |
| `src/turingtongue/cli/` | thin CLI over the library |
| `tests/{unit,contract,integration,e2e,browser,benchmark}` | test tiers (see `pyproject.toml` markers) |
| `tests/fixtures/` | sanitized provider responses for contract tests |
| `benchmark/corpus/` | provenance-rich benchmark texts |
| `docs/` | providers matrix, signals research, architecture, privacy, benchmarking, ADRs |
| `scripts/` | small documented helper scripts (see `scripts/README.md`) |
