<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# ADR 0005 — External detection APIs only; no self-developed or local detector

- Status: accepted (owner decision)
- Date: 2026-10-07

## Context

`vision.md` §2.1 allows a *future* optional local or heuristic detector as an
experimental supplement. After the research question "is there a detector API without
signup?" (answer: no, see `docs/providers.md` §6) a local open-source detector
(Binoculars on a small model pair, torch + transformers) was proposed and briefly
prototyped.

## Decision

The owner decided: **the Python package only integrates external detection services.**

- No self-developed check, evaluator, heuristic or score of our own.
- No local/offline model-based detector either (no Binoculars, RoBERTa detector,
  perplexity scoring, GPU/CPU inference, `[local]` extra) — not even as an option.
- The prototype was never committed; it was discarded and its dependencies removed.
- `docs/human-vs-ai-signals.md` stays as interpretation background only.

This overrides the optional future local provider mentioned in vision §2.1.

## Consequences

- Detection always requires at least one configured external provider (API keys);
  without keys a check returns `NO_VERDICT` with `NOT_CONFIGURED` details.
- The offline `mock` provider remains strictly a test double for smoke tests, Docker
  checks and demos: it returns a fixed configured answer and analyses nothing.
- Any future proposal for an own or local detector needs a new owner decision.
