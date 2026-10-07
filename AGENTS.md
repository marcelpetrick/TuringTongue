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
- **Do not preprocess the submitted text.** No stripping, normalizing, rewriting. Only an exact prefix
  may be submitted when a provider's documented hard limit requires it, and it is marked `truncated`.
- Document provider facts with a verification date in `docs/providers.md`.
- Keep `plan.md` current so another agent can resume after a crash.
- Run the smallest relevant test set while developing (`./localPipeline.sh --fast`, or `uv run pytest tests/unit`)
  and the full gate before every commit (done by `scripts/commit.sh`).
- After a sub-agent returns, review its diff and run the tests instead of trusting its summary.
- Every source file carries the SPDX `GPL-3.0-or-later` header (`scripts/check_headers.py` enforces it).

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
