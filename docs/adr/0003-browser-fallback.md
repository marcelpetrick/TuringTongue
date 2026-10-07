<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# ADR 0003 — Browser fallback: framework yes, site adapters no (for now)

- Status: accepted
- Date: 2026-10-07

## Context

Vision §2.2/§13 makes browser automation a fallback behind documented APIs, only where
the provider's terms permit it. The 2026-10-07 research (`docs/providers.md` §5) found:

- all eight candidate services (GPTZero, Pangram, Sapling, Copyleaks, Winston AI,
  Originality.ai, Hive, ZeroGPT) **have documented APIs**;
- the terms of service of all of them **forbid automated use of the web UI** (robots,
  scrapers, "except via the API").

## Decision

1. Ship the browser *framework* (`turingtongue.browser`) as an optional `[browser]` extra:
   lazy Playwright import, a fresh non-persistent context per run, explicit per-phase
   timing (startup/navigate/submit/wait_result/parse), categorized failures, and
   opt-in debug capture.
2. A site adapter only runs when its registry entry declares
   `automation_terms = "permitted"` with a `terms_reviewed` date; otherwise it returns
   `TERMS_NOT_PERMITTED` without touching the network.
3. **No concrete site adapter is registered.** Scraping a site whose terms forbid it, or
   duplicating a service that offers an API, is not worth the fragility or the breach.
4. `--transport browser` is supported and simply selects nothing today.

## Consequences

- API-only users never import Playwright (tested).
- Adding a permitted site later means one subclass of `BrowserProvider` plus a registry
  entry and separate opt-in `browser` tests — no change to the ensemble or CLI.
- Added wall-clock cost of a browser provider is not measurable until one exists.
