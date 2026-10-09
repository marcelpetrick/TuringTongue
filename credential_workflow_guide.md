<!-- SPDX-License-Identifier: GPL-3.0-or-later -->

# Credential workflow guide

Verified against the providers' official documentation on **2026-10-09**.

TuringTongue supports provider-approved APIs only. Every real provider requires a human to
create and, where required, verify an account. Do not automate signup forms, CAPTCHAs, email
verification, private endpoints, identity rotation, or repeated trial accounts. No supported
provider currently documents machine-driven account registration.

After that one-time human step, `scripts/setup_credentials.sh` can read credentials without
echoing them, save them in the gitignored `.env` with mode `0600`, optionally set GitHub secrets,
and deliberately start a live E2E. A live check sends the sample text to the named third party and
may consume credits. Never paste a real secret into a tracked file or a command committed to shell
history.

## Common commands

From the repository root, replace `<provider>` with one of the provider IDs below:

```bash
# Store locally; prompts are hidden.
scripts/setup_credentials.sh <provider>

# Deliberately allow documented acquisition, then run init -> E2E -> cleanup.
scripts/live_e2e.sh --acquire-credential <provider>

# Store locally and run the E2E immediately.
scripts/setup_credentials.sh <provider> --test

# Also set GitHub secrets and add the provider to E2E_PROVIDERS.
# This opts the provider into scheduled and release E2E runs.
scripts/setup_credentials.sh <provider> --github
```

For a temporary shell session instead of `.env`, use the `export` commands in the provider
section. For providers that already have a dashboard API key, the expanded lifecycle is:

```bash
uv run turingtongue init <provider> --mode e2e
uv run turingtongue e2e <provider>
uv run turingtongue cleanup <provider>
```

Remote token/key issuance is never implicit. Where TuringTongue implements an official
existing-account acquisition mechanism, it is deliberately selected with
`init <provider> --mode e2e --acquire-credential`; the provider section shows the exact command.

The default detector E2E limit is two HTTP requests. Credential acquisition has a separate hard
limit: one login request for Copyleaks and one login plus at most one key-issuance request for
ZeroGPT, with no retries. Do not use `--no-sandbox` unless you deliberately want a real,
potentially billed Copyleaks classification. Exit code `3` means a human prerequisite or explicit
acquisition step is still missing; the CLI prints the next step without printing secrets.

## Sapling (`sapling`)

**Account and key:** free 30-day production-API trial, no card advertised; real detector results.
The trial allows one key and was documented as 50,000 characters per 24 hours and 250,000 per
month.

1. Register as a human at <https://sapling.ai/user/register> and complete any verification shown.
2. Follow [API Access](https://sapling.ai/docs/api/api-access/) to open API settings and select
   **Generate Key**. The [sandbox/testing page](https://sapling.ai/docs/sandbox/) explains the
   trial limits.
3. Configure and deliberately test:

```bash
scripts/setup_credentials.sh sapling
scripts/live_e2e.sh sapling
```

Temporary environment alternative:

```bash
export SAPLING_API_KEY='paste-sapling-key-here'
scripts/live_e2e.sh sapling
```

Do not create another account when the trial expires. Add billing or replace the key through the
human dashboard. A production account can use a separately named staging/CI key.

## GPTZero (`gptzero`)

**Account and key:** an API subscription is required by the documented setup flow. The general
trial and the limited interactive documentation console do not establish a free CI/API key.

1. Create or sign in to the human account at <https://app.gptzero.me/>.
2. Subscribe to an API plan, then open <https://app.gptzero.me/app/api> and copy the API key. See
   GPTZero's [official setup instructions](https://support.gptzero.me/articles/5840144813-how-can-i-get-the-api-and-request-code-samples).
3. Configure and deliberately test:

```bash
scripts/setup_credentials.sh gptzero
scripts/live_e2e.sh gptzero
```

Temporary environment alternative:

```bash
export GPTZERO_API_KEY='paste-gptzero-key-here'
scripts/live_e2e.sh gptzero
```

The E2E calls the paid/production API; GPTZero documents no API sandbox or temporary CI key.

## Pangram (`pangram`)

**Account and key:** paid, prepaid API credits; no free API tier or sandbox was documented.
Pangram listed Pangram 4 at $0.05 per 100 words on the verification date.

1. Use the human signup/login path on the [Pangram API page](https://www.pangram.com/solutions/api).
2. Open the account's **API** tab, generate a key, and purchase enough API credits. Read the
   [official API introduction](https://docs.pangram.com/api-reference/introduction).
3. Configure and deliberately test:

```bash
scripts/setup_credentials.sh pangram
scripts/live_e2e.sh pangram
```

Temporary environment alternative:

```bash
export PANGRAM_API_KEY='paste-pangram-key-here'
scripts/live_e2e.sh pangram
```

Pangram's current API is asynchronous (submit, then poll). A run can stop at the repository's
two-request safety limit before Pangram finishes; do not switch to its deprecated endpoint to
avoid that limit.

## Copyleaks (`copyleaks`)

**Account and key:** free human signup. Copyleaks exchanges the permanent dashboard key plus email
for a 48-hour bearer token through its official login API. This is credential acquisition for an
existing account, not account registration.

1. Register as a human at <https://api.copyleaks.com/signup> and complete any required verification.
2. Open <https://api.copyleaks.com/dashboard> and copy the API key. See the official
   [authentication guide](https://docs.copyleaks.com/using-the-apis/authentication/).
3. Configure both account values and deliberately test:

```bash
scripts/setup_credentials.sh copyleaks
scripts/live_e2e.sh --acquire-credential copyleaks
```

Temporary environment alternative:

```bash
export COPYLEAKS_EMAIL='you@example.com'
export COPYLEAKS_API_KEY='paste-copyleaks-key-here'
uv run turingtongue init copyleaks --mode e2e --acquire-credential
uv run turingtongue e2e copyleaks
uv run turingtongue cleanup copyleaks
```

The default E2E uses `sandbox: true`: it is free but returns **simulated/mock classifications**.
It validates authentication, transport, and response parsing, not detector quality. A real scan
needs available credits and an explicit billed run:

```bash
scripts/live_e2e.sh --acquire-credential copyleaks -- --no-sandbox
```

Cleanup deletes the protected local token cache. Copyleaks documents no token-revocation endpoint;
the remote token expires after 48 hours.

## Winston AI (`winston`)

**Account and key:** human-created developer account with limited free starter credits and no card
advertised. Official pages disagreed between 2,000 and 2,500 starter credits, so do not depend on
an exact grant. The developer API account is separate from the ordinary Winston web-app account.

1. Open <https://dev.gowinston.ai/login>, select its human signup path, and complete verification.
2. Generate and copy the token in the developer dashboard. See the
   [official API introduction](https://docs.gowinston.ai/api-reference/introduction).
3. Configure and deliberately test:

```bash
scripts/setup_credentials.sh winston
scripts/live_e2e.sh winston
```

Temporary environment alternative:

```bash
export WINSTON_AI_API_KEY='paste-winston-key-here'
scripts/live_e2e.sh winston
```

There is no REST API sandbox. The test uses real credits. Winston's documented interactive OAuth
is scoped to its MCP server and is not a substitute for this REST detector key.

## Originality.ai (`originality`)

**Account and key:** paid **Enterprise** plan; no API sandbox or API trial was documented. Pricing
was $179/month or $136.58/month billed annually on the verification date. Automatic credit top-up
is enabled by default for API accounts.

1. Create the account and purchase Enterprise through the
   [official pricing page](https://originality.ai/pricing).
2. Follow the [V3 API setup instructions](https://docs.originality.ai/originality-ai-api-v1) to
   open the API-token dashboard and create a key.
3. Review or disable automatic credit top-up before testing, then configure and deliberately test:

```bash
scripts/setup_credentials.sh originality
scripts/live_e2e.sh originality
```

Temporary environment alternative:

```bash
export ORIGINALITY_API_KEY='paste-originality-key-here'
scripts/live_e2e.sh originality
```

The E2E is billed. Originality's current terms require prior written consent for certain competing
detector development and public comparative benchmarking; obtain clarification before publishing
comparative results.

## Hive (`hive`)

**Account and key:** Hive offers human self-service signup and advertised $1 initial credit, but
public pricing did not confirm that a new account can use the exact V2 AI-generated-text detector.
Treat model access and pricing as sales/support-confirmed until the dashboard proves entitlement.

1. Register as a human at <https://portal.thehive.ai/signup>.
2. Confirm that the **AI-generated text** model is enabled for a project. If it is absent, contact
   Hive through the [official getting-started page](https://docs.thehive.ai/docs/getting-started).
3. In that project's dashboard, create a project-specific key as described in
   [Hive authentication](https://docs.thehive.ai/reference/authentication).
4. Configure and deliberately test:

```bash
scripts/setup_credentials.sh hive
scripts/live_e2e.sh hive
```

Temporary environment alternative:

```bash
export HIVE_API_KEY='paste-hive-project-key-here'
scripts/live_e2e.sh hive
```

There is no documented sandbox for this model. The request can consume project credit. Keys can
be rotated or deleted manually and independently in the project dashboard.

## ZeroGPT (`zerogpt`)

**Account and key:** paid, prepaid API balance; no sandbox. ZeroGPT is disabled by default in
TuringTongue because its official response examples and authentication contract are incomplete;
explicitly naming it for E2E is still allowed.

1. Create and verify a human account through <https://www.zerogpt.com/>.
2. Follow the [official API pricing/getting-started page](https://www.zerogpt.com/pricing) to fund
   the API balance, generate/copy the API key, and configure the dashboard IP allowlist as needed.
   The machine API is described at <https://api.zerogpt.com/docs>.
3. Configure and deliberately test:

```bash
# This helper prompts for email, password and the existing dashboard API key.
scripts/setup_credentials.sh zerogpt
scripts/live_e2e.sh --acquire-credential zerogpt
```

Temporary environment alternative:

```bash
export ZEROGPT_EMAIL='you@example.com'
export ZEROGPT_PASSWORD='paste-account-password-here'
export ZEROGPT_API_KEY='paste-zerogpt-key-here'
uv run turingtongue init zerogpt --mode e2e --acquire-credential
uv run turingtongue e2e zerogpt
uv run turingtongue cleanup zerogpt
```

The key is documented as non-expiring and required only once. It is a permanent production
credential, not a disposable test key; do not generate a new key for every run. The documented
login/key-generation API still requires an already-created, verified, funded account and has a
thin/undocumented success response shape, so a dashboard-created key stored as a CI secret is the
recommended stable path.

TuringTongue's experimental, deliberate existing-account acquisition uses the official login and
`generateApiKey` operations. Use it only when no dashboard key is already available; never run it
per E2E. The command must fail safely if ZeroGPT's live response does not match its thin schema:

```bash
export ZEROGPT_EMAIL='you@example.com'
export ZEROGPT_PASSWORD='paste-account-password-here'
uv run turingtongue init zerogpt --mode e2e --acquire-credential
uv run turingtongue e2e zerogpt
uv run turingtongue cleanup zerogpt
```

On first acquisition, TuringTongue writes only the issued API key to the gitignored `.env` with
mode `0600`; it never prints it. The login JWT stays in the protected run-state directory and is
deleted by cleanup. Put the persistent API key in GitHub secrets before enabling scheduled CI;
do not make an ephemeral runner issue a new non-expiring key on every run.

## Offline mock (`mock`)

The mock is a fixed local test double, **not an AI detector**. It has no provider account, signup,
credential, network call, or live E2E. `turingtongue e2e mock` intentionally refuses to run it.

Use it only to verify the local CLI/package plumbing:

```bash
uv run turingtongue check --text "Any text you like." --provider mock
TURINGTONGUE_MOCK_RESULT=ai uv run turingtongue check --text "Any text." --provider mock
```

For more detail about request budgets, secret storage, cleanup, GitHub Actions, and Copyleaks
sandbox semantics, see [`docs/e2e-live.md`](docs/e2e-live.md). Provider request/response and privacy
facts are maintained in [`docs/providers.md`](docs/providers.md).
