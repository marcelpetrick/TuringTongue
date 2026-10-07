<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# Architecture

> Functionality first. Make it correct, observable, testable, and resumable. Optimize
> only after profiling identifies a real bottleneck.

```text
            text (str, never modified)
                     │
   CLI (cli/main.py) │  Python API: Checker.check() / acheck()
                     ▼
            ┌─────────────────┐  Registry (data/providers.toml)
            │ client.Checker  │◄─ Settings (env credentials, .env, TOML config)
            │  select()       │
            │  run concurrently (global + per-provider semaphores,
            │  per-provider timeout, overall deadline)
            └───────┬─────────┘
       ┌────────────┼──────────────┬───────────────┐
       ▼            ▼              ▼               ▼
  SaplingProvider GPTZero …   CopyleaksProvider  BrowserProvider (optional)
       │  BaseProvider.detect(): credentials → exact-prefix limits →
       │  _detect() via HttpCaller (timeouts, bounded jittered retries,
       │  Retry-After, body cap, error classification) → Detection
       ▼
  ProviderResult (raw + normalized evidence, confidence, segments, cost,
                  rate limit, timings, warnings, error)  — failures are data
       │
       ▼
  ensemble.combine()  → Verdict (HUMAN / AI / NO_VERDICT) + Aggregate
       │                (evidence, strength, agreement, confidence, reasons)
       ▼
  CheckResult  → one word · verbose report · versioned JSON (schema_version 1.0)
```

## Modules

| Module | Responsibility |
| --- | --- |
| `models.py` | Typed dataclasses, enums, error categories, JSON serialization |
| `errors.py`, `redaction.py` | Categorized failures; HTTP status mapping; secret redaction |
| `config.py` | `Settings`: timeouts, concurrency, retries, per-provider overrides, credentials |
| `registry.py` + `data/providers.toml` | Machine-readable provider metadata (vision §5.3), lazy adapter import |
| `normalization/` | Exact-prefix limits (chars/bytes/words), score/label/confidence orientation |
| `transport.py` | Shared HTTP behaviour; retry policy (vision §11.4) |
| `providers/` | One adapter per service + offline `mock` test double |
| `ensemble.py` | Weighted mixture-of-experts and verdict policy (ADR 0002) |
| `client.py` | Provider selection, concurrency, deadlines, partial success |
| `batch.py`, `benchmark/` | Many-file analysis; corpus → runs → metrics → report |
| `browser/` | Optional Playwright framework with terms gate (ADR 0003) |
| `cli/` | Thin argparse layer, exit codes 0/2/3/4, rich rendering |

## Provider selection

| Request | Runs | Unconfigured providers |
| --- | --- | --- |
| default (`None`) | enabled-by-default providers with credentials | listed under `selection.skipped` |
| `"all"` | every real provider | `NOT_CONFIGURED` result each |
| explicit ids | exactly those | `NOT_CONFIGURED` result each |
| `transport="api"` / `"browser"` / `"mock"` | filter on top of the above | — |

The `mock` provider (a fixed answer, not a detector) only runs when named or with
`transport="mock"`.

## Observability

Each `ProviderResult` records `checked_at`, latency, phase timings (`prepare`, `network`,
`parse_and_overhead`; browser phases for browser adapters), attempts, HTTP status,
rate-limit headers, credits, model/version, adapter version, coverage, weight factors and
the inclusion/exclusion reason. `CheckResult.timing` separates wall clock from the sum of
provider latencies (they differ because providers run concurrently) and the ensemble
time. Library logging uses the standard `logging` module (`turingtongue` logger,
`--debug` in the CLI) and never logs the text.

## Adding a provider

1. Verify the official docs; add a row to `docs/providers.md` with `last_verified`.
2. Add `[providers.<id>]` to `data/providers.toml`.
3. Implement `providers/<id>.py` (subclass `BaseProvider`, implement `_detect`).
4. Add sanitized fixtures under `tests/fixtures/<id>/` and `tests/contract/test_<id>.py`.
