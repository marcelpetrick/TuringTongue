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

1. `turingtongue init <provider> --mode e2e` → `turingtongue e2e <provider>` →
   `turingtongue cleanup <provider>`, also as `scripts/live_e2e.sh` and the `Live E2E`
   workflow. The release pipeline runs it when `vars.E2E_PROVIDERS` is set and does not
   publish if it fails.
2. Mechanisms in the owner's preference order (`credentials.Mechanism`): environment →
   sandbox → machine-issued token → OAuth → owned ephemeral identity → CI secret →
   manual. Each provider declares what it supports (`bootstrap` in providers.toml).
3. **First provider: Copyleaks** — `machine_token` + `sandbox`: per run a fresh 48 h token
   is issued via the official login API, stored 0600 in a run-scoped directory, reused,
   and deleted at cleanup; checks run in the free sandbox. Only the long-lived account
   secret (email + API key) is a CI secret.
4. Request volume is enforced technically: a transport-level budget (default 2 requests
   per `e2e` run, plus 1 login in `init`), timeout 30 s, 1 retry.
5. **Account signup is never scripted** (no website automation, CAPTCHA, email
   verification, mass accounts). Providers without an automatable path report
   `manual-credential-required` with exact instructions. A live run never falls back
   to the mock provider.
6. No owned/internal service exists, so the "owned ephemeral identity" mechanism is
   defined but unused (not faked).

## Consequences

- Copyleaks needs a one-time free signup by the owner; afterwards CI runs unattended
  and at zero cost. Sandbox runs validate plumbing, not detector accuracy.
- Other providers work through the `environment` mechanism once their key is a CI
  secret; adding machine-token/sandbox support for another provider = one bootstrapper.
