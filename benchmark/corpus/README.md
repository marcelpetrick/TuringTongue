<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# Benchmark corpus

A small, transparent corpus for catching integration/ensemble mistakes and starting to
compare providers (vision §10). **It is not a representative dataset** and must not be
used to claim detector accuracy in general.

| Folder | Label | Count | Content |
| --- | --- | --- | --- |
| `human/` | `HUMAN_RAW` | 8 | Public-domain prose, 1813–1915 (Project Gutenberg), 7 English + 1 German |
| `ai/` | `AI_RAW` | 8 | Generated 2026-10-07 by three model families: Anthropic Claude (claude-opus-5-5), OpenAI GPT (gpt-5.6-sol via Codex CLI), Alibaba Qwen (qwen3.5:4b; MiniCPM-V on a Qwen2 base) — 7 English + 1 German, five genres |
| `mixed/` | `MIXED` | 1 | Austen paragraph followed by a Claude-written continuation |

Every sample's provenance (source, licence, model, tool, full prompt + SHA-256, settings,
human edits, split) is recorded in [`manifest.toml`](manifest.toml); the loader verifies
each file's SHA-256 so silent edits are detected.

## Known limitations

- **Historical literature is a false-positive sanity check only.** 19th-century prose is
  stylistically far from modern human writing (and very likely part of LLM training data,
  which can make it *look* predictable). It does not represent bloggers, students or
  non-native writers.
- **Tiny size.** 17 samples cannot produce statistically meaningful accuracy estimates;
  per-provider numbers are smoke tests, not evaluations.
- **AI samples are raw and prompt-matched.** No human-edited, paraphrased or "humanized"
  AI text yet; real-world text is often in between.
- **Calibration vs holdout.** Samples alternate between `calibration` and `holdout`
  splits. Weights are currently equal (`v0-equal-weights`); if weights are ever learned,
  only the calibration split may be used and results reported on the holdout split.
- The project owner's own pre-2022 blog posts are a planned addition and are **not**
  included without explicit permission.
