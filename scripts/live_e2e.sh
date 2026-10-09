#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
#
# live_e2e.sh — live end-to-end validation against REAL provider services.
#
#   scripts/live_e2e.sh [--acquire-credential] PROVIDER [PROVIDER...] [-- E2E_ARGS...]
#   scripts/live_e2e.sh --acquire-credential copyleaks # free sandbox, 1-2 requests
#   scripts/live_e2e.sh --acquire-credential copyleaks -- --max-requests 2 --json
#
# For each provider: explicit `turingtongue init P --mode e2e --acquire-credential`,
# `turingtongue e2e P` (budget-limited live check, default max 2 requests), and
# `turingtongue cleanup P`, which always runs (trap) so run-scoped tokens never linger.
# Account secrets come from the environment / CI secrets only. Exit code: 0 when every
# provider passed, 3 when a credential must be provisioned manually, 1 otherwise.
# A live run never falls back to the mock provider.
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 1

declare -a providers=() extra=()
acquire=false
while [[ $# -gt 0 ]]; do
    case "$1" in
        --acquire-credential) acquire=true; shift ;;
        --) shift; extra=("$@"); break ;;
        *) providers+=("$1"); shift ;;
    esac
done
[[ ${#providers[@]} -gt 0 ]] || { sed -n '5,16p' "$0" | sed 's/^# \{0,1\}//'; exit 64; }

tt() { uv run --quiet turingtongue "$@"; }
export TURINGTONGUE_E2E_STATE_DIR="${TURINGTONGUE_E2E_STATE_DIR:-$(mktemp -d)}"
# shellcheck disable=SC2317,SC2329  # invoked via trap (rule id differs by shellcheck version)
cleanup_all() { for p in "${providers[@]}"; do tt cleanup "${p}" >/dev/null || true; done; }
trap cleanup_all EXIT

overall=0
for provider in "${providers[@]}"; do
    printf '\n== %s ==\n' "${provider}"
    declare -a init_args=(init "${provider}" --mode e2e)
    if [[ "${acquire}" == true ]]; then init_args+=(--acquire-credential); fi
    tt "${init_args[@]}"; rc=$?
    if [[ ${rc} -eq 0 ]]; then
        tt e2e "${provider}" "${extra[@]}"; rc=$?
    fi
    tt cleanup "${provider}"
    if [[ ${rc} -eq 3 && ${overall} -ne 1 ]]; then
        overall=3                 # credential must be provisioned manually
    elif [[ ${rc} -ne 0 && ${rc} -ne 3 ]]; then
        overall=1                 # a real failure always wins
    fi
done
exit "${overall}"
