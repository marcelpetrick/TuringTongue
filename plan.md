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
- [x] T004 — GitHub Actions CI mirroring localPipeline.sh
  - Status: done
  - Depends on: T001
  - Acceptance:
    - [ ] workflow runs ./localPipeline.sh
    - [ ] green on main
  - Notes: —

## Phase 1 — provider research

- [x] T003 — Fresh provider research → docs/providers.md
  - Status: done
  - Depends on: T001
  - Acceptance:
    - [x] all §4 fields per provider
    - [x] last_verified dates
    - [x] browser fallback evaluation
  - Notes: fresh official-doc research 2026-10-07 by research sub-agent; reviewed

## Phase 3 — domain model

- [x] T010 — Typed result models + versioned JSON serialization
  - Status: done
  - Depends on: T001
  - Acceptance:
    - [x] Verdict/ProviderResult/CheckResult dataclasses
    - [x] schema_version in every output
    - [x] round-trip tests
  - Notes: —
- [x] T011 — Error categories, ProviderFailure, secret redaction
  - Status: done
  - Depends on: T010
  - Acceptance:
    - [x] all §7.3 categories
    - [x] redaction of keys/headers tested
  - Notes: —
- [x] T012 — Configuration: env credentials, optional .env and TOML config
  - Status: done
  - Depends on: T010
  - Acceptance:
    - [x] missing creds → NOT_CONFIGURED, no crash
    - [x] no secrets in config file by default
  - Notes: —
- [x] T013 — Machine-readable provider registry (providers.toml)
  - Status: done
  - Depends on: T010
  - Acceptance:
    - [x] all §5.3 fields
    - [x] selection by id/all/default/transport
  - Notes: —
- [x] T014 — Exact-prefix input limit handling (chars/bytes/words)
  - Status: done
  - Depends on: T010
  - Acceptance:
    - [x] no silent truncation
    - [x] coverage reported
    - [x] Unicode boundary tests
  - Notes: —
- [x] T015 — HTTP transport: timeouts, bounded retry with jitter, Retry-After, body cap
  - Status: done
  - Depends on: T011
  - Acceptance:
    - [x] retry only 408/429/5xx/network
    - [x] Retry-After respected
    - [x] tests
  - Notes: —

## Phase 4 — first adapters

- [x] T020 — Provider base adapter + protocol
  - Status: done
  - Depends on: T011,T013,T014,T015
  - Acceptance:
    - [x] common flow
    - [x] error mapping
    - [x] raw capture opt-in
  - Notes: —
- [x] T021 — Sapling adapter + contract fixtures
  - Status: done
  - Depends on: T020,T003
  - Acceptance:
    - [x] adapter
    - [x] fixtures
    - [x] contract tests
  - Notes: —
- [x] T022 — GPTZero adapter + contract fixtures
  - Status: done
  - Depends on: T020,T003
  - Acceptance:
    - [x] adapter
    - [x] fixtures
    - [x] contract tests
  - Notes: —
- [x] T023 — Pangram adapter + contract fixtures
  - Status: done
  - Depends on: T020,T003
  - Acceptance:
    - [x] adapter
    - [x] fixtures
    - [x] contract tests
  - Notes: —
- [x] T024 — Offline mock provider for smoke tests (never default)
  - Status: done
  - Depends on: T020
  - Acceptance:
    - [x] clearly labeled
    - [x] deterministic
  - Notes: —

## Phase 5 — ensemble

- [x] T030 — Score/label/confidence normalization
  - Status: done
  - Depends on: T010
  - Acceptance:
    - [x] documented orientation -1 human … +1 AI
  - Notes: —
- [x] T031 — Weighted mixture-of-experts, agreement, verdict + NO_VERDICT policy
  - Status: done
  - Depends on: T030
  - Acceptance:
    - [x] formula documented in code + docs
    - [x] confidence/evidence/agreement distinct
    - [x] tests
  - Notes: —
- [x] T032 — Async orchestrator: selection, concurrency limits, timeouts, deadline, partial success
  - Status: done
  - Depends on: T020,T031
  - Acceptance:
    - [x] partial success
    - [x] all-fail → NO_VERDICT
    - [x] sync façade
  - Notes: shipped in commit 13604a5 together with T013/T020/T024

## Phase 6 — CLI

- [x] T040 — CLI check: one-line default, exit codes 0/2/3/4
  - Status: done
  - Depends on: T032
  - Acceptance:
    - [x] AI is not an error exit
  - Notes: —
- [x] T041 — Verbose report
  - Status: done
  - Depends on: T040
  - Acceptance:
    - [x] every §3.2 item shown
  - Notes: —
- [x] T042 — JSON output
  - Status: done
  - Depends on: T040
  - Acceptance:
    - [x] versioned schema
  - Notes: —
- [x] T043 — providers command (registry + credential presence)
  - Status: done
  - Depends on: T040
  - Acceptance:
    - [x] no secret values shown
  - Notes: —

## Phase 7 — provider expansion

- [x] T050 — Copyleaks adapter (login token flow, sandbox flag)
  - Status: done
  - Depends on: T020,T003
  - Acceptance:
    - [x] adapter
    - [x] fixtures
    - [x] sandbox = mock results documented
  - Notes: —
- [x] T051 — Winston AI adapter
  - Status: done
  - Depends on: T020,T003
  - Acceptance:
    - [x] adapter
    - [x] fixtures
  - Notes: —
- [x] T052 — Originality.ai adapter
  - Status: done
  - Depends on: T020,T003
  - Acceptance:
    - [x] adapter
    - [x] fixtures
  - Notes: —
- [x] T053 — Hive adapter
  - Status: done
  - Depends on: T020,T003
  - Acceptance:
    - [x] adapter
    - [x] fixtures
  - Notes: —
- [x] T054 — ZeroGPT adapter (if documented)
  - Status: done
  - Depends on: T020,T003
  - Acceptance:
    - [x] adapter or documented exclusion
  - Notes: implemented opt-in (disabled by default) because docs lack example responses

## Phase 8 — research documentation

- [x] T060 — docs/human-vs-ai-signals.md
  - Status: done
  - Depends on: —
  - Acceptance:
    - [x] all §9 topics
    - [x] evidence classes
    - [x] references
  - Notes: written by research sub-agent; reviewed by orchestrator

## Phase 9 — benchmark

- [x] T070 — Human ground-truth corpus (public domain, provenance)
  - Status: done
  - Depends on: —
  - Acceptance:
    - [x] pre-LLM texts
    - [x] source + license per sample
  - Notes: —
- [x] T071 — AI ground-truth corpus from several model families
  - Status: done
  - Depends on: —
  - Acceptance:
    - [x] model/tool/date/prompt hash recorded
  - Notes: —
- [x] T072 — Benchmark runner, metrics, report + CLI command
  - Status: done
  - Depends on: T032,T070,T071
  - Acceptance:
    - [x] §10.5 metrics
    - [x] latency percentiles
    - [x] tests
  - Notes: —
- [x] T073 — Initial benchmark run / documented credential blocker
  - Status: done
  - Depends on: T072
  - Acceptance:
    - [x] docs/benchmarking.md
  - Notes: offline mock run done; real-provider comparison blocked on owner API keys (docs/benchmarking.md)

## Phase 10 — browser fallback

- [x] T080 — Optional Playwright framework + evaluation ADR
  - Status: done
  - Depends on: T020
  - Acceptance:
    - [x] [browser] extra
    - [x] API package imports without playwright
    - [x] decision documented
  - Notes: framework + terms gate shipped; no site adapter because all candidates forbid automation and have APIs (ADR 0003)

## Phase 11 — performance

- [x] T090 — Timing/profiling instrumentation (per phase, ensemble, wall clock)
  - Status: done
  - Depends on: T032
  - Acceptance:
    - [x] timings in result
  - Notes: —
- [x] T091 — Measured performance pass
  - Status: done
  - Depends on: T090
  - Acceptance:
    - [x] before/after numbers or documented 'no bottleneck'
  - Notes: —

## Phase 12 — delivery

- [x] T100 — Clean-install e2e script (wheel in fresh venv, outside source tree)
  - Status: done
  - Depends on: T040
  - Acceptance:
    - [x] §18.6 steps 1-6, 8-10
  - Notes: —
- [x] T101 — Batch command (JSONL/CSV)
  - Status: done
  - Depends on: T032
  - Acceptance:
    - [x] §30 columns
  - Notes: shipped together with the benchmark CLI commit (T072)
- [x] T102 — Dockerfile + docker smoke check in pipeline
  - Status: done
  - Depends on: T100
  - Acceptance:
    - [x] image runs CLI
    - [x] pipeline stage
  - Notes: —
- [x] T103 — GHCR docker publish workflow
  - Status: done
  - Depends on: T102
  - Acceptance:
    - [x] push on main + tags
  - Notes: —
- [x] T104 — Release workflow: GitHub release + prepared PyPI Trusted Publishing
  - Status: done
  - Depends on: T004
  - Acceptance:
    - [x] tag → release with artifacts
    - [x] PyPI job manual-only
  - Notes: PyPI job manual-only (workflow_dispatch publish_pypi=true) until the owner registers the trusted publisher
- [x] T105 — Opt-in network integration workflow
  - Status: done
  - Depends on: T004
  - Acceptance:
    - [x] manual/scheduled
    - [x] only configured providers
    - [x] never on PRs
  - Notes: —
- [x] T106 — Docs: architecture, privacy, benchmarking, ADRs, .env.example
  - Status: done
  - Depends on: T032
  - Acceptance:
    - [x] privacy prominent
  - Notes: —
- [x] T107 — README with real badges, screenshot, usage
  - Status: done
  - Depends on: T040
  - Acceptance:
    - [x] §20 questions answered
  - Notes: —
- [x] T108 — Dependabot config
  - Status: done
  - Depends on: T004
  - Acceptance:
    - [x] pip + actions + docker
  - Notes: —

## Phase 13 — review and handoff

- [x] T110 — Review A: implementation correctness (/reviewBranch) + fixes
  - Status: done
  - Depends on: all
  - Acceptance:
    - [x] findings fixed or tracked
  - Notes: reviewBranch: 7 findings (raw text echo, loop-keyed gates, Pangram poll clamp, rich markup, CLI timeout precedence, weights_version, commit staging) all fixed with regression tests
- [x] T111 — Review B: adversarial end-to-end scenarios
  - Status: done
  - Depends on: all
  - Acceptance:
    - [x] §21.3 scenarios tested
  - Notes: tests/integration/test_adversarial.py covers every §21.3 scenario across all seven API adapters; clean install via e2e script; no new defects found
- [x] T112 — GitHub About + topics
  - Status: done
  - Depends on: T107
  - Acceptance:
    - [x] applied
  - Notes: —
- [x] T113 — IMPLEMENTATION_REPORT.md
  - Status: done
  - Depends on: T110,T111
  - Acceptance:
    - [x] §33 contents
  - Notes: —
- [x] T114 — GitHub release
  - Status: done
  - Depends on: T104,T113
  - Acceptance:
    - [x] release published with artifacts
  - Notes: released via scripts/release.sh; Release workflow publishes wheel+sdist, Docker workflow publishes GHCR image
- [x] T115 — Project metrics (LOC, tests, per-tier and e2e coverage, complexity) documented
  - Status: done
  - Depends on: T111
  - Acceptance:
    - [x] scripts/metrics.py with test
    - [x] docs/metrics.md + README summary
  - Notes: metrics snapshot in docs/metrics.md; e2e coverage measured in subprocesses (52.8 % alone, 98.4 % combined)
- [x] T116 — README quick start for first-time users
  - Status: done
  - Depends on: T107
  - Acceptance:
    - [x] offline mock, real key and Docker paths documented
  - Notes: quick start shipped in the same README commit as T115 (1ba61c7)
- [ ] T117 — Lizard-style automatic PyPI publishing (Trusted Publishing on tags)
  - Status: blocked
  - Depends on: T104
  - Acceptance:
    - [x] release.yml publishes from `pypi` environment via OIDC on every tag, PYPI_PUBLISH-gated
    - [x] GitHub environment `pypi` created; name `turingtongue` verified free on PyPI/TestPyPI
    - [x] docs/releasing.md documents the one-time owner setup
    - [ ] owner adds the pending publisher on PyPI and sets PYPI_PUBLISH=true
    - [ ] first upload visible under Environments → pypi
  - Notes: PyPI only lets an account owner register a publisher; this cannot be automated from the repo.
- [ ] T118 — Live validation of API adapters with real keys
  - Status: blocked
  - Depends on: T021–T054
  - Acceptance:
    - [ ] TURINGTONGUE_E2E_LIVE=1 scripts/e2e_clean_install.sh green for ≥ 3 providers
    - [ ] real benchmark run committed to docs/benchmarking.md; drift captured as fixtures
  - Notes: 2026-10-07 owner declined manual web signups ("maybe automate later"); agents must not create accounts. Sapling free trial is the cheapest first step when revisited.
- [x] T120 — Research: detector APIs usable without signup
  - Status: done
  - Depends on: T003
  - Acceptance:
    - [x] answer documented in docs/providers.md §6 (none exist; no-signup web UIs are not APIs)
  - Notes: only zero-signup route is local open-source detection (see T119).
- [ ] T119 — Optional local open-source detector (Binoculars) as experimental provider
  - Status: todo
  - Depends on: T120
  - Acceptance:
    - [ ] `[local]` extra (torch + transformers), lazy import, API-only install unaffected
    - [ ] registry entry transport `local`, enabled only when installed, labelled experimental
    - [ ] small model pair chosen by measurement; benchmark on corpus before setting its weight
    - [ ] unit tests with a fake model; opt-in `slow` test with real weights
  - Notes: proposed to the owner 2026-10-07; awaiting go-ahead (large dependency, several GB).

## Open items / blockers

- Live provider validation (T118) is blocked on owner-supplied API keys for all eight providers
  (Originality.ai and Hive additionally need enterprise/sales-provisioned accounts).
- Real-provider benchmark comparison blocked on the same keys (`docs/benchmarking.md`).
- ZeroGPT stays opt-in until a live call confirms its undocumented response shape.
- PyPI publication waits for the owner's one-time pending-publisher registration (T117).
- Corpus lacks AI_HUMAN_EDITED / HUMAN_AI_ASSISTED samples and the owner's blog posts.
- Traceability note: batch (T101) shipped inside the T072 commit; ADRs 0001/0002/0004
  inside the T080 commit; the review fix of the CLI disclaimer inside the T107 commit.
