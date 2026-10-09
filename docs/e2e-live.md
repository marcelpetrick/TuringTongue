<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# Live end-to-end tests against real providers

```bash
turingtongue init copyleaks --mode e2e --acquire-credential  # explicit; max 1 login
turingtongue e2e copyleaks                  # ≤ 2 provider attempts, free sandbox, 30 s timeout
turingtongue cleanup copyleaks              # discard run-scoped token
scripts/live_e2e.sh --acquire-credential copyleaks  # all three; cleanup guaranteed
```

Exit codes: `0` passed/ready · `1` failed (auth, network, schema, budget) · `3`
`manual-credential-required` (a one-time account secret is missing — the message says
exactly what to do).

## What is automated, per provider

| Provider | Mechanisms (`bootstrap`) | One-time manual step | Per run (automated) |
| --- | --- | --- | --- |
| **Copyleaks** | environment, machine_token, sandbox | free signup at <https://api.copyleaks.com/signup>, API key from <https://api.copyleaks.com/dashboard> | fresh 48 h token via official login API; check in the free **sandbox** (no cost) |
| Sapling | environment | account + trial key in the dashboard | 1–2 real requests with the key |
| GPTZero, Pangram, Winston, Originality, Hive, ZeroGPT | environment | account + key (some paid/enterprise) | 1–2 real requests with the key |

No provider offers machine-driven account registration (checked 2026-10-08), so the
account itself is always created once by the owner. Signup flows are never scripted.

**Evaluated and not adopted — ZeroGPT key minting.** ZeroGPT's official API has
`POST /api/auth/login` (email + password → JWT) and `GET /api/auth/generateApiKey`. Its
own documentation says the key is "only required once" and "doesn't expire", so it is not
a temporary credential; minting one per run could invalidate keys used elsewhere, and the
response schema is undocumented (no example), and detection calls need a paid balance.
It would not remove the one-time signup either. Revisit if ZeroGPT documents expiring or
scoped keys.

## After the one-time signup: one command

```bash
scripts/setup_credentials.sh sapling --github --test     # or: copyleaks
```

Paste the key when asked (hidden input). It is written to the gitignored `.env` (0600),
optionally stored as GitHub secrets with the provider added to `E2E_PROVIDERS`, and the
live E2E runs immediately.

## Make CI run it manually (alternative to the script)

1. Create the free Copyleaks account (link above) and copy the API key.
2. Store the account secret in GitHub — never in the repo:

   ```bash
   gh secret set COPYLEAKS_EMAIL --body "you@example.com"
   gh secret set COPYLEAKS_API_KEY            # paste the key at the prompt
   gh variable set E2E_PROVIDERS --body "copyleaks"
   ```

3. Run *Actions → Live E2E → Run workflow*. From then on it runs weekly, on demand, and
   inside releases while `E2E_PROVIDERS` remains non-empty (the GitHub Release and PyPI
   upload wait for it to pass). If `E2E_PROVIDERS` is unset or empty, the release skips
   the live-E2E job and is not gated by provider validation.

Locally: put the two values in `.env` (gitignored) and run
`scripts/live_e2e.sh --acquire-credential copyleaks`.

## Guarantees

- **Budget:** `init` sends at most one login request and never retries it. During `e2e`,
  a transport wrapper refuses provider attempt number `max+1` (default 2), so the one
  permitted retry is included in that limit. Timeout is 30 seconds. Reported request
  counts are the actual outbound attempts.
- **Secrets:** account secrets only in env/CI secrets; the machine-issued token lives in
  a 0700 directory / 0600 file for the run (`$TURINGTONGUE_E2E_STATE_DIR`, else
  `$XDG_RUNTIME_DIR/turingtongue-e2e`) and is deleted by `cleanup`. Copyleaks documents
  no revoke endpoint; the token expires after 48 h on its own. Nothing secret is logged
  or printed; reports are redacted.
- **No silent downgrade:** a live run never uses the mock provider; missing credentials
  fail with `manual-credential-required`.
- **No implicit acquisition:** without `--acquire-credential`, `init` may reuse a valid
  run-scoped token but never calls the login API; `e2e` refuses to acquire one implicitly.
- **Sandbox semantics:** Copyleaks sandbox classifications are simulated — the E2E run
  proves authentication, reachability, request format and response parsing, not
  detection quality (`e2e --no-sandbox` uses billed real classification).

## What this does not complete

The conditional release gate and Copyleaks sandbox validate live integration plumbing.
They do not complete ledger task T118: real detector validation still requires
non-sandbox classification runs for at least three providers, a committed real-provider
benchmark, and regression fixtures for any response drift found there.

Design and rationale: [ADR 0006](adr/0006-live-e2e-credential-bootstrap.md).
