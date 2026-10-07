<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# ADR 0002 — Ensemble v0: equal reliability, documented factors, three separate numbers

- Status: accepted
- Date: 2026-10-07

## Decision

- Every detector is an expert whose vote weight is
  `reliability × confidence_factor × applicability × coverage`.
- **Reliability starts equal (1.0)** for all providers (`v0-equal-weights`). Vendor
  headline accuracy claims are ignored. Owners may override weights in the config file.
- Confidence factor `0.5 + 0.5·c` for provider confidence `c ∈ [0, 1]`; **unknown
  confidence stays unknown** (`None`) and uses the neutral factor 0.75.
- Applicability 0.5 below a provider's *recommended* minimum length; coverage = share of
  characters actually submitted (exact-prefix truncation).
- Evidence orientation: −1 human … +1 AI; it is **not called a probability**.
- Provider confidence, ensemble strength and directional agreement are reported as
  separate numbers; the derived "ensemble confidence" is `strength × agreement × support`.
- `NO_VERDICT` when nothing usable came back, effective weight < 0.3, agreement < 0.3
  (conflicted) or |evidence| < 0.15 (deadband).

## Consequences

Weights can later be learned from the benchmark's `calibration` split only and reported
on the `holdout` split; any change bumps `EnsemblePolicy.version`.
