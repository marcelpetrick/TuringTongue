<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# ADR 0006 — Live E2E with a self-configuring credential bootstrap

- Status: accepted (owner decision, POC scope)
- Date: 2026-10-08

## Context

Mocked contract tests cannot prove that authentication still succeeds, endpoints are
reachable, request formats are accepted and responses still parse. The owner wants
reproducible **real-service end-to-end tests** in CI and before every release, without
someone re-creating and copying credentials by hand each time ("Confirmed Task Plan —
Self-Configuring API Credential POC").

Research (2026-10-08): **no detector provider offers machine-driven account
registration** (Sapling, GPTZero, Pangram, Winston, Originality, Hive, ZeroGPT and
Copyleaks all require a website signup; ZeroGPT's API has login/key generation but no
register endpoint). Copyleaks officially offers a login API that issues a 48 h token from
email + API key, and a free `sandbox` mode (real service, simulated classifications).

## Decision

1. `turingtongue init <provider> --mode e2e --acquire-credential` → `turingtongue e2e <provider>` →
   `turingtongue cleanup <provider>`, also as `scripts/live_e2e.sh` and the `Live E2E`
   workflow. The release pipeline runs and gates on it only when `vars.E2E_PROVIDERS` is
   set; with no configured providers, that release job is skipped.
2. Mechanisms in the owner's preference order (`credentials.Mechanism`): environment →
   sandbox → machine-issued token → existing-account API-key issuance → OAuth → owned
   ephemeral identity → CI secret → manual. Each provider declares what it supports
   (`bootstrap` in providers.toml).
3. **First provider: Copyleaks** — `machine_token` + `sandbox`: per run a fresh 48 h token
   is issued via the official login API, stored in a mode-0600 file inside a mode-0700
   run-scoped directory, reused, and deleted at cleanup; checks run in the free sandbox.
   Only the long-lived account secret (email + API key) is a CI secret.
4. **Second provider: ZeroGPT** — `account_key`: after the owner creates, verifies and
   funds an account, explicit acquisition logs in for a run-scoped JWT and issues a
   documented non-expiring API key only if `ZEROGPT_API_KEY` does not already exist. A
   new key is atomically stored in gitignored `.env` (0600); cleanup removes only the JWT
   and makes no remote-revocation claim. Undocumented success envelopes fail closed.
5. Request volume is enforced technically. Copyleaks `init` has a one-request budget;
   ZeroGPT has a two-request ceiling (login + optional key issue). Neither retries. The
   `e2e` transport has a default budget of two attempts total, including its one permitted
   retry, with a 30-second timeout.
6. **Account signup is never scripted** (no website automation, CAPTCHA, email
   verification, mass accounts). Providers without an automatable path report
   `manual-credential-required` with exact instructions. A live run never falls back
   to the mock provider.
7. Remote credential acquisition is never implicit. The CLI and shell workflow require
   `--acquire-credential`; without it, `init` can only reuse a valid run-scoped token and
   `e2e` refuses to trigger a login itself.
8. No owned/internal service exists, so the "owned ephemeral identity" mechanism is
   defined but unused (not faked).

## Consequences

- Copyleaks needs a one-time free signup by the owner; afterwards CI runs unattended
  and at zero cost. Sandbox runs validate plumbing, not detector accuracy.
- Other providers work through the `environment` mechanism once their key is a CI
  secret; adding machine-token/sandbox support for another provider = one bootstrapper.
- ZeroGPT acquisition does not automate account registration or make detection free. Its
  non-expiring key is persistent owner state; reruns reuse it and acquire only a login JWT.
- A configured Copyleaks sandbox release gate proves authentication, reachability,
  request compatibility and response parsing only. It does not satisfy the separate
  T118 real-detector validation, which still requires non-sandbox classifications from
  at least three providers plus the real benchmark and captured response drift.
