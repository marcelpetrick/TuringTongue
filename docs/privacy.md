<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# Privacy and responsibility

**Checking a text sends the complete text (or, where a provider limit forces it, an exact
prefix) to every selected third-party detection service.** Once submitted, storage,
retention, training use, sub-processors and jurisdiction are governed by each provider's
own terms and privacy policy — not by this package. See the per-provider "Retention /
privacy" rows in [`providers.md`](providers.md). Notably, at the 2026-10-07 review
Copyleaks' policy allows using submitted content to train its models, and Hive retains
data for 14 days by default.

What this package does:

- It never writes the submitted text to disk. Results contain character/word counts and
  a SHA-256 fingerprint, not the text.
- It does not log the text; `--debug` logs only metadata.
- It sends privacy-preserving options where providers offer them (Originality.ai
  `storeScan=false`, Pangram `public_dashboard_link=false`).
- It removes echoed input from optional raw-response captures where providers echo it.
- It reads long-lived account credentials only from environment variables and redacts
  credentials from every error message. For live E2E, the short-lived Copyleaks login
  token is shared between `init` and `e2e` through a run-scoped owner-only directory
  (mode 0700) and file (mode 0600), then deleted by `cleanup`; the token also expires at
  the provider after 48 hours. The submitted text is never stored with it.
- Browser debug captures (screenshots/HTML, which may contain your text) happen only
  when you explicitly pass a `debug_dir` option.

What you should do:

- Do not submit confidential, personal or regulated material unless the provider's terms
  allow it for your use case.
- Select providers deliberately (`-p sapling -p gptzero`) when it matters.
- Treat results as **indicators, not proof of authorship**. Detectors are wrong in both
  directions, particularly on short, formulaic, technical, translated, heavily edited or
  non-native writing (see [`human-vs-ai-signals.md`](human-vs-ai-signals.md)).

Benchmark and batch runs write results to files you choose; that is a deliberate
workflow, separate from ordinary checks.
