<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# ADR 0004 — Credentials only via environment; text never persisted

- Status: accepted
- Date: 2026-10-07

## Decision

- API keys are read from environment variables only (optionally pre-filled from a
  gitignored `.env` that never overrides real variables). The TOML config file rejects
  secret-looking keys.
- Errors, logs and fixtures pass through redaction (known key values, bearer tokens,
  `key=value` patterns, sensitive headers). Copyleaks tokens are cached in memory only.
- The library never writes the submitted text to disk. Results store size and SHA-256,
  not the text; raw provider captures (opt-in `verbose`) drop echoed input where the
  provider returns it. Benchmark/batch outputs are explicit user actions.
- Provider-side privacy toggles are set where they exist (Originality `storeScan=false`,
  Pangram `public_dashboard_link=false`).
