<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# Live end-to-end tests against real providers

```bash
turingtongue init copyleaks --mode e2e      # credential bootstrap (max 1 login request)
turingtongue e2e copyleaks                  # ≤ 2 real requests, free sandbox, 30 s timeout
turingtongue cleanup copyleaks              # discard run-scoped token
scripts/live_e2e.sh copyleaks               # all three, cleanup guaranteed (trap)
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

## Make CI run it (one time, ~3 minutes)

1. Create the free Copyleaks account (link above) and copy the API key.
2. Store the account secret in GitHub — never in the repo:

   ```bash
   gh secret set COPYLEAKS_EMAIL --body "you@example.com"
   gh secret set COPYLEAKS_API_KEY            # paste the key at the prompt
   gh variable set E2E_PROVIDERS --body "copyleaks"
   ```

3. Run *Actions → Live E2E → Run workflow*. From then on it runs weekly, on demand, and
   **inside every release** (the GitHub Release and PyPI upload wait for it to pass).

Locally: put the two values in `.env` (gitignored) and run `scripts/live_e2e.sh copyleaks`.

## Guarantees

- **Budget:** a transport wrapper refuses request number `max+1` (default 2) — it is
  never sent. Plus at most one login in `init`. Timeout 30 s, 1 retry.
- **Secrets:** account secrets only in env/CI secrets; the machine-issued token lives in
  a 0700 directory / 0600 file for the run (`$TURINGTONGUE_E2E_STATE_DIR`, else
  `$XDG_RUNTIME_DIR/turingtongue-e2e`) and is deleted by `cleanup`. Copyleaks documents
  no revoke endpoint; the token expires after 48 h on its own. Nothing secret is logged
  or printed; reports are redacted.
- **No silent downgrade:** a live run never uses the mock provider; missing credentials
  fail with `manual-credential-required`.
- **Sandbox semantics:** Copyleaks sandbox classifications are simulated — the E2E run
  proves authentication, reachability, request format and response parsing, not
  detection quality (`e2e --no-sandbox` uses billed real classification).

Design and rationale: [ADR 0006](adr/0006-live-e2e-credential-bootstrap.md).
