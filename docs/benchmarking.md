<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# Benchmarking

```bash
# offline pipeline smoke test (mock provider — a fixed answer, NOT a detector)
turingtongue benchmark -p mock --out benchmark/results

# real providers (sends 17 texts to each; may consume paid credits)
turingtongue benchmark -p sapling -p gptzero --yes
turingtongue benchmark --split holdout --yes          # report on holdout only
turingtongue benchmark --from-results benchmark/results/results-<stamp>.jsonl
```

- Corpus: [`benchmark/corpus`](../benchmark/corpus/README.md) — 8 public-domain human
  texts (1813–1915, EN + DE), 8 AI texts from three model families (Claude, GPT via Codex,
  Qwen), 1 mixed sample. Every file is SHA-256-pinned in `manifest.toml` with provenance.
- Samples run **one after another** (no bursts). Each run writes a new
  `results-<UTC>.jsonl` plus `.report.md` / `.report.json`; earlier runs are never
  overwritten, so provider drift stays visible.
- Metrics per provider and for the ensemble: accuracy, balanced accuracy, precision,
  recall, specificity, false-positive/negative rates, F1, abstention rate, coverage,
  failure rate, confusion matrix, rank-based ROC-AUC on the evidence score, latency mean
  and p50/p90/p95/p99 (only with enough samples), credits per sample and per 1,000 words,
  model versions seen. Brier/calibration metrics are intentionally not computed.
- **False positives on human text** matter most: check the FPR column first.
- Separation: samples carry `split = calibration | holdout`. Weights are equal today; if
  they are ever learned, use only `--split calibration` for fitting and report holdout.

## Initial run (2026-10-07)

No provider credentials were available in the development environment, so only the
offline mock pipeline run was possible; it validates corpus loading, sequential
execution, result storage, metrics and reporting, but says nothing about detector
quality (the mock answers HUMAN for every text, hence 50 % accuracy / 0 % recall).
The real comparison is blocked on owner-supplied API keys — run the commands above
once keys are in `.env`.
