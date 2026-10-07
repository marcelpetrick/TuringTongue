<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# Performance

Target (vision §11.1): a multi-provider check in about one minute or less. Approach:
measure first, optimize only proven bottlenecks.

## Instrumentation

Every result records wall clock, the sum of provider latencies, ensemble time, and per
provider: total latency, `prepare` / `network` / `parse_and_overhead` phases (browser
adapters: `startup` / `navigate` / `submit` / `wait_result` / `parse`), attempts and
retries. `turingtongue check -v` shows them; JSON carries all of them.

## Measurement (2026-10-07, offline)

`scripts/profile_concurrency.py` runs five real adapters (Sapling, GPTZero, Winston,
Originality, Hive) against mocked endpoints with a simulated 300 ms latency each:

| max_concurrency | wall clock ms | provider latency sum ms | overhead vs ideal ms |
| ---: | ---: | ---: | ---: |
| 1 | 1519 | 1508 | 19.5 |
| 2 | 917 | 1510 | 16.9 |
| 4 | 613 | 1511 | 13.3 |

Findings:

- Our own overhead (selection, input preparation, parsing, ensemble, result building) is
  **~3–4 ms per provider** — negligible against real network latencies of 0.5–10 s.
- Concurrency is the only lever that matters: with the default `max_concurrency = 4`
  wall clock is ≈ `ceil(n / 4) × slowest latency`. Note that the provider latency sum
  (~1.5 s) is unchanged — it is *not* wall-clock time.
- Each provider still receives at most one request at a time
  (`per_provider_concurrency = 1`), batch/benchmark runs are sequential, and retries use
  bounded jittered backoff — so concurrency never creates per-provider bursts.
- Pangram is asynchronous (submit + poll every 1 s); its wall clock is bounded by the
  per-provider timeout (default 30 s) and overall deadline (default 120 s).

Decision: no caching, batching or connection pooling beyond the shared `httpx` client —
there is no measured bottleneck to justify them. Re-measure with real credentials using
`turingtongue benchmark` (latency mean/p50/p90/p95/p99 per provider).
