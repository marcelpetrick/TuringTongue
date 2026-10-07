<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# plan.md — execution ledger

Durable, resumable task ledger (see `AGENTS.md` for the crash-recovery protocol).
Task → commits: `git log --grep='Txxx'`. Status values: `todo`, `in_progress`, `done`, `blocked`.

## Phase 0 — repository foundation

- [x] T001 — Initialize Python 3.14 project, LICENSE (GPLv3), localPipeline.sh, helper scripts
  - Status: done
  - Depends on: —
  - Acceptance:
    - [x] pyproject with requires-python >=3.14
    - [x] uv.lock committed
    - [x] pipeline green
  - Notes: —
- [x] T002 — Create AGENTS.md and plan.md
  - Status: done
  - Depends on: T001
  - Acceptance:
    - [x] mantra + crash-recovery protocol in AGENTS.md
    - [x] plan with stable IDs
  - Notes: —
- [ ] T004 — GitHub Actions CI mirroring localPipeline.sh
  - Status: todo
  - Depends on: T001
  - Acceptance:
    - [ ] workflow runs ./localPipeline.sh
    - [ ] green on main
  - Notes: —

## Phase 1 — provider research

- [ ] T003 — Fresh provider research → docs/providers.md
  - Status: todo
  - Depends on: T001
  - Acceptance:
    - [ ] all §4 fields per provider
    - [ ] last_verified dates
    - [ ] browser fallback evaluation
  - Notes: —

## Phase 3 — domain model

- [ ] T010 — Typed result models + versioned JSON serialization
  - Status: todo
  - Depends on: T001
  - Acceptance:
    - [ ] Verdict/ProviderResult/CheckResult dataclasses
    - [ ] schema_version in every output
    - [ ] round-trip tests
  - Notes: —
- [ ] T011 — Error categories, ProviderFailure, secret redaction
  - Status: todo
  - Depends on: T010
  - Acceptance:
    - [ ] all §7.3 categories
    - [ ] redaction of keys/headers tested
  - Notes: —
- [ ] T012 — Configuration: env credentials, optional .env and TOML config
  - Status: todo
  - Depends on: T010
  - Acceptance:
    - [ ] missing creds → NOT_CONFIGURED, no crash
    - [ ] no secrets in config file by default
  - Notes: —
- [ ] T013 — Machine-readable provider registry (providers.toml)
  - Status: todo
  - Depends on: T010
  - Acceptance:
    - [ ] all §5.3 fields
    - [ ] selection by id/all/default/transport
  - Notes: —
- [ ] T014 — Exact-prefix input limit handling (chars/bytes/words)
  - Status: todo
  - Depends on: T010
  - Acceptance:
    - [ ] no silent truncation
    - [ ] coverage reported
    - [ ] Unicode boundary tests
  - Notes: —
- [ ] T015 — HTTP transport: timeouts, bounded retry with jitter, Retry-After, body cap
  - Status: todo
  - Depends on: T011
  - Acceptance:
    - [ ] retry only 408/429/5xx/network
    - [ ] Retry-After respected
    - [ ] tests
  - Notes: —

## Phase 4 — first adapters

- [ ] T020 — Provider base adapter + protocol
  - Status: todo
  - Depends on: T011,T013,T014,T015
  - Acceptance:
    - [ ] common flow
    - [ ] error mapping
    - [ ] raw capture opt-in
  - Notes: —
- [ ] T021 — Sapling adapter + contract fixtures
  - Status: todo
  - Depends on: T020,T003
  - Acceptance:
    - [ ] adapter
    - [ ] fixtures
    - [ ] contract tests
  - Notes: —
- [ ] T022 — GPTZero adapter + contract fixtures
  - Status: todo
  - Depends on: T020,T003
  - Acceptance:
    - [ ] adapter
    - [ ] fixtures
    - [ ] contract tests
  - Notes: —
- [ ] T023 — Pangram adapter + contract fixtures
  - Status: todo
  - Depends on: T020,T003
  - Acceptance:
    - [ ] adapter
    - [ ] fixtures
    - [ ] contract tests
  - Notes: —
- [ ] T024 — Offline mock provider for smoke tests (never default)
  - Status: todo
  - Depends on: T020
  - Acceptance:
    - [ ] clearly labeled
    - [ ] deterministic
  - Notes: —

## Phase 5 — ensemble

- [ ] T030 — Score/label/confidence normalization
  - Status: todo
  - Depends on: T010
  - Acceptance:
    - [ ] documented orientation -1 human … +1 AI
  - Notes: —
- [ ] T031 — Weighted mixture-of-experts, agreement, verdict + NO_VERDICT policy
  - Status: todo
  - Depends on: T030
  - Acceptance:
    - [ ] formula documented in code + docs
    - [ ] confidence/evidence/agreement distinct
    - [ ] tests
  - Notes: —
- [ ] T032 — Async orchestrator: selection, concurrency limits, timeouts, deadline, partial success
  - Status: todo
  - Depends on: T020,T031
  - Acceptance:
    - [ ] partial success
    - [ ] all-fail → NO_VERDICT
    - [ ] sync façade
  - Notes: —

## Phase 6 — CLI

- [ ] T040 — CLI check: one-line default, exit codes 0/2/3/4
  - Status: todo
  - Depends on: T032
  - Acceptance:
    - [ ] AI is not an error exit
  - Notes: —
- [ ] T041 — Verbose report
  - Status: todo
  - Depends on: T040
  - Acceptance:
    - [ ] every §3.2 item shown
  - Notes: —
- [ ] T042 — JSON output
  - Status: todo
  - Depends on: T040
  - Acceptance:
    - [ ] versioned schema
  - Notes: —
- [ ] T043 — providers command (registry + credential presence)
  - Status: todo
  - Depends on: T040
  - Acceptance:
    - [ ] no secret values shown
  - Notes: —

## Phase 7 — provider expansion

- [ ] T050 — Copyleaks adapter (login token flow, sandbox flag)
  - Status: todo
  - Depends on: T020,T003
  - Acceptance:
    - [ ] adapter
    - [ ] fixtures
    - [ ] sandbox = mock results documented
  - Notes: —
- [ ] T051 — Winston AI adapter
  - Status: todo
  - Depends on: T020,T003
  - Acceptance:
    - [ ] adapter
    - [ ] fixtures
  - Notes: —
- [ ] T052 — Originality.ai adapter
  - Status: todo
  - Depends on: T020,T003
  - Acceptance:
    - [ ] adapter
    - [ ] fixtures
  - Notes: —
- [ ] T053 — Hive adapter
  - Status: todo
  - Depends on: T020,T003
  - Acceptance:
    - [ ] adapter
    - [ ] fixtures
  - Notes: —
- [ ] T054 — ZeroGPT adapter (if documented)
  - Status: todo
  - Depends on: T020,T003
  - Acceptance:
    - [ ] adapter or documented exclusion
  - Notes: —

## Phase 8 — research documentation

- [ ] T060 — docs/human-vs-ai-signals.md
  - Status: todo
  - Depends on: —
  - Acceptance:
    - [ ] all §9 topics
    - [ ] evidence classes
    - [ ] references
  - Notes: —

## Phase 9 — benchmark

- [ ] T070 — Human ground-truth corpus (public domain, provenance)
  - Status: todo
  - Depends on: —
  - Acceptance:
    - [ ] pre-LLM texts
    - [ ] source + license per sample
  - Notes: —
- [ ] T071 — AI ground-truth corpus from several model families
  - Status: todo
  - Depends on: —
  - Acceptance:
    - [ ] model/tool/date/prompt hash recorded
  - Notes: —
- [ ] T072 — Benchmark runner, metrics, report + CLI command
  - Status: todo
  - Depends on: T032,T070,T071
  - Acceptance:
    - [ ] §10.5 metrics
    - [ ] latency percentiles
    - [ ] tests
  - Notes: —
- [ ] T073 — Initial benchmark run / documented credential blocker
  - Status: todo
  - Depends on: T072
  - Acceptance:
    - [ ] docs/benchmarking.md
  - Notes: —

## Phase 10 — browser fallback

- [ ] T080 — Optional Playwright framework + evaluation ADR
  - Status: todo
  - Depends on: T020
  - Acceptance:
    - [ ] [browser] extra
    - [ ] API package imports without playwright
    - [ ] decision documented
  - Notes: —

## Phase 11 — performance

- [ ] T090 — Timing/profiling instrumentation (per phase, ensemble, wall clock)
  - Status: todo
  - Depends on: T032
  - Acceptance:
    - [ ] timings in result
  - Notes: —
- [ ] T091 — Measured performance pass
  - Status: todo
  - Depends on: T090
  - Acceptance:
    - [ ] before/after numbers or documented 'no bottleneck'
  - Notes: —

## Phase 12 — delivery

- [ ] T100 — Clean-install e2e script (wheel in fresh venv, outside source tree)
  - Status: todo
  - Depends on: T040
  - Acceptance:
    - [ ] §18.6 steps 1-6, 8-10
  - Notes: —
- [ ] T101 — Batch command (JSONL/CSV)
  - Status: todo
  - Depends on: T032
  - Acceptance:
    - [ ] §30 columns
  - Notes: —
- [ ] T102 — Dockerfile + docker smoke check in pipeline
  - Status: todo
  - Depends on: T100
  - Acceptance:
    - [ ] image runs CLI
    - [ ] pipeline stage
  - Notes: —
- [ ] T103 — GHCR docker publish workflow
  - Status: todo
  - Depends on: T102
  - Acceptance:
    - [ ] push on main + tags
  - Notes: —
- [ ] T104 — Release workflow: GitHub release + prepared PyPI Trusted Publishing
  - Status: todo
  - Depends on: T004
  - Acceptance:
    - [ ] tag → release with artifacts
    - [ ] PyPI job manual-only
  - Notes: —
- [ ] T105 — Opt-in network integration workflow
  - Status: todo
  - Depends on: T004
  - Acceptance:
    - [ ] manual/scheduled
    - [ ] only configured providers
    - [ ] never on PRs
  - Notes: —
- [ ] T106 — Docs: architecture, privacy, benchmarking, ADRs, .env.example
  - Status: todo
  - Depends on: T032
  - Acceptance:
    - [ ] privacy prominent
  - Notes: —
- [ ] T107 — README with real badges, screenshot, usage
  - Status: todo
  - Depends on: T040
  - Acceptance:
    - [ ] §20 questions answered
  - Notes: —
- [ ] T108 — Dependabot config
  - Status: todo
  - Depends on: T004
  - Acceptance:
    - [ ] pip + actions + docker
  - Notes: —

## Phase 13 — review and handoff

- [ ] T110 — Review A: implementation correctness (/reviewBranch) + fixes
  - Status: todo
  - Depends on: all
  - Acceptance:
    - [ ] findings fixed or tracked
  - Notes: —
- [ ] T111 — Review B: adversarial end-to-end scenarios
  - Status: todo
  - Depends on: all
  - Acceptance:
    - [ ] §21.3 scenarios tested
  - Notes: —
- [ ] T112 — GitHub About + topics
  - Status: todo
  - Depends on: T107
  - Acceptance:
    - [ ] applied
  - Notes: —
- [ ] T113 — IMPLEMENTATION_REPORT.md
  - Status: todo
  - Depends on: T110,T111
  - Acceptance:
    - [ ] §33 contents
  - Notes: —
- [ ] T114 — GitHub release
  - Status: todo
  - Depends on: T104,T113
  - Acceptance:
    - [ ] release published with artifacts
  - Notes: —

## Open items / blockers

- No provider API credentials are available in this environment; live provider calls are blocked on owner-supplied keys.
