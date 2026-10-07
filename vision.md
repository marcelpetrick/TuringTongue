# Vision: Multi-Provider Human-vs-AI Text Assessment Library

> **Status:** implementation vision and execution contract  
> **Audience:** autonomous/agentic software-development systems, maintainers, reviewers, and contributors  
> **Python baseline:** CPython 3.14+ only  
> **Public project/repository name:** intentionally left unspecified; do not spend implementation time on branding  
> **Primary principle:** **functionality first; correctness and observability before optimization; optimize only after measurement**

---

## 1. Executive intent

Build a reliable, local Python package that accepts a text string and asks multiple existing AI-authorship detection services whether the text appears to be human-written or AI-generated. The package is an **orchestrator and ensemble over external detectors**, not an attempt to invent a new detector in the first implementation.

The project should make existing detector services easier to use together, normalize their incompatible outputs, expose failures instead of hiding them, record latency and relevant metadata, and combine the available evidence with a transparent mixture-of-experts strategy.

The normal user experience should remain deliberately simple:

```text
HUMAN
```

or

```text
AI
```

If a meaningful result cannot be produced, the tool must say so rather than fabricate a verdict:

```text
NO_VERDICT
```

A verbose mode and a structured Python/JSON result must expose the evidence behind that one-line answer: which services ran, which transport was used, each detector's raw and normalized result, confidence where available, elapsed time, input coverage, failures, model/version metadata, and the aggregate reasoning inputs.

The tool is an **indicator**, not proof of authorship. It should help a user compare several independent signals and investigate disagreements. It must not present a commercial detector's score, or the ensemble's score, as conclusive evidence that a person did or did not use AI.

---

## 2. Non-negotiable product direction

The following requirements come directly from the project owner and override tempting alternative designs.

### 2.1 External detectors first

The first useful version MUST use existing APIs and web services. It MUST NOT begin by training, inventing, or shipping a home-grown AI detector.

A future local or heuristic detector may be explored as an optional supplementary provider, but only after the external-service aggregation architecture works end-to-end and only if it is clearly labeled as experimental.

### 2.2 API first, browser fallback second

Provider integration priority is:

1. documented official REST/HTTP API;
2. documented official SDK if it is useful and does not hide needed response information;
3. another explicitly supported machine interface;
4. permitted web-UI automation through Playwright as a fallback;
5. exclude the provider if no responsible, stable integration is possible.

Browser automation is never the architectural center of the product. It is slower, more fragile, harder to test, and more likely to break when a website changes.

### 2.3 No quota evasion or stealth abuse

The package must remain a good citizen of the services it uses.

It MUST NOT:

- rotate identities to reset free quotas;
- manufacture accounts;
- defeat CAPTCHAs;
- forge authentication;
- deliberately evade provider rate limits;
- disguise repeated automated traffic for the purpose of bypassing access controls;
- use random cookies, UUIDs, private browsing, proxies, or other session tricks to obtain service beyond the provider's intended allowance;
- rapidly fire requests in a way that can overload a provider.

An isolated browser profile, ephemeral cookie jar, or per-run UUID is acceptable when it is used for normal session isolation, test reproducibility, or because the provider's public UI legitimately requires such a client/session identifier. It must not be used to reset or bypass limits.

### 2.4 Preserve the user's text

The detector input is evidence. Do not silently alter it.

The package MUST NOT, before submission:

- rewrite or paraphrase;
- correct spelling or grammar;
- normalize punctuation;
- normalize Unicode confusables;
- strip or collapse whitespace;
- replace unusual characters;
- reflow paragraphs;
- translate;
- summarize;
- "humanize";
- inject errors;
- remove technical vocabulary;
- otherwise transform the prose in an attempt to influence a detector.

The exact Python string supplied by the caller is the canonical input. Transport encoding required by HTTP is not considered content transformation.

### 2.5 Any language, best effort

Do not reject input because the package itself thinks the language is unsupported. Send the user's text as supplied. Each provider may support a different language set. Provider limitations and rejections must be surfaced as metadata/errors, not hidden behind a local language filter.

### 2.6 Python 3.14+ only

The package targets CPython 3.14 and newer. Do not spend time supporting older Python versions.

Use current stable dependency versions at implementation time. Keep development reproducible with a lock file. Avoid unnecessary dependencies, but do not compromise clarity or robustness merely to reduce dependency count.

### 2.7 Local library first

The core product is a locally installed Python library. A CLI is also required because the desired default/verbose workflows are easiest to use and test from a terminal, but all real behavior must live in reusable library code rather than in the CLI layer.

### 2.8 Partial success is success

If six providers are requested and four work, return the four results and make the two failures visible. One broken service must not destroy the entire run.

If no provider yields usable evidence, return `NO_VERDICT` plus structured failure information.

### 2.9 Functionality first; optimize after measurement

This statement must also appear prominently in `AGENTS.md`:

> **Functionality first. Make it correct, observable, testable, and resumable. Optimize only after profiling identifies a real bottleneck.**

The first prototype may be slower than the final target. Do not introduce complex caching, batching, browser pooling, speculative parallelism, or other optimization before the basic integrations and end-to-end behavior are correct.

---

## 3. Desired user experience

### 3.1 Minimal default mode

For a normal successful check, default CLI output should be one short verdict:

```text
HUMAN
```

or:

```text
AI
```

When the system cannot responsibly decide:

```text
NO_VERDICT
```

No marketing language, essay, or long explanation belongs in default mode.

### 3.2 Verbose mode

Verbose mode should answer at least:

- which providers were selected;
- which providers actually ran;
- API/SDK/browser transport used by each provider;
- provider result and raw score semantics;
- normalized human/AI position;
- provider confidence if supplied;
- ensemble weight used;
- whether the input was complete or provider-limited;
- submitted character/word coverage when a provider limit applies;
- provider/model/version when available;
- request latency and total provider elapsed time;
- any provider cost/credit information that can be known reliably;
- retries, if any;
- failures, timeouts, rate limits, authentication problems, unsupported inputs, and provider-side errors;
- aggregate score, aggregate confidence/agreement, and final verdict;
- total wall-clock time.

Example shape only:

```text
Verdict: HUMAN
Aggregate evidence: human-leaning
Agreement: moderate
Wall clock: 4.82 s

Provider       Transport  Result       Confidence   Time     Status
GPTZero        API        HUMAN        high         0.71 s   ok
Pangram        API        HUMAN        0.91         1.26 s   ok
Sapling        API        AI           0.68         0.62 s   ok
Winston        API        —            —            2.01 s   timeout
Copyleaks      API        HUMAN        —            0.84 s   ok

Warnings:
- Winston timed out after the configured provider deadline.
- Providers disagree; inspect individual results before drawing a strong conclusion.
```

### 3.3 Provider selection

The user must be able to choose:

- an automatic default set;
- all known providers;
- one or more named providers;
- API/SDK providers only;
- browser-backed providers only;
- both API and browser providers.

Illustrative Python API:

```python
result = checker.check(text)
result = checker.check(text, providers=["gptzero", "pangram"])
result = checker.check(text, transport="api")
result = checker.check(text, providers="all", verbose=True)
```

Illustrative CLI behavior:

```text
<tool> check article.txt
<tool> check article.txt --verbose
<tool> check article.txt --provider gptzero --provider pangram
<tool> check article.txt --transport api
<tool> check article.txt --json
```

The exact command/package name is intentionally not specified in this document.

### 3.4 Structured return value

The Python library must return a typed result object. It must be serializable to a stable, versioned JSON representation.

Conceptual top-level schema:

```json
{
  "schema_version": "1.0",
  "verdict": "human",
  "aggregate": {
    "evidence_score": -0.64,
    "confidence": 0.73,
    "agreement": 0.71
  },
  "input": {
    "characters": 8421,
    "words": 1320,
    "sha256": "..."
  },
  "providers": [],
  "errors": [],
  "timing": {
    "wall_clock_ms": 4821
  }
}
```

Exact field names may evolve before 1.0, but every serialized output must include `schema_version` from the beginning.

---

## 4. Fresh provider research is a required first implementation task

The AI-detector market changes quickly. Provider capabilities, model versions, prices, limits, authentication, and terms must not be assumed from this document forever.

Before implementing or updating adapters, an agent MUST perform a fresh web review using **official provider documentation as the primary source** and update a checked-in provider matrix.

Create:

```text
docs/providers.md
```

For every candidate service, capture:

- provider name;
- official product/API documentation source;
- whether a documented API exists;
- official SDK availability;
- authentication method;
- free trial/sandbox status;
- whether a sandbox returns real or mock classifications;
- production pricing model if publicly documented;
- request rate limits if documented;
- minimum input size;
- maximum input size;
- unit of the maximum: bytes/characters/tokens/words/documents;
- supported languages as claimed by the provider;
- whether arbitrary-language input is accepted;
- response fields;
- binary vs mixed/AI-assisted classifications;
- confidence/probability semantics;
- sentence/paragraph/window/token-level results;
- model/version field availability;
- provider retention/privacy statements where publicly available;
- expected latency if documented or measured;
- API terms relevant to automation;
- web UI availability;
- whether browser automation appears explicitly permitted, forbidden, or unclear;
- integration status in this repository;
- date last verified.

### 4.1 Current seed list, to be re-verified

As of the vision's preparation date, the provider research should begin with at least:

- GPTZero;
- Pangram;
- Sapling;
- Copyleaks;
- Winston AI;
- Originality.ai;
- Hive AI text detection;
- ZeroGPT as an additional candidate if its current API and terms are sufficiently documented.

The implementation target is **at least five usable provider adapters**, preferably more when they can be implemented responsibly.

Current official documentation indicates that GPTZero, Pangram, Sapling, Copyleaks, Winston AI, Originality.ai, and Hive expose developer/API paths. Do not treat this as permanent truth; verify again when implementing.

### 4.2 Important known provider nuances to re-check

These are research seeds, not hard-coded eternal assumptions:

- Sapling currently exposes a document-level AI score, an AI fraction, sentence scores/offsets, token probabilities, model versions, and a large character limit; it recommends a non-trivial minimum input length for better accuracy.
- Pangram currently exposes human/AI/AI-assisted fractions plus window-level labels, confidence, offsets, and model selection through its API/SDK.
- GPTZero currently exposes an official text-prediction API.
- Copyleaks currently provides a synchronous text detector API; its free sandbox is useful for integration plumbing but has historically returned mock results, so sandbox output must not be used to claim detector quality.
- Winston currently exposes a developer API and advertises starter credits, but exact credit amounts and plan conditions are provider-controlled and can change.
- Originality.ai currently exposes a public API and uses minimum word-count rules that differ between web and API use.
- Hive currently returns an aggregate AI-generated classification plus segment classifications and itself performs fixed-size internal segmentation; that provider-internal behavior is not a reason for this library to pre-segment text.

Every such fact must have a `last_verified` date in `docs/providers.md`.

---

## 5. Provider adapter architecture

### 5.1 Common adapter protocol

Each provider must implement one common internal interface. The implementation should be async-first so independent providers can run concurrently, with a synchronous public façade for normal scripts.

Conceptual protocol:

```python
class Provider(Protocol):
    id: str
    transport: TransportKind

    async def detect(
        self,
        text: str,
        *,
        options: DetectionOptions,
    ) -> ProviderResult: ...
```

The core ensemble must not know provider-specific JSON structures.

### 5.2 Adapter responsibilities

A provider adapter owns:

- authentication;
- request construction;
- provider-specific input-limit handling;
- provider-specific timeout/retry hints;
- response parsing;
- raw score semantics;
- model/version extraction;
- segment extraction where present;
- rate-limit headers and retry-after handling;
- error mapping into common exceptions/statuses;
- cost/credit metadata where possible;
- redaction of secrets;
- optional safe raw-response capture for debugging/tests.

It does NOT own the final ensemble verdict.

### 5.3 Provider registry

Maintain machine-readable provider metadata used by both the library and CLI.

At minimum:

```text
id
name
transport
requires_credentials
enabled_by_default
supports_segments
supports_mixed_label
supports_model_version
known_min_input
known_max_input
limit_unit
known_languages
adapter_status
last_verified
```

Provider metadata that changes frequently must be easy to update without rewriting the entire ensemble.

---

## 6. Text fidelity and provider size limits

### 6.1 Full text is preferred

Always attempt to submit the complete text in one provider request when that provider supports it. Do not locally chunk a document and then pretend the result is equivalent to a single full-document scan.

### 6.2 No silent truncation

Provider size limits create tension with the requirement to preserve the user's input. Therefore size handling must be explicit and deterministic.

Recommended initial behavior:

1. If the full text fits the provider's documented limit, send it unchanged.
2. If it exceeds a hard provider limit and the provider accepts a maximal prefix, submit the **largest exact prefix** that safely fits the provider's documented unit/limit.
3. Mark the provider result as `truncated=true` and report coverage.
4. Never normalize or rewrite the retained prefix.
5. Never silently treat a truncated provider result as full-document evidence.
6. Reduce that provider's ensemble weight proportionally or according to a documented coverage policy.
7. If a safe exact-prefix boundary cannot be determined, skip that provider with `INPUT_TOO_LARGE` rather than guessing.

Examples of exact-prefix rules:

- character limit: slice the Python string by Unicode code points only if provider documentation explicitly defines characters that way;
- byte limit: encode using the actual transport encoding and cut only on a valid character boundary;
- word limit: find the substring boundary ending at the provider-defined maximum word count while preserving every character before that boundary exactly.

Do not implement semantic summarization or representative sampling as a fallback.

### 6.3 Provider-internal segmentation is allowed

If a provider itself splits a submitted text into windows/chunks, preserve and expose those returned results. This is provider behavior, not local preprocessing.

---

## 7. Result model

### 7.1 Provider result

Each provider result should retain both normalized and provider-native information.

Suggested fields:

```text
provider_id
provider_name
transport
status
raw_label
raw_score
raw_confidence
score_semantics
normalized_evidence
normalized_confidence
model
model_version
segments
input_characters
submitted_characters
input_coverage
truncated
latency_ms
attempt_count
rate_limit_metadata
credit_or_cost_metadata
warning_codes
error
checked_at
```

`normalized_evidence` should use a documented common orientation, for example:

```text
-1.0 = maximally human-leaning evidence
 0.0 = neutral / inconclusive
+1.0 = maximally AI-leaning evidence
```

Do not call this a universal probability unless calibration has demonstrated that interpretation.

### 7.2 Error result

Failures are data. A provider failure record should include:

```text
provider_id
category
message_safe_for_user
http_status_if_any
retryable
attempt_count
latency_ms
```

Never include API secrets, bearer tokens, cookies, or sensitive request headers in errors.

### 7.3 Common error categories

At minimum:

```text
NOT_CONFIGURED
AUTHENTICATION_FAILED
AUTHORIZATION_FAILED
RATE_LIMITED
QUOTA_EXHAUSTED
TIMEOUT
NETWORK_ERROR
SERVICE_UNAVAILABLE
PROVIDER_ERROR
INVALID_RESPONSE
SCHEMA_CHANGED
INPUT_TOO_SHORT
INPUT_TOO_LARGE
UNSUPPORTED_INPUT
UNSUPPORTED_LANGUAGE
BROWSER_AUTOMATION_FAILED
TERMS_NOT_PERMITTED
UNKNOWN_ERROR
```

Avoid pretending to know whether a provider intentionally blocked the client versus suffering an outage unless the provider response actually says so.

---

## 8. Mixture-of-experts ensemble

### 8.1 Concept

Treat each external detector as an expert with:

- an opinion/evidence direction;
- a confidence signal, if the provider exposes one;
- an empirically determined reliability weight;
- applicability constraints based on text length/language/provider limits;
- possible abstention or failure.

Do not use simple majority vote as the final design because not all detectors are equally reliable and not all provider confidence values mean the same thing.

### 8.2 Version 0 weighting

Before enough benchmark evidence exists:

- default provider reliability weights to equal values;
- normalize only what can be defended from provider documentation;
- preserve unknown confidence as unknown rather than inventing one;
- treat provider abstention/inconclusive results as near-zero evidence;
- reduce weight for partial-input/truncated results;
- expose the formula in documentation and code comments.

Do not assign a higher weight merely because a vendor advertises a higher headline accuracy number.

### 8.3 Evidence calculation

A defensible first implementation may use:

```text
provider_vote_weight =
    reliability_weight
  * confidence_factor
  * applicability_factor
  * input_coverage_factor
```

and:

```text
ensemble_evidence =
    sum(normalized_evidence_i * provider_vote_weight_i)
    / sum(provider_vote_weight_i)
```

The exact confidence mapping must be provider-specific and documented. If provider score semantics are unclear, use categorical evidence rather than pretending the score is calibrated.

### 8.4 Verdict mapping

Normal default output should be simple. Internally, preserve more nuance.

Recommended public verdicts:

```text
HUMAN
AI
NO_VERDICT
```

Recommended internal diagnostics:

```text
strongly_human
human_leaning
borderline
conflicted
ai_leaning
strongly_ai
```

`NO_VERDICT` should be used when:

- no providers return usable evidence;
- total effective vote weight is below a minimum threshold;
- the ensemble is exactly or effectively tied inside a calibrated deadband;
- evidence is so contradictory that a binary answer would be misleading according to the configured policy.

The default output remains one line; verbose/JSON explains why.

### 8.5 Agreement is separate from confidence

Track at least three distinct concepts:

1. provider-native confidence;
2. ensemble evidence strength;
3. cross-provider agreement.

Do not collapse these into one fake percentage.

For example, two highly confident detectors on opposite sides can yield high individual confidence but low agreement and low ensemble certainty.

### 8.6 Calibration over time

The benchmark corpus should eventually produce reliability weights. The weighting configuration must be versioned and reproducible.

Do not overfit a tiny corpus. Until there is enough representative data, equal weighting is preferable to pseudo-scientific precision.

---

## 9. Human-vs-AI writing research documentation

Create and maintain:

```text
docs/human-vs-ai-signals.md
```

This is a required deliverable, not optional background reading.

Its purpose is to document what is actually known about cues used in AI-text detection and where those cues fail. It must distinguish:

- peer-reviewed or otherwise credible evidence;
- provider claims;
- plausible heuristics;
- folklore that should not be treated as established fact.

Topics should include, where evidence supports them:

- token predictability and perplexity;
- burstiness and variation in sentence length/structure;
- lexical diversity;
- repetition and phrase reuse;
- syntactic regularity;
- discourse structure and transition patterns;
- over-structured prose;
- formulaic introductions/conclusions;
- punctuation tendencies;
- hedging and assistant-style phrasing;
- model-specific stylistic artifacts;
- paraphrasing and "humanization" effects;
- mixed human/AI text;
- grammar/style tools and post-editing;
- translation effects;
- technical/academic/formulaic writing;
- non-native writing;
- very short samples;
- code, quotations, lists, tables, and boilerplate;
- Unicode substitutions/confusables and other evasion artifacts;
- detector drift as models and providers change.

The document must emphasize that many of these features are correlations, not proof of authorship.

**Do not turn this document into a home-grown detector in the initial implementation.** It exists to inform interpretation, tests, and future research.

---

## 10. Benchmark and calibration corpus

### 10.1 Purpose

Create a small, transparent benchmark corpus sufficient to catch obvious integration/ensemble mistakes and begin comparing providers. It is not intended to become a giant academic dataset in the first version.

### 10.2 Human ground truth

Include clearly pre-generative-AI material where licensing permits, for example:

- public-domain literature such as Mary Shelley's *Frankenstein*;
- other public-domain prose from long before modern LLMs;
- carefully selected historical snapshots with verifiable publication dates;
- optional personal blog material from before 2022 when provided by the project owner.

Historical literature is useful as a false-positive sanity check but is not representative of all modern human writing. Document that limitation.

If Wikipedia snapshots are used:

- capture an exact historical revision ID/date;
- comply with attribution/license requirements;
- do not simply scrape current text and label it "pre-AI";
- store provenance alongside the sample.

Do not bundle the owner's private or copyrighted blog text into a public repository without explicit permission.

### 10.3 AI ground truth

Generate a modest set of intentionally AI-written texts using currently available agent/model tooling, including at least several different model families when accessible.

Codex- and Claude-Code-driven generation may be used, but record the actual underlying model/tool and date where available.

For every generated sample record:

```text
sample_id
label
model/tool
model version if known
prompt or prompt hash
creation date
generation settings if exposed
human edits after generation
```

Create at least a few distinct styles/topics rather than ten near-identical essays.

### 10.4 Optional mixed samples

Useful categories include:

```text
HUMAN_RAW
HUMAN_GRAMMAR_CHECKED
AI_RAW
AI_HUMAN_EDITED
HUMAN_AI_ASSISTED
MIXED
```

These are valuable because real-world writing often lies between the extremes.

### 10.5 Benchmark metrics

Per provider and ensemble, calculate where meaningful:

- accuracy;
- balanced accuracy;
- precision;
- recall/sensitivity;
- specificity;
- false-positive rate;
- false-negative rate;
- F1;
- abstention/NO_VERDICT rate;
- coverage;
- confusion matrix;
- ROC-AUC only when score semantics support it;
- calibration/Brier-style measures only when probability interpretation is defensible;
- median and percentile latency;
- provider failure rate;
- estimated cost/credits per sample and per 1,000 words where known.

The project should care particularly about **false positives on genuinely human text**.

### 10.6 Benchmark separation

Do not use exactly the same tiny benchmark both to tune weights and claim performance. Even for a small project, preserve a simple train/calibration vs holdout concept if weights are learned.

---

## 11. Timeouts, concurrency, rate limiting, and performance

### 11.1 Target

The eventual normal wall-clock target is to finish a multi-provider check in approximately one minute or less under ordinary network conditions.

This is a target, not a reason to sacrifice functionality in the first prototype.

### 11.2 Async concurrency

Independent API providers should run concurrently once correctness is established. Browser providers may need stricter concurrency limits because they are much heavier.

Provide:

- a global concurrency limit;
- per-provider concurrency limits;
- configurable provider timeouts;
- an optional overall run deadline.

### 11.3 Rate limits

Respect documented provider limits and `Retry-After` headers.

Do not send a burst merely because async makes it easy.

### 11.4 Retry policy

Retry only transient failures and only a small bounded number of times.

Potentially retry:

```text
408
429 (respect Retry-After)
500
502
503
504
selected network/DNS/connect timeouts
```

Normally do not retry:

```text
400
401
403
invalid input
unsupported input
known exhausted quota without reset information
```

Use exponential backoff with jitter.

### 11.5 Profiling

Instrument at least:

- provider request elapsed time;
- browser startup/navigation/submit/result wait when relevant;
- parsing/normalization time when measurable;
- ensemble calculation time;
- total wall-clock time.

Benchmark reports should eventually include mean and p50/p90/p95/p99 latency where sample counts make those percentiles meaningful.

Remember that:

```text
sum(individual_provider_latency) != total_wall_clock_latency
```

when providers execute concurrently.

---

## 12. Credentials and configuration

### 12.1 Secrets

Use environment variables as the primary runtime mechanism for API keys.

Examples may follow the obvious provider naming pattern, such as:

```text
GPTZERO_API_KEY
PANGRAM_API_KEY
SAPLING_API_KEY
COPYLEAKS_API_KEY
WINSTON_API_KEY
ORIGINALITY_API_KEY
HIVE_API_KEY
ZEROGPT_API_KEY
```

Verify actual conventions when implementing.

For local development, `.env` loading may be supported as a convenience, but:

- `.env` must be gitignored;
- examples contain placeholders only;
- production behavior must not depend on a committed secrets file.

### 12.2 Missing credentials

Missing credentials are not a crash for an ensemble run.

Behavior:

- automatic mode: run providers that are usable/configured and record others as unavailable where useful;
- explicitly requested provider: return a structured `NOT_CONFIGURED` failure if its credential is absent;
- `--verbose` and JSON must make this visible.

### 12.3 Config file

A small optional user config file may be added if it simplifies provider enable/disable settings, timeout defaults, and weight overrides. Do not store secrets there by default.

---

## 13. Browser automation fallback

### 13.1 Tooling

Use Playwright unless fresh research finds a compelling reason not to.

Browser support must be an optional dependency/extra so API-only users are not forced to install Chromium and browser tooling.

Conceptually:

```text
pip install <package>[browser]
```

### 13.2 Isolation

Use a fresh browser context/private profile for a run unless a provider legitimately requires persisted user state.

Do not persist cookies by default.

### 13.3 Site-specific adapters only

Do not build a generic "scrape any AI detector" mechanism. Each browser provider gets a specific adapter with:

- selectors;
- input strategy;
- result parser;
- explicit wait conditions;
- timeout;
- screenshots/HTML capture only in opt-in debug mode;
- terms/automation review date.

### 13.4 Fragility isolation

Browser adapters must be separated from API adapters in tests and dependency groups. A website redesign must not break importing or using the API-only package.

---

## 14. Privacy and user responsibility

The package sends user-provided text to third-party services over the network. Once submitted, processing and retention are subject to those providers' policies and are outside this package's control.

This must be stated clearly in:

- README;
- package documentation;
- provider documentation;
- CLI help for first-use/privacy-related commands where practical.

Do not add intrusive interactive consent prompts to normal library calls. Calling the networked check function is an intentional action by the user. The documentation must make the consequence clear.

By default, the package itself should not persist submitted full text to disk.

Logs must avoid printing the full input unless explicit debug behavior requests it.

Saved benchmark data is a separate, deliberate workflow.

---

## 15. Cost and credits

Some providers are paid, some have trials, some have free web interfaces, and these conditions change.

Where a provider exposes or publishes reliable billing/credit information, capture:

```text
credits_used
credits_remaining
estimated_cost
currency
billing_unit
```

Do not invent cost when it cannot be calculated reliably.

Future useful options:

```text
max_cost
free_only
skip_paid
```

But these are secondary to getting provider integration correct.

A "free" web UI must not be treated as an unlimited API.

---

## 16. Package architecture

A suggested structure; agents may adjust details while preserving separation of concerns:

```text
src/
  <module>/
    __init__.py
    client.py
    config.py
    models.py
    ensemble.py
    errors.py
    registry.py
    timing.py

    providers/
      __init__.py
      base.py
      gptzero.py
      pangram.py
      sapling.py
      copyleaks.py
      winston.py
      originality.py
      hive.py
      zerogpt.py

    browser/
      __init__.py
      base.py
      playwright_support.py

    normalization/
      labels.py
      scores.py
      confidence.py
      limits.py

    benchmark/
      corpus.py
      runner.py
      metrics.py
      report.py

    cli/
      main.py
      output.py

tests/
  unit/
  contract/
  integration/
  browser/
  benchmark/
  fixtures/

docs/
  providers.md
  human-vs-ai-signals.md
  architecture.md
  privacy.md
  benchmarking.md
  adr/

AGENTS.md
plan.md
pyproject.toml
README.md
```

Do not choose a public-facing project name merely to fill the placeholder. Use the repository's existing name if one already exists. If none exists, keep branding/publishing as an explicitly blocked release detail while continuing implementation under a neutral internal module name.

---

## 17. Dependency and packaging policy

### 17.1 Python

```text
requires-python = ">=3.14"
```

Do not add compatibility code for 3.13 or older.

### 17.2 Modern tooling

A reasonable modern baseline is:

- `pyproject.toml` as the authoritative project configuration;
- `uv` for environment/lock/workflow management unless the repository already standardizes another modern tool;
- `httpx` for async HTTP;
- typed models using dataclasses or a current stable validation library where it clearly helps;
- `pytest`;
- `pytest-asyncio` or current equivalent when needed;
- HTTP mocking such as `respx` or an equivalent compatible tool;
- `ruff` for linting/formatting;
- a current static type checker (`mypy`, `pyright`, or repository standard);
- Playwright as an optional extra only.

Agents may make final dependency choices based on Python 3.14 compatibility and current maintenance status. Record meaningful architecture choices in ADRs.

### 17.3 Reproducibility

Commit a development lock file. Keep published library dependency constraints reasonable so consumers are not unnecessarily pinned to exact patch versions.

---

## 18. Testing strategy

### 18.1 Unit tests

No network required. Cover:

- normalization;
- ensemble math;
- verdict thresholds;
- weight handling;
- truncation/coverage calculations;
- Unicode boundary behavior;
- error mapping;
- config loading;
- serialization/schema version;
- secret redaction;
- timeout/retry policy decisions;
- provider selection;
- partial success;
- no-verdict behavior.

### 18.2 Contract tests

For every provider, keep sanitized response fixtures based on documented/observed responses. Contract tests must verify parser behavior without spending credits.

Provider response drift is expected; every discovered drift bug should receive a regression fixture.

### 18.3 Integration tests

Real network tests are opt-in and credential-aware.

They must not run on arbitrary external pull requests and must not consume paid credits unexpectedly.

Recommended markers:

```text
unit
contract
integration
network
paid
browser
slow
```

### 18.4 Sandbox semantics

A provider sandbox that returns fake/mock classifications can validate authentication/request/response plumbing, but it cannot validate detector accuracy. Tests and docs must say so explicitly.

### 18.5 Browser tests

Keep browser tests separate and slow. They should provide useful diagnostics when selectors change, but avoid persisting page content that contains user text or secrets.

### 18.6 End-to-end clean-install test

Before declaring a release-ready result:

1. create a clean Python 3.14 environment;
2. build wheel and sdist;
3. install the built wheel, not the source tree;
4. import the package;
5. run CLI help;
6. run a fixture/mock provider smoke test;
7. run real provider smoke tests where credentials are available;
8. verify missing credentials fail gracefully;
9. verify JSON schema output;
10. verify no source-tree import leakage.

---

## 19. CI/CD and GitHub

### 19.1 Continuous integration

GitHub Actions should run on pull requests and pushes.

Because Python 3.14 is the baseline, do not maintain an obsolete multi-version matrix just for appearance. Test the supported baseline/current CPython 3.14 environment; add newer supported versions when they actually exist and are intended to be supported.

Required checks:

```text
format
lint
type-check
unit tests
contract tests
coverage
package build
package metadata validation
```

### 19.2 Network integration workflow

Provide a separate manual and/or scheduled workflow using repository secrets.

Requirements:

- only run a provider if its credentials exist;
- clear cost/credit guardrails;
- no secrets in output;
- do not fail unrelated pull requests because a commercial provider is down;
- record provider-health regressions distinctly from code regressions.

### 19.3 Release workflow

Prepare a release workflow for eventual PyPI publication:

- run full quality gates;
- build sdist/wheel;
- validate artifacts;
- use PyPI Trusted Publishing/OIDC rather than a long-lived PyPI token when possible;
- create a GitHub release from a version tag;
- attach artifacts as appropriate.

Because the public package/repository name is deliberately omitted from this vision, do not publish to PyPI until the owner supplies/finalizes the distribution name. The pipeline itself should be ready.

### 19.4 README badges

Only show badges that correspond to real workflows/services. Typical badges:

- CI;
- PyPI version after publication;
- Python 3.14+;
- coverage if a coverage service is actually configured;
- license;
- typing/lint status if meaningful.

Do not add decorative broken badges.

---

## 20. README and user documentation

The README should quickly answer:

1. What does the package do?
2. What does it **not** prove?
3. Where is text sent?
4. How do I install it?
5. How do I configure provider credentials?
6. How do I run the simplest check?
7. How do I see verbose details?
8. How do I select providers/API-only/browser?
9. What happens when a provider fails?
10. How can I reproduce/benchmark results?

A dedicated section must explain that external provider results are probabilistic and may be wrong, especially for short, formulaic, heavily edited, translated, mixed, technical, or otherwise atypical text.

---

## 21. Agentic development execution model

This repository is explicitly intended to be buildable by an autonomous software-development system without the owner watching every step.

### 21.1 Orchestrator responsibility

One lead/orchestrator agent owns:

- reading this vision;
- creating `AGENTS.md` and `plan.md` before substantive implementation;
- decomposing work;
- assigning independent work to sub-agents;
- preventing conflicting edits;
- integrating sub-agent work;
- running global quality gates;
- ensuring every completed task is traceable to an atomic commit;
- performing final end-to-end verification;
- leaving the repository in a resumable, understandable state even if some providers remain blocked by credentials or terms.

### 21.2 Mandatory sub-agent use

Use sub-agents where tasks are genuinely separable, especially:

- provider landscape research;
- individual provider adapters;
- benchmark corpus/research;
- tests/contract fixtures;
- documentation review;
- security/privacy review;
- final code review.

Do not create sub-agents merely to look busy. Parallel work should reduce wall-clock time without creating merge chaos.

Where supported, use separate branches/worktrees for sub-agents working concurrently on code.

### 21.3 Review roles

At least two review passes should occur before final completion:

**Review A — implementation correctness**

- architecture boundaries;
- API behavior;
- error handling;
- type correctness;
- test quality;
- secret handling;
- provider terms/rate-limit compliance.

**Review B — adversarial/end-to-end review**

- clean install;
- missing credentials;
- one provider down;
- several providers disagree;
- short text;
- huge text;
- Unicode/confusable input;
- non-English input;
- provider schema variation;
- timeouts;
- all providers fail;
- JSON stability;
- CLI default remains simple.

Review findings must be fixed or explicitly recorded as open items in `plan.md`; do not silently ignore them.

### 21.4 Do not wait unnecessarily for the owner

The agentic system should make reasonable engineering decisions when the vision provides enough direction. Do not repeatedly ask the owner minor implementation questions.

Escalate only when genuinely blocked by something that cannot be responsibly inferred, such as:

- a paid credential is required and absent;
- terms explicitly require owner acceptance;
- final public project name is required for publication;
- a legally consequential licensing decision conflicts with existing repository material.

---

## 22. `AGENTS.md` requirements

Create `AGENTS.md` near the start of work. It is an operational guide for all agents.

It must include at least:

### Core mantra

> **Functionality first. Make it correct, observable, testable, and resumable. Optimize only after profiling identifies a real bottleneck.**

### Working rules

- read `vision.md`, `AGENTS.md`, `plan.md`, `git status`, and recent `git log` before modifying code;
- never overwrite unrelated uncommitted user work;
- one logical concern per commit;
- use Conventional Commits;
- include the plan task ID in each commit message;
- update tests in the same logical task as the behavior they verify;
- do not mark a task done until its acceptance criteria pass;
- keep network/paid/browser tests opt-in;
- never commit credentials;
- never hide provider failures;
- API first, browser fallback;
- no quota evasion;
- do not preprocess the submitted text;
- document provider facts with verification date;
- update `plan.md` continuously so another agent can resume after a crash;
- run the smallest relevant test set during development and the full gate before integration/release;
- after a sub-agent returns, the orchestrator reviews the diff and tests instead of trusting the summary blindly.

---

## 23. `plan.md`: traceability and crash recovery

`plan.md` is mandatory and must be created before substantive implementation.

It is not a static project plan. It is the durable execution ledger that allows another agent to resume after an interruption.

### 23.1 Task format

Every task gets a stable ID and checkbox.

Recommended shape:

```markdown
- [ ] T021 — Implement Sapling provider adapter
  - Status: todo
  - Depends on: T010, T012
  - Acceptance:
    - [ ] official API behavior documented
    - [ ] adapter implemented
    - [ ] secrets redacted
    - [ ] contract fixtures added
    - [ ] unit/contract tests pass
  - Notes: —
```

When work starts:

```markdown
- [ ] T021 — Implement Sapling provider adapter
  - Status: in_progress
  ...
```

When done, the task and acceptance checks are updated **in the same logical commit as the implementation whenever practical**:

```markdown
- [x] T021 — Implement Sapling provider adapter
  - Status: done
  ...
```

### 23.2 Commit traceability without self-referential hashes

Do not attempt to write a commit's own hash into the file that is part of that same commit; that is self-referential and unnecessary.

Instead, include the task ID in the conventional commit message:

```text
feat(provider): add Sapling adapter [T021]
```

Then task-to-commit mapping is recoverable with Git history:

```text
git log --grep='T021'
```

This keeps the commit atomic and the plan traceable.

### 23.3 Crash-recovery protocol

On startup or resumption, an agent MUST:

1. read `vision.md`;
2. read `AGENTS.md`;
3. read `plan.md`;
4. inspect `git status`;
5. inspect recent `git log --oneline`;
6. identify any `in_progress` tasks;
7. inspect the working tree before discarding anything;
8. resume or safely roll back the incomplete task;
9. update the task notes if the previous run left ambiguous state;
10. continue from the next dependency-ready task.

Never assume an uncommitted working tree is disposable after a crash.

### 23.4 Plan contents

At minimum the plan must contain phases for:

- repository/tooling foundation;
- current provider research;
- core result/error/config models;
- provider registry;
- at least five provider adapters;
- API/provider contract tests;
- ensemble normalization;
- weighting/agreement/verdict logic;
- minimal CLI;
- verbose/JSON output;
- browser fallback framework if justified;
- human-vs-AI signals documentation;
- benchmark corpus;
- benchmark runner/metrics;
- performance instrumentation;
- privacy/security review;
- CI;
- release pipeline;
- README/docs;
- end-to-end review;
- release-readiness report.

---

## 24. Git discipline

### 24.1 Atomic commits

Each commit handles one logical topic. Do not create giant "implement everything" commits.

Good examples:

```text
chore(repo): initialize Python 3.14 project [T001]
docs(research): add provider capability matrix [T006]
feat(core): add provider result model [T011]
feat(provider): add GPTZero adapter [T022]
test(provider): add GPTZero response contracts [T023]
feat(ensemble): add weighted evidence aggregation [T034]
feat(cli): add verbose provider report [T041]
docs: document human-vs-ai signals and caveats [T052]
ci: add Python 3.14 quality workflow [T061]
```

A provider adapter and its tightly coupled unit tests may live in one commit if that is the smallest coherent change. Large contract-fixture work may deserve its own commit.

### 24.2 Conventional Commits

Use Conventional Commits consistently. Typical types:

```text
feat
fix
test
docs
chore
build
ci
refactor
perf
```

Do not use `perf` until a measured optimization actually occurs.

### 24.3 Clean history

Before final handoff:

- no temporary debug commits if the workflow permits clean-up safely;
- no secrets;
- no generated browser profiles;
- no unexplained binary blobs;
- no failing tests knowingly hidden by blanket ignores.

---

## 25. Suggested implementation phases

The orchestrator should turn these into finer-grained `plan.md` tasks.

### Phase 0 — inspect existing repository

- preserve existing work;
- identify current package/repo configuration;
- confirm Python 3.14 availability;
- create/update `vision.md`, `AGENTS.md`, `plan.md` as appropriate.

### Phase 1 — provider research

- fresh official-doc research;
- create provider matrix;
- identify at least five responsible API-first targets;
- note credential blockers and provider-specific limits;
- decide which web-only candidates, if any, warrant Playwright work.

### Phase 2 — project foundation

- `pyproject.toml`;
- source layout;
- test layout;
- lock file;
- lint/format/type/test configuration;
- initial CI skeleton.

### Phase 3 — domain model

- typed provider result;
- typed aggregate result;
- errors/statuses;
- serialization/schema version;
- provider metadata registry;
- configuration/credential lookup.

### Phase 4 — first three API adapters

Preferred starting candidates, subject to fresh research:

1. Sapling;
2. GPTZero;
3. Pangram.

These are useful architectural reference points because they expose different output shapes and useful detailed signals.

Implement each with fixtures/tests before moving on.

### Phase 5 — ensemble and default verdict

- provider normalization;
- equal initial reliability weights;
- confidence/applicability/coverage factors;
- disagreement metric;
- binary default verdict plus `NO_VERDICT`;
- fully inspectable internals.

### Phase 6 — CLI and JSON

- default one-line mode;
- verbose mode;
- provider selection;
- transport selection;
- JSON output;
- timing display;
- useful exit codes without treating `AI` as a shell error.

### Phase 7 — provider expansion to five or more

Subject to current API viability and credentials, add adapters such as:

- Copyleaks;
- Winston AI;
- Originality.ai;
- Hive;
- ZeroGPT if properly documented and responsible to automate.

Goal: at least five maintained adapters, more if feasible within the run.

### Phase 8 — human/AI signals research document

Complete `docs/human-vs-ai-signals.md` using credible research and provider documentation, clearly separating evidence from speculation.

### Phase 9 — benchmark corpus and runner

- small known-human corpus;
- small known-AI corpus from multiple contemporary models/tools;
- provenance metadata;
- optional mixed samples;
- metrics and reports;
- initial empirical comparison;
- do not overfit weights.

### Phase 10 — browser fallback, only where justified

If there is a worthwhile provider with no official API and current terms permit automation:

- add optional Playwright support;
- implement site-specific adapter;
- isolate browser tests;
- measure added wall-clock cost.

If no such provider is worth the fragility, explicitly document that browser fallback was evaluated and deferred. Do not add scraping merely to satisfy a checkbox.

### Phase 11 — performance pass

Only now:

- profile wall-clock behavior;
- run API providers concurrently;
- tune timeouts;
- avoid accidental request bursts;
- evaluate caching only if needed;
- compare before/after numbers.

### Phase 12 — CI/release/docs polish

- complete CI;
- optional/scheduled integration tests;
- PyPI Trusted Publishing workflow prepared;
- README;
- privacy docs;
- contributor docs;
- badges tied to real workflows.

### Phase 13 — adversarial final review

Run the scenarios in Section 21.3, fix defects, rerun all gates, and produce a final implementation report.

---

## 26. CLI exit behavior

Do not use shell exit code `1` merely because the content verdict is AI. AI vs human is data, not process success/failure.

Suggested semantics:

```text
0 = command executed and produced a valid HUMAN/AI verdict
2 = command executed but produced NO_VERDICT
3 = invalid user configuration/input/arguments
4 = unexpected internal failure
```

Exact codes may be adjusted, but the principle must remain.

---

## 27. Security requirements

- never log API keys;
- redact authorization headers in exceptions and recorded fixtures;
- use TLS verification normally;
- set finite network timeouts;
- cap response/body sizes where practical;
- validate external JSON defensively;
- do not execute provider-returned content;
- keep browser profiles temporary;
- do not commit browser storage/cookies;
- dependency vulnerability scanning should be enabled where practical;
- GitHub secret scanning/Dependabot may be enabled if repository settings permit;
- avoid passing secrets to untrusted pull-request workflows.

---

## 28. Observability and diagnostics

A user trying to understand why a run failed should not need to attach a debugger.

Provide structured diagnostics for:

- provider chosen/skipped;
- credential present/missing without exposing value;
- start/end timestamps;
- timeout/retry count;
- HTTP status where safe;
- provider parser version/adapter version if useful;
- text size and submitted coverage;
- provider/model version;
- browser phase failures;
- aggregate inclusion/exclusion reason.

Optional debug logs should use the standard Python logging system rather than ad-hoc prints from library code.

---

## 29. Reproducibility and provider drift

External detector behavior changes over time. Therefore a result should record, when available:

```text
provider
provider model/version
adapter/package version
check timestamp
input hash
provider options
```

Do not overwrite historical benchmark results silently when a provider model changes.

A text classified HUMAN today and AI in six months is a meaningful observation, not necessarily a software bug.

---

## 30. Future batch/blog analysis

After the core single-text library works, support batch/corpus analysis so the owner can evaluate historical blog posts.

Desired future behavior:

```text
<tool> batch path/to/posts --jsonl results.jsonl
<tool> batch path/to/posts --csv results.csv
```

Useful output columns:

```text
file/id
date if known
characters
words
verdict
ensemble evidence
agreement
providers succeeded
providers failed
latency
estimated cost
provider/model versions
```

Do not make this feature block the first working library.

Longitudinal analysis can later examine:

- score drift over time;
- detector disagreements;
- false positives on known self-written text;
- effect of grammar correction;
- technical vs non-technical prose;
- length effects;
- provider model-version changes.

---

## 31. Explicit non-goals for the initial implementation

Do not let scope drift turn this into another project.

Initial non-goals:

- training a new transformer/classifier;
- inventing an opaque proprietary detector;
- proving authorship;
- deanonymizing authors;
- identifying the exact LLM that generated text unless a provider explicitly returns such a signal and it is presented as that provider's claim;
- rewriting text to evade detectors;
- "humanizer" functionality;
- grammar checking or spell checking;
- plagiarism detection except where a provider response happens to include it and it is ignored/separated from the core feature;
- document editing;
- a hosted SaaS service;
- account farming;
- CAPTCHA bypass;
- proxy rotation;
- stealth scraping designed to avoid enforcement;
- old-Python compatibility;
- premature micro-optimization.

---

## 32. Definition of done for a strong first autonomous delivery

The agentic implementation run should aim to return a repository in which:

- [ ] Python 3.14+ is the documented and enforced baseline.
- [ ] `AGENTS.md` exists and contains the functionality-first rule and crash-recovery workflow.
- [ ] `plan.md` exists, uses stable task IDs, and accurately reflects completed/open work.
- [ ] fresh provider research exists in `docs/providers.md`.
- [ ] at least five provider adapters are implemented if current APIs/terms make that feasible.
- [ ] at least three adapters have been exercised end-to-end with genuine responses or clearly documented credential blockers.
- [ ] provider contract fixtures/tests exist.
- [ ] the package does not preprocess ordinary submitted text.
- [ ] provider size-limit behavior is explicit and tested.
- [ ] any language can be passed through without a local pre-filter.
- [ ] partial provider failures return partial results.
- [ ] all-provider failure returns `NO_VERDICT` and useful errors.
- [ ] default CLI output is intentionally minimal.
- [ ] verbose output explains every provider attempt and timing.
- [ ] JSON output is versioned.
- [ ] provider selection and API-vs-browser selection exist.
- [ ] weighted mixture-of-experts aggregation exists and is documented.
- [ ] initial weights are not based solely on vendor marketing claims.
- [ ] provider confidence, ensemble evidence, and agreement are distinct concepts.
- [ ] timeout/retry/rate-limit behavior is bounded and tested.
- [ ] no quota-evasion behavior exists.
- [ ] privacy disclaimer is prominent.
- [ ] secrets are redacted.
- [ ] `docs/human-vs-ai-signals.md` exists and discusses known cues and failure modes.
- [ ] a small provenance-rich benchmark corpus exists.
- [ ] the benchmark can compare provider accuracy/false positives/latency where credentials permit.
- [ ] timing/profiling is implemented.
- [ ] the codebase passes lint/format/type/unit/contract gates.
- [ ] a clean wheel install has been tested.
- [ ] GitHub Actions exist for quality checks.
- [ ] network/paid tests are isolated from normal PR CI.
- [ ] a PyPI release workflow using Trusted Publishing is prepared but final publication waits for the public package name.
- [ ] README is complete and contains only real badges.
- [ ] at least two review passes have occurred and findings were resolved or tracked.
- [ ] every completed task is represented by an atomic Conventional Commit containing its task ID.
- [ ] the working tree is clean or any intentional remaining state is documented.

If fewer than five providers can responsibly be integrated because of credentials, discontinued APIs, or terms, the run is not considered a failure **provided the blocker is documented precisely, the architecture supports adding them, and every feasible provider has been pursued**.

---

## 33. Final handoff report expected from the autonomous system

At the end of the run, create a concise `IMPLEMENTATION_REPORT.md` containing:

- what was built;
- what remains open;
- provider table with status;
- real vs mocked/sandbox-tested providers;
- tests run and results;
- clean-install result;
- benchmark summary;
- wall-clock/profile observations;
- known limitations;
- credential/terms blockers;
- any deviations from this vision and why;
- exact next tasks from `plan.md`;
- release readiness status.

The report should allow the owner to understand the result without reading the entire Git history.

---

## 34. Guiding philosophy

This project should be useful precisely because it does **not** pretend AI-authorship detection is certain.

A good result is not the most dramatic verdict. A good result is one that:

- preserves the submitted text;
- queries several independent systems responsibly;
- records exactly what happened;
- exposes disagreement and failure;
- distinguishes provider claims from normalized evidence;
- can be reproduced later;
- can survive provider API changes;
- can be resumed by another development agent after a crash;
- and gives the user a simple answer without hiding the machinery that produced it.

The first milestone is not a clever new detector. The first milestone is a **working, maintainable, API-first ensemble over existing detectors**. The research on human-vs-AI linguistic signals is required context and documentation, but it is supplementary to that core objective.

Build the straightforward thing first. Verify it end-to-end. Measure it. Then optimize it.
