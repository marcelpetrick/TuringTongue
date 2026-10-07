<!-- SPDX-License-Identifier: GPL-3.0-or-later -->

# Provider matrix

> **Privacy reminder.** Every provider listed here is a third-party network
> service. Calling `turingtongue` with a provider enabled **sends your full
> text to that provider**. What happens to it afterwards (storage, retention,
> training use, sub-processors, jurisdiction) is governed by that provider's
> terms and privacy policy, not by this library. Read the per-provider
> "Retention / privacy" rows below before submitting sensitive material.

- **Research date / `last_verified`:** 2026-10-07 for every row unless stated otherwise.
- **Method:** fresh review of official provider documentation (API references,
  OpenAPI specs, official SDK source, official ToS / privacy pages). Third-party
  sources are used only where no official statement was found and are marked
  **(unverified, third-party)**.
- **Integration status** is a placeholder for all rows:
  `adapter implemented (contract-tested, no live credentials)`. Update it when a
  live run against real credentials has been done.
- Statements marked **AMBIGUOUS** mean the official docs contradict each other
  or are silent; adapters must handle both interpretations defensively.

This file is the user-facing matrix. Exact request/response shapes belong in
the adapters and their contract-test fixtures.

---

## 1. Summary table

| Provider | Documented API | Auth | Sync? | Max input (unit) | Min input | Languages (claimed) | Labels | Segments | Model/version field | Free tier / sandbox | Browser automation |
|---|---|---|---|---|---|---|---|---|---|---|---|
| GPTZero | Yes (OpenAPI on Stoplight) | `x-api-key` header | Sync | 50,000 characters, **provider silently truncates** | not documented | English; `multilingual=true` adds French, Spanish | human / ai / mixed (+ subclasses) | sentences (no offsets), paragraphs (legacy) | Yes (`version`, `neatVersion`) | "try for free" in docs console; API plans paid | Forbidden (ToS) |
| Pangram | Yes (docs.pangram.com, OpenAPI) | `x-api-key` header | **Async** (submit + poll) | not documented | not documented | 24 languages listed | AI / Human / Mixed; windows AI-Generated / AI-Assisted / Human Written | windows with char offsets | Yes (`version`, `model` selector) | No free API tier; pay-as-you-go credits | Forbidden (ToS s.10) |
| Sapling | Yes (OpenAPI) | `key` in body or `Authorization: Bearer` | Sync | 200,000 characters; body 4 MB | >= 300 chars recommended | English only | continuous score + `ai_fraction` | sentences with offsets, tokens | Yes (`version`) | Free trial key: 30 days, 50k chars/24h, 250k/month, **real results** | Forbidden (ToS 4.3) |
| Copyleaks | Yes | Login (email + key) -> Bearer token (48h) | Sync | 100,000 characters | 255 characters | 30 languages, auto-detect | per-section 1=Human / 2=AI | sections with char + word offsets | Yes (`modelVersion`) | `sandbox: true` free but **mock results** | Forbidden (ToS: no robots/spiders) |
| Winston AI | Yes (OpenAPI) | `Authorization: Bearer` | Sync | 150,000 characters | 300 characters (<600 unreliable) | 14 languages, auto-detect | human score 0-100 (no mixed label) | sentences (no offsets) | Yes (`version`) | 2,000 free credits on signup, real results | Forbidden except via API |
| Originality.ai | Yes | `X-OAI-API-KEY` header | Sync | not documented | not documented (see section) | multilang model, "30 languages" | AI / Original (+ AI Allowance pass logic) | blocks (text only, no offsets) | Partial (`aiModel` name only) | No; Enterprise plan required | Forbidden except via API |
| Hive | Yes (V2 task API) | `authorization: token <key>` | Sync or async | not documented for AI-text model | not documented | not documented | `ai_generated` score | provider-side 2048-char chunks with offsets | Partial (`model_version` in envelope) | Enterprise/sales project for this model | Forbidden (ToS) |
| ZeroGPT | Yes (Swagger + Postman, thin) | `ApiKey` header (+ possibly Bearer JWT) | Sync | not documented | not documented | not documented | `fakePercentage` + highlighted sentences | highlighted sentence list | No | Paid balance only | Forbidden except via API |

---

## 2. Per-provider details

### 2.1 GPTZero

| Field | Value |
|---|---|
| Name | GPTZero |
| Official docs | https://gptzero.stoplight.io/ (OpenAPI 2.0.0 "GPTZero API", project `gptzero-api`); https://gptzero.me/developers |
| Documented API | Yes. `POST https://api.gptzero.me/v2/predict/text`, plus `/v2/predict/files`, `/v3/usage-stats`, `/v2/model-versions/ai-scan`, `/v2/api-versions/ai-scan` |
| Official SDK | No official Python SDK found. Developer page advertises "ready-to-use code" snippets in 17 languages. Third-party wrappers exist (not used). |
| Auth | API key in `x-api-key` header. Key from https://app.gptzero.me/app/api |
| Free trial / sandbox | Docs say "try our API for free" via the Stoplight console; key "necessary to use the API after testing". No separate sandbox host. AMBIGUOUS how much free volume exists. |
| Sandbox real or mock | No mock sandbox documented; console calls hit production. |
| Pricing model | Word-based monthly API plans. Official pricing page only says "View Pricing / Contact Sales". Third-party (unverified): 300k words/mo $45 ... 20M words/mo $1,850. |
| Rate limits | Not documented numerically. 429 documented via example error body ("Monthy limit of 1 million words has been reached..."). |
| Min input | Not documented. |
| Max input | **50,000 characters**. "The document will be truncated to 50,000 characters" (server-side, silently). |
| Unit | Characters (code-point vs UTF-16 not specified: AMBIGUOUS). |
| Languages | English model by default; `multilingual: true` uses a multilingual model for **French and Spanish**; unsupported languages fall back to the English model. |
| Arbitrary language accepted | Yes (no rejection), but non-EN/FR/ES are scored by the English model. |
| Response fields | Top: `version`, `neatVersion`, `scanId`, `meta`, `documents[]`. Per document: `predicted_class`, `class_probabilities{human,ai,mixed}`, `confidence_score`, `confidence_category`, `completely_generated_prob`, `average_generated_prob` (internal, do not use), `document_classification`, `result_message`, `subclass`, `sentences[]`, `paragraphs[]` (legacy), `language`, `inputText`, `document_id`. |
| Binary vs mixed | Three-way: `human` / `ai` / `mixed`; subclasses `pure_ai` / `ai_paraphrased` (under ai) and `concatenated` / `polished` (under mixed). `document_classification`: `HUMAN_ONLY` / `MIXED` / `AI_ONLY`. |
| Confidence semantics | `class_probabilities[predicted_class]` "can be interpreted as the chance that our detector is correct". `confidence_category` high/medium/low; "high confidence has a less than 1% error rate". `completely_generated_prob` = P(entire document AI). Higher = more AI. |
| Segment results | Sentences: `sentence`, `generated_prob`, `class_probabilities{human,ai,paraphrased}`, `highlight_sentence_for_ai`. **No character offsets.** Paragraphs: sentence index ranges (legacy, "do not use"). |
| Model/version field | Yes: `version` (e.g. `2025-11-28-base`), `neatVersion`; request can pin `modelVersion`, `apiVersion`. |
| Retention / privacy | Developer page: "We do not store or collect the documents passed into any calls to our API." SOC 2 claimed. |
| Latency | Not documented. |
| API terms re automation | ToS (https://gptzero.me/terms-of-use.html): no access "through automated or non-human means, whether through a bot, script or otherwise"; no "spider, robot, ... scraper". The API is the sanctioned programmatic channel. |
| Web UI | Yes (gptzero.me), free tier with word caps. |
| Browser automation | **Forbidden.** |
| Integration status | adapter implemented (contract-tested, no live credentials) |
| last_verified | 2026-10-07 |

Library notes: because GPTZero truncates silently at 50,000 characters, the
adapter must apply the library's own exact-prefix rule (vision 6.2) before
sending and mark `truncated=true`, otherwise coverage would be misreported.

### 2.2 Pangram

| Field | Value |
|---|---|
| Name | Pangram (Pangram Labs) |
| Official docs | https://docs.pangram.com/ (current, Mintlify, with OpenAPI); https://pangram.readthedocs.io/ (older SDK docs, still online) |
| Documented API | Yes. Async: `POST https://text.external-api.pangram.com/task`, `GET /task/{task_id}`, `GET /models`, Bulk API, file upload, plagiarism. Legacy sync endpoints (`https://text.api.pangram.com/v3` etc.) are marked **Deprecated**. |
| Official SDK | Yes, `pip install pangram-sdk` (v1.0.0, Python >=3.10). `Pangram().predict(text, model=...)` submits and polls. |
| Auth | `x-api-key` header. SDK reads env `PANGRAM_API_KEY`. |
| Free trial / sandbox | No free API tier: API "is not included in Pangram's Free, Individual, Professional, or Teams plans"; Developers plan is pay-as-you-go. Professional plan "includes $200 monthly API credits". |
| Sandbox real or mock | No sandbox. |
| Pricing model | "$0.05 per 100 words"; Bulk API 20% discount. Bulk billable unit = "one started 1,000-word block per valid item, with a minimum of one unit per item". |
| Rate limits | Per-key configured limit, 429 on excess; numbers not documented. |
| Min input | Not documented. |
| Max input | Not documented for `/task`. Bulk: 1,000 billable units per request (413 if exceeded). |
| Unit | Words (billing); window offsets are character indices into the **returned** text. |
| Languages | Knowledge hub lists 24: English, Arabic, Chinese, Czech, Dutch, French, German, Greek, Hindi, Hungarian, Italian, Japanese, Korean, Persian, Polish, Portuguese, Romanian, Russian, Spanish, Swedish, Turkish, Ukrainian, Urdu, Vietnamese. |
| Arbitrary language accepted | Not stated. AMBIGUOUS. |
| Response fields | `stage`, `text`, `version`, `headline`, `prediction`, `prediction_short`, `fraction_ai`, `fraction_ai_assisted`, `fraction_human`, `num_ai_segments`, `num_ai_assisted_segments`, `num_human_segments`, `windows[]`, optional `dashboard_link`. |
| Binary vs mixed | Mixed-aware: `prediction_short` "AI" / "Human" / "Mixed"; windows labelled "AI-Generated" / "AI-Assisted" / "Human Written" (Pangram 4). Fractions for AI, AI-assisted, human. |
| Confidence semantics | `fraction_*` are shares of text (0-1). Window `ai_assistance_score` 0 = human, 1 = fully AI. Window `confidence` is a string High/Medium/Low. Pangram 4 adds `is_humanized`, `humanizer_score`. |
| Segment results | Windows with `start_index`, `end_index` (end-exclusive), `word_count`, `token_length`. |
| Model/version field | Yes: response `version` (e.g. "4.0"); request `model` selector from `GET /models` (e.g. `default`, `pangram-4`). SDK: "Model will be required after September 30, 2026." REST doc: omitted model "temporarily" resolves to `default`. Always send it. |
| Retention / privacy | Privacy policy: submissions "not retained, used, nor disclosed for any purpose outside of our contractual obligations"; "not used to train our AI". Bulk results kept 48 h. `public_dashboard_link` defaults to false. |
| Latency | Not documented. SDK defaults: poll every 0.5 s, overall timeout 300 s. |
| API terms re automation | ToS s.10 forbids using the Service "through the use of any engine, software, tool, agent, device, or mechanism other than the software provided by Pangram Labs". API/SDK is the sanctioned route. |
| Web UI | Yes (pangram.com), free tier exists. |
| Browser automation | **Forbidden.** |
| Integration status | adapter implemented (contract-tested, no live credentials) |
| last_verified | 2026-10-07 |

Library notes: "Pangram 4 may normalize the submitted text before inference;
window offsets refer to this returned value." Offsets must not be mapped onto
the user's original string without checking for equality first.

### 2.3 Sapling

| Field | Value |
|---|---|
| Name | Sapling AI Detector |
| Official docs | https://sapling.ai/docs/api/detector/ ; OpenAPI at https://api.sapling.ai/openapi.json |
| Documented API | Yes. `POST https://api.sapling.ai/api/v1/aidetect` |
| Official SDK | Yes (Python/JS SDKs and an MCP server); REST is trivial. |
| Auth | `key` field in JSON body, or `Authorization: Bearer <key>` (body key wins if both). Docs examples use env `SAPLING_API_KEY`. |
| Free trial / sandbox | Free trial key against production: 30 days, one key, 50,000 chars per 24 h (continuous refill), 250,000 chars/month, no credit card. |
| Sandbox real or mock | **Real** results (same production API). |
| Pricing model | Per character: $0.005 per 1,000 chars (0-10M/month), $0.00375 (10-50M), $0.0025 (50-100M). Prepaid credits (1 credit = 1 USD) or monthly billing; $5 minimum. AI-detection results are cached 3 days (repeat texts not re-billed). |
| Rate limits | Trial: 50k chars/24h, 250k/month. Subscribed: 10M chars/24h, 25M/month. Per key and per endpoint. Headers `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset` (seconds). |
| Min input | "At least 300 characters is recommended". (OpenAPI description says "at least ~50 characters for a meaningful score": AMBIGUOUS, use 300 as quality threshold.) |
| Max input | 200,000 characters per request (batch: combined length); request body max 4 MB (413). |
| Unit | Characters (CJK billed x2.5). Code-point definition not stated. |
| Languages | "The AI detector is currently trained for English only." |
| Arbitrary language accepted | Accepted (no rejection documented) but only English is supported. |
| Response fields | `score`, `ai_fraction`, `sentence_scores[]`, `text`, `token_probs[]`, `tokens[]`, `version`; optional `usage.characters`; batch: `results[]`. |
| Binary vs mixed | Continuous; `ai_fraction` = share of text in sentences scoring >= 0.5 ("flags partially AI-written documents"). No discrete mixed label. |
| Confidence semantics | `score`: "0 indicating the maximum confidence that the text is human-written, and 1 ... AI-generated". |
| Segment results | Sentence scores with `start`/`end` offsets; token-level probabilities. |
| Model/version field | Yes: response `version`; request `version` in {`20240606`, `20251027`, `20260820` (default)}. |
| Retention / privacy | Processed on AWS us-west; "Sapling also offers a no data retention option where data is never stored on disk" (contact to enable). AI detection cache 3 days for billing dedup. |
| Latency | Not documented. |
| API terms re automation | ToS 4.3 forbids "software or automated agents or scripts ... to generate automated searches, requests, or queries to (or to strip, scrape, or mine data from) the Service"; API use is the sanctioned programmatic channel and is metered by key. |
| Web UI | Yes (sapling.ai/ai-content-detector). |
| Browser automation | **Forbidden.** |
| Integration status | adapter implemented (contract-tested, no live credentials) |
| last_verified | 2026-10-07 |

### 2.4 Copyleaks (AI Text Detector)

| Field | Value |
|---|---|
| Name | Copyleaks AI Content Detector |
| Official docs | https://docs.copyleaks.com/reference/actions/writer-detector/check ; https://docs.copyleaks.com/guides/ai-detector/ai-text-detection ; https://docs.copyleaks.com/llms.txt |
| Documented API | Yes. `POST https://api.copyleaks.com/v2/writer-detector/{scanId}/check` (synchronous) |
| Official SDK | Yes: Python, JavaScript, Java, C#, PHP, Ruby. |
| Auth | Two-step: `POST https://id.copyleaks.com/v3/account/login/api` with `{email, key}` -> `access_token` valid **48 h**, then `Authorization: Bearer <token>`. Login limited to 12 requests / 15 min (5-minute block on excess). Docs use env `COPYLEAKS_EMAIL`, `COPYLEAKS_API_KEY`. |
| Free trial / sandbox | `"sandbox": true` is free. |
| Sandbox real or mock | **Mock.** "Sandbox mode is free and returns mock results." Never use sandbox output as detector evidence. |
| Pricing model | Credits. ToS 8.1: each credit = one page "containing up to 250 words". API pricing via sales. Credit balance endpoint available. |
| Rate limits | Default 10 requests/second per account; login 12 / 15 min. 429 on excess; no rate-limit headers documented. |
| Min input | 255 characters. |
| Max input | 100,000 characters. |
| Unit | Characters. |
| Languages | 30 (ISO-639-1): en, es, fr, pt, de, it, ru, pl, ro, nl, sv, cs, no, ko, ja, zh-CN, zh-TW, ar, bn, bg, hr, el, he, hi, hu, sr, th, tr, uk, vi. Auto-detect if `language` omitted. |
| Arbitrary language accepted | Not stated for unsupported languages. AMBIGUOUS. |
| Response fields | `modelVersion`, `results[]` (`classification`, `probability`, `matches[].text.chars/words.starts/lengths`), `summary{human, ai}`, `scannedDocument{scanId, totalWords, totalExcluded, credits / actualCredits, expectedCredits, creationTime}`, optional `explain`. |
| Binary vs mixed | Per section binary (1 = Human, 2 = AI); a document can contain both. `summary` gives human vs AI share. |
| Confidence semantics | `summary.ai` / `summary.human`: "the confidence in which this text was written by AI/human". Per-result `probability` = classification confidence, **deprecated, "plan to remove this value by July 2026"** (may already be absent). |
| Segment results | Sections with character and word offsets. |
| Model/version field | Yes: `modelVersion` (e.g. "v9.0"). |
| Retention / privacy | Privacy policy states submitted content of others "will be used by us to train our models" (requires consent). Retention "as long as necessary"; scan delete/purge API exists for authenticity scans. SOC 2/3, GDPR claimed. |
| Latency | Not documented ("synchronous ... results in the same API call"). |
| API terms re automation | ToS: no "automated tool (e.g., robots, spiders) to access or use our Services" except as authorized in writing; API keys are the authorized channel. ToS 11.3 forbids bot re-uploads of over-limit files. |
| Web UI | Yes (copyleaks.com/ai-content-detector). |
| Browser automation | **Forbidden.** |
| Integration status | adapter implemented (contract-tested, no live credentials) |
| last_verified | 2026-10-07 |

### 2.5 Winston AI

| Field | Value |
|---|---|
| Name | Winston AI |
| Official docs | https://docs.gowinston.ai/api-reference/v2/ai-content-detection/post ; https://docs.gowinston.ai/llms.txt ; changelog https://docs.gowinston.ai/api-reference/changelog |
| Documented API | Yes. `POST https://api.gowinston.ai/v2/ai-content-detection` (v1 also still documented). |
| Official SDK | Node only: `@winston-ai/ai-detector`. No official Python SDK. |
| Auth | `Authorization: Bearer <token>` from https://dev.gowinston.ai. Node SDK uses env `WINSTON_AI_API_KEY`. |
| Free trial / sandbox | 2,000 free credits on registration, no credit card. |
| Sandbox real or mock | No sandbox; free credits give real results. |
| Pricing model | Credits: AI text detection = 1 credit per word. Paid credit packs. |
| Rate limits | Not documented numerically; 429 `TOO_MANY_REQUESTS` exists. ToS: "Rate limits and fair use policies apply". |
| Min input | 300 characters; "Texts under 600 characters may produce unreliable results". |
| Max input | 150,000 characters per request. |
| Unit | Characters (limit); words (billing). |
| Languages | en, fr, es, pt, nl, de, pl, it, ro, id, tl, ru, bg, zh (simplified); `language: "auto"` default. |
| Arbitrary language accepted | Not documented. AMBIGUOUS. |
| Response fields | `status`, `score`, `sentences[]` (`text`, `score`), `input`, `attack_detected{zero_width_space, homoglyph_attack}`, `readability_score`, `credits_used`, `credits_remaining`, `version`, `language`. |
| Binary vs mixed | No mixed label; single human score. |
| Confidence semantics | `score` is a **human** score 0-100: "A low score means our system believes that the text is written by AI". Direction is inverted relative to most providers. |
| Segment results | Sentence list with per-sentence score; no offsets. |
| Model/version field | Yes: response `version`; request `version` ("5.0" default since 2026-09-24, "latest", older 4.x/3.x/2.0). |
| Retention / privacy | Privacy policy: "Submitted text and images are stored to generate and display analysis reports in your user dashboard"; deleted with the report/account; not used to train AI models "without your explicit consent". |
| Latency | Not documented. |
| API terms re automation | ToS: no access "through automated or non-human means, whether through a bot, script or otherwise, **except as expressly permitted through our API**". |
| Web UI | Yes (app.gowinston.ai), 14-day free trial. |
| Browser automation | **Forbidden** (API explicitly the only permitted automation). |
| Integration status | adapter implemented (contract-tested, no live credentials) |
| last_verified | 2026-10-07 |

### 2.6 Originality.ai

| Field | Value |
|---|---|
| Name | Originality.ai |
| Official docs | https://docs.originality.ai/originality-ai-api-v1 (titled "API V3"); https://docs.originality.ai/scan ; https://docs.originality.ai/llms.txt |
| Documented API | Yes. `POST https://api.originality.ai/api/v3/scan`; balance `GET /api/v3/account/balance`. Batch and URL scans also exist. |
| Official SDK | None found. |
| Auth | `X-OAI-API-KEY: <key>` header. |
| Free trial / sandbox | No. API requires the **Enterprise plan** ($179/month, or $136.58/month billed annually; 15,000 credits/month). |
| Sandbox real or mock | No sandbox. |
| Pricing model | Credits: "1 credit equals 100 words" for AI detection; AI + plagiarism together roughly doubles cost. **Auto credit top-up is ON by default** and charges the card on file. |
| Rate limits | 500 requests/minute; remaining limit exposed in response headers (header names not documented); 429 on excess. |
| Min input | Not stated in the official API docs. Third-party reports say no minimum but reduced accuracy under ~100 words (unverified). |
| Max input | Not documented. |
| Unit | Words (billing). |
| Languages | `multilang` model "supports languages other than English"; help centre: "30 Languages". |
| Arbitrary language accepted | Not documented. AMBIGUOUS. |
| Response fields | `results.properties` (scan metadata, `content`), `results.credits.used`, `results.ai{aiModel, classification{AI, Original}, confidence{AI, Original}, blocks[]}`, `results.aiAllowance{"<threshold>": {confidence, blocks}}`, plus plagiarism/readability/grammar/facts if enabled. |
| Binary vs mixed | Binary AI vs Original; "AI Allowance" thresholds (0/5/15/25/40 %) express tolerated AI share. |
| Confidence semantics | `confidence.AI` = probability-like AI score (0-1), `confidence.Original` = 1 - AI. `classification` is the 0/1 hard decision. Block `result.fake` = AI, `result.real` = human. |
| Segment results | `blocks[]` with text and fake/real scores; no offsets. |
| Model/version field | Only `aiModel` name (e.g. "lite"). Since 2026-08-25 older models (lite, turbo, academic, lite-102) are deprecated and mapped onto AI Allowance thresholds. |
| Retention / privacy | `storeScan: false` prevents storing the scan for later viewing. No other retention statement found in API docs. |
| Latency | Not documented for AI-only; plagiarism "could take up to 60 seconds". |
| API terms re automation | ToS forbids "scrape, crawl, harvest, index, or automatically extract data, scores, Outputs, or service responses **except through approved APIs**". |
| Web UI | Yes (paid). |
| Browser automation | **Forbidden.** |
| Integration status | adapter implemented (contract-tested, no live credentials) |
| last_verified | 2026-10-07 |

### 2.7 Hive (AI-Generated Text Detection)

| Field | Value |
|---|---|
| Name | Hive AI-Generated Text Detection |
| Official docs | https://docs.thehive.ai/docs/ai-generated-text-detection ; https://docs.thehive.ai/reference/ai-generated-text-detection-1 ; https://docs.thehive.ai/reference/authentication |
| Documented API | Yes. V2 task API: `POST https://api.thehive.ai/api/v2/task/sync` (or `/task/async` with callback). Model selected by the project the API key belongs to. |
| Official SDK | None for Python. |
| Auth | `authorization: token <API_KEY>` (per-project key). |
| Free trial / sandbox | V3 "Playgrounds" are self-serve with low default limits for some models (e.g. 100 req/day for moderation); availability of AI-text detection on V3 not confirmed. V2 AI-text detection needs an Enterprise project via sales. |
| Sandbox real or mock | No mock sandbox. |
| Pricing model | Per request/volume; AI-text price not listed publicly (contact sales). |
| Rate limits | Per project; FAQ: "generous default rate limits of 25-50 tasks per second, depending on the model". 429 `{return_code: 429, message: 'Project has been rate limited'}`. |
| Min input | Not documented. |
| Max input | Not documented for AI-text detection. (Text *moderation* is capped at 1,024 characters; the AI-text example processes 2,586 characters, so that cap does not appear to apply. AMBIGUOUS.) |
| Unit | Characters (provider-side chunking is per 2,048 characters). |
| Languages | Not documented (model "trained on ... essays and school assignments"). |
| Arbitrary language accepted | Not documented. |
| Response fields | Task envelope (`id`, `code`, `project_id`, `user_id`, `created_on`, `status`, `from_cache`, `metadata`); inner `response.input`, `response.aggregate_score[{class, score}]`, `response.output[{time, start_index, end_index, classes[{ai_generated: score}]}]`. |
| Binary vs mixed | Single class `ai_generated` with a score; mixed only implicit via per-chunk scores. |
| Confidence semantics | Score 0.0-1.0, "indicates whether or not the text is predicted to be AI-generated"; higher = more AI. |
| Segment results | Provider-internal 2,048-character chunks with `start_index`/`end_index`. |
| Model/version field | Envelope `input.model_version` documented in generic schema; not shown in AI-text sample. |
| Retention / privacy | FAQ: "Our default policy is to retain customer data for 14 days", adjustable (including zero) on request. |
| Latency | Not documented for AI-text. |
| API terms re automation | ToS forbids "automated agents or scripts ... to generate automated searches, requests, or queries to (or to strip, scrape, or mine data from) the Sites or the Services"; demo services "solely for evaluation purposes". |
| Web UI | Yes: free demo (hivemoderation.com/ai-generated-content-detection) and Chrome extension. |
| Browser automation | **Forbidden** (and demo is evaluation-only). |
| Integration status | adapter implemented (contract-tested, no live credentials) |
| last_verified | 2026-10-07 |

### 2.8 ZeroGPT

| Field | Value |
|---|---|
| Name | ZeroGPT Business API |
| Official docs | https://api.zerogpt.com/docs (Swagger UI), https://api.zerogpt.com/openapi.json, linked official Postman collection |
| Documented API | Yes, but thin: `POST https://api.zerogpt.com/api/detect/detectText` with `{"input_text": ...}`. No example response, few error codes. |
| Official SDK | None. |
| Auth | `ApiKey: <key>` header ("Mandatory Header" per endpoint descriptions). Swagger also marks endpoints as JWT-secured and the Postman collection sends `Authorization: Bearer <token>` from `POST /api/auth/login` (email + password). AMBIGUOUS whether the bearer token is required in addition to `ApiKey`. |
| Free trial / sandbox | No; "This is a paid service". Balance must be funded in the dashboard. |
| Sandbox real or mock | None. |
| Pricing model | Prepaid balance, per words. Official rates not published (third-party: from $0.034 per 1,000 words, unverified). |
| Rate limits | Not documented. |
| Min input | Not documented. |
| Max input | Not documented for the API (third-party: web plan limits 15k-150k characters, unverified). |
| Unit | Unknown. |
| Languages | Not documented. |
| Arbitrary language accepted | Unknown. |
| Response fields | Envelope `{success, code, data, message}`; `data` fields per schema: `textWords`, `aiWords`, `fakePercentage`, `sentences[]`, `h[]` (highlighted sentences), plus undocumented/hidden `isHuman`, `feedback`, `additional_feedback`, `id`, `cost`, etc. |
| Binary vs mixed | Percentage of AI words (`fakePercentage`), effectively a mixed-share metric. |
| Confidence semantics | `fakePercentage`: "the percentage of AI generated words inside the text" (0-100, higher = more AI). Not a probability. |
| Segment results | `h[]`: sentences "most probably generated by AI"; no offsets. |
| Model/version field | No. |
| Retention / privacy | ToS: does not use private User Content "to train, retrain, fine-tune, or otherwise develop ZeroGPT models"; processes/caches "only as reasonably necessary". |
| Latency | Not documented. |
| API terms re automation | ToS: "Automated access to ZeroGPT is permitted only through an authorized API or another method expressly approved by ZeroGPT." Scraping/crawling forbidden. |
| Web UI | Yes (zerogpt.com), free tier. |
| Browser automation | **Forbidden.** |
| Integration status | adapter implemented (contract-tested, no live credentials) |
| last_verified | 2026-10-07 |

Recommendation: ZeroGPT meets the "documented API" bar only minimally. Keep
it `enabled_by_default = false` until a live response confirms field names
and auth.

### 2.9 Other detectors noted (not integrated)

| Provider | Status | Notes |
|---|---|---|
| Resemble AI "Detect" (text) | API announced 2026-03-17 (changelog) | Text endpoint returning an AI-likelihood score; endpoint and fields not verified (docs at https://docs.resemble.ai/). Candidate for a later research pass. |
| OpenAI AI Text Classifier | Discontinued (July 2023) | From prior knowledge, not re-verified in this pass. Not a candidate. |
| Turnitin | No public self-serve API found | Institutional integrations only. Not a candidate. |

No provider in the seed list was found to have **discontinued** its API.

---

## 3. Text-size handling summary (vision section 6)

| Provider | Hard max | Unit | Provider behaviour when exceeded | Library rule |
|---|---|---|---|---|
| GPTZero | 50,000 | characters | **silently truncates** | cut exact prefix locally, mark `truncated` |
| Pangram | not documented | (words billed) | unknown | send full text; map 413/422 to `INPUT_TOO_LARGE` |
| Sapling | 200,000 (and 4 MB body) | characters | error (400/413) | exact prefix |
| Copyleaks | 100,000 (min 255) | characters | 400 | exact prefix; below 255 -> skip `INPUT_TOO_SMALL` |
| Winston | 150,000 (min 300) | characters | 400 | exact prefix; below 300 -> skip |
| Originality.ai | not documented | (words billed) | unknown | send full text |
| Hive | not documented | characters (2,048-char internal chunks) | unknown | send full text |
| ZeroGPT | not documented | unknown | unknown | send full text |

Only the character unit is ever documented. None of the providers says
whether "character" means Unicode code point or UTF-16 code unit. AMBIGUOUS for
every provider. The safe exact-prefix choice is to count UTF-16 code units
(this is never more than the code-point count) and cut only on a code-point
boundary.

---

## 4. Score direction cheat-sheet

| Provider | Primary score | Range | Higher means |
|---|---|---|---|
| GPTZero | `documents[0].class_probabilities.ai` / `completely_generated_prob` | 0-1 | AI |
| Pangram | `fraction_ai` (+ `fraction_ai_assisted`) | 0-1 | AI |
| Sapling | `score` | 0-1 | AI |
| Copyleaks | `summary.ai` | 0-1 | AI |
| Winston | `score` | 0-100 | **Human** (invert) |
| Originality.ai | `results.ai.confidence.AI` | 0-1 | AI |
| Hive | `aggregate_score[class=ai_generated].score` | 0-1 | AI |
| ZeroGPT | `data.fakePercentage` | 0-100 | AI share |

---

## 5. Browser fallback evaluation

Question: does any detector that is only available as a web UI justify
Playwright automation under vision section 13?

Findings:

1. **Every seed provider has a documented API.** None is web-only, so the
   "API first, browser fallback second" rule never needs the fallback for
   these eight.
2. **Every seed provider's terms forbid automated use of the website.**
   - GPTZero: no access "through automated or non-human means, whether through a bot, script or otherwise".
   - Pangram: no use "through ... any engine, software, tool, agent ... other than the software provided by Pangram Labs".
   - Sapling: no "automated agents or scripts ... to generate automated searches, requests, or queries".
   - Copyleaks: no "automated tool (e.g., robots, spiders) to access or use our Services".
   - Winston AI: no automated access "except as expressly permitted through our API".
   - Originality.ai: no automated extraction of "scores, Outputs, or service responses except through approved APIs".
   - Hive: no "automated agents or scripts" for queries; demos are evaluation-only.
   - ZeroGPT: "Automated access ... is permitted only through an authorized API".
3. The free web tiers also carry word/usage caps. Automating them to get
   around paid API quotas is exactly the quota evasion that vision 2.3
   prohibits.
4. Several sites use bot protection. Copyleaks returned HTTP 403 to a
   non-browser fetch during this research. Getting past that would mean stealth
   techniques, which are also out of scope.

**Conclusion:** No candidate justifies a Playwright adapter. The honest status
for browser automation is **"forbidden by terms" for all eight providers**. The
`[browser]` extra should stay unimplemented (or a skeleton with no site
adapters) until a detector is found that (a) has no API and (b) explicitly
permits automated use of its web UI in writing. Re-evaluate at the next
research pass. Record the provider's written permission in this file before
adding any browser adapter.

---

## 6. No-signup options and local detectors (reviewed 2026-10-07)

Question from the owner: is there an AI-text detection **API usable without creating an
account**? Answer: **no.** Every provider with a documented API (all eight above and the
rest of the market reviewed) requires an account and a key. Services advertised as
"free, no signup" (ZeroGPT, Copyleaks, Grammarly, Quetext, AIscan24, … — see
[fast.io overview](https://www.fast.io/resources/free-ai-detector-tools-2026.md)) are
**web UIs**, not APIs. Calling the private endpoints behind those pages would be web
scraping that their terms forbid and that vision §2.3 rules out (no quota evasion, no
session tricks). They are therefore not integrated.

Decision on account creation: the owner does not want to sign up for detector web
accounts manually; agents must not create accounts either (it accepts terms on the
owner's behalf and needs email verification). Live validation of the API adapters is
deferred until keys exist (plan T118).

The only zero-signup route is **local open-source detection** (model weights download
from Hugging Face without an account, then run offline; the text never leaves the
machine):

| Option | Method | Size / hardware | Assessment |
| --- | --- | --- | --- |
| [Binoculars](https://proceedings.mlr.press/v235/hans24a.html) (ICML 2024) | zero-shot: ratio of perplexity to cross-perplexity of two related LLMs | reference pair 2×7B (~30 GB fp16); smaller pairs possible with accuracy loss | strongest open-source detector in [independent evaluation](https://www.dsta.gov.sg/staticfile/ydsp/projects/files/reports/YDSP%20Report_Evaluation%20of%20Artificial%20Intelligence%20Text%20Detection%20Models.pdf); >90 % TPR at 0.01 % FPR on ChatGPT text (paper claim) |
| [RoBERTa OpenAI detector](https://huggingface.co/openai-community/roberta-base-openai-detector) | fine-tuned classifier on GPT-2 output | ~500 MB, CPU | outdated (GPT-2 era); weak on modern models |

Vision §2.1 allows such a provider only as an **optional, clearly experimental**
supplement after the external-API ensemble works (it does). Proposed as plan T119
(`[local]` extra, Binoculars with a small model pair, benchmarked on the corpus before
deciding its ensemble weight) — awaiting the owner's go-ahead.

## 7. Sources (accessed 2026-10-07)

GPTZero
- https://gptzero.stoplight.io/ (OpenAPI export: https://stoplight.io/api/v1/projects/gptzero/gptzero-api/nodes/open_api.json)
- https://gptzero.me/developers
- https://gptzero.me/pricing
- https://gptzero.me/terms-of-use.html

Pangram
- https://docs.pangram.com/llms.txt
- https://docs.pangram.com/api-reference/introduction
- https://docs.pangram.com/api-reference/ai-detection
- https://docs.pangram.com/api-reference/models
- https://docs.pangram.com/api-reference/deprecated-endpoints
- https://pangram.readthedocs.io/en/latest/api/rest.html
- https://pypi.org/project/pangram-sdk/ (v1.0.0)
- https://www.pangram.com/knowledge-hub/what-is-pangrams-developers-plan
- https://www.pangram.com/knowledge-hub/what-languages-does-pangram-work-on
- https://www.pangram.com/pricing
- https://www.pangram.com/terms-of-service
- https://www.pangram.com/privacy-policy

Sapling
- https://sapling.ai/docs/api/detector/
- https://api.sapling.ai/openapi.json
- https://sapling.ai/docs/api/api-access/
- https://sapling.ai/docs/rate_limits/
- https://sapling.ai/docs/sandbox/
- https://sapling.ai/docs/api/account-status/
- https://sapling.ai/docs/api/pricing/
- https://sapling.ai/docs/data/
- https://sapling.ai/tos

Copyleaks
- https://docs.copyleaks.com/reference/actions/writer-detector/check
- https://docs.copyleaks.com/reference/actions/account/login
- https://docs.copyleaks.com/reference/data-types/ai-detector/ai-text-detector-response
- https://docs.copyleaks.com/reference/actions/writer-detector/credits
- https://docs.copyleaks.com/guides/ai-detector/ai-text-detection
- https://docs.copyleaks.com/using-the-apis/rate-limits
- https://docs.copyleaks.com/reference/actions/miscellaneous/ai-detection-supported-languages
- https://copyleaks.com/termsofuse
- https://copyleaks.com/privacy-policy
- https://copyleaks.com/pricing

Winston AI
- https://docs.gowinston.ai/llms.txt
- https://docs.gowinston.ai/api-reference/introduction
- https://docs.gowinston.ai/api-reference/v2/ai-content-detection/post
- https://docs.gowinston.ai/api-reference/node-sdk
- https://docs.gowinston.ai/api-reference/changelog
- https://gowinston.ai/terms
- https://gowinston.ai/privacy-policy/

Originality.ai
- https://docs.originality.ai/llms.txt
- https://docs.originality.ai/originality-ai-api-v1
- https://docs.originality.ai/scan
- https://docs.originality.ai/credit-balance-copy-1
- https://originality.ai/pricing
- https://originality.ai/terms-and-conditions
- https://help.originality.ai/en/article/api-1a1ea3s/

Hive
- https://docs.thehive.ai/docs/ai-generated-text-detection
- https://docs.thehive.ai/reference/ai-generated-text-detection-1
- https://docs.thehive.ai/reference/authentication
- https://docs.thehive.ai/reference/submitting-via-task-api
- https://docs.thehive.ai/reference/submit-a-task-synchronously
- https://docs.thehive.ai/reference/error-codes
- https://docs.thehive.ai/reference/common-errors
- https://docs.thehive.ai/docs/frequently-asked-questions-faq
- https://docs.thehive.ai/docs/getting-started
- https://thehive.ai/pricing
- https://thehive.ai/terms-of-use

ZeroGPT
- https://api.zerogpt.com/docs
- https://api.zerogpt.com/openapi.json
- Postman collection linked from the OpenAPI description (api.postman.com collection 564519-df642187-...)
- https://www.zerogpt.com/terms-of-use

Other
- https://www.resemble.ai/changelogs/text-ai-detection-api-2026

Third-party (unverified, used only where marked)
- GPTZero API tier prices: aggregated search results (casrai.org, toolsforhumans.ai)
- Originality.ai minimum-words note: fast.io review
- ZeroGPT pricing / web limits: fast.io, stack-junkie.com
