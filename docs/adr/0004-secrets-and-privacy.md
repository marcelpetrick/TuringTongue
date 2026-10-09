<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# ADR 0004 — Long-lived credentials only via environment; text never persisted

- Status: accepted
- Date: 2026-10-07

## Decision

- Long-lived API keys and account secrets are read from environment variables only
  (optionally pre-filled from a
  gitignored `.env` that never overrides real variables). The TOML config file rejects
  secret-looking keys.
- Errors, logs and fixtures pass through redaction (known key values, bearer tokens,
  `key=value` patterns, sensitive headers). The ordinary adapter caches Copyleaks tokens
  in memory. The live-E2E bootstrap added by ADR 0006 persists only the machine-issued,
  48-hour token so separate `init` and `e2e` processes can share it: the run-scoped
  directory is mode 0700, its token file is mode 0600, and `cleanup` deletes the file.
- The library never writes the submitted text to disk. Results store size and SHA-256,
  not the text; raw provider captures (opt-in `verbose`) drop echoed input where the
  provider returns it. Benchmark/batch outputs are explicit user actions.
- Provider-side privacy toggles are set where they exist (Originality `storeScan=false`,
  Pangram `public_dashboard_link=false`).
