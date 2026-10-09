#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
#
# setup_credentials.sh — store a provider's account secret after the one-time signup.
#
#   scripts/setup_credentials.sh PROVIDER [--github] [--test]
#
#   PROVIDER   sapling | copyleaks | gptzero | pangram | winston | originality | hive | zerogpt
#   --github   also store the values as GitHub repository secrets and add the provider to
#              the E2E_PROVIDERS variable (needs an authenticated `gh`)
#   --test     run scripts/live_e2e.sh PROVIDER afterwards
#
# Values are read with hidden input and written to the gitignored .env (mode 0600); they
# are never echoed, logged or passed on a command line. Signup itself stays manual —
# see `turingtongue init PROVIDER` for where to get the key.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

provider="${1:-}"
shift || true
github=false
test_after=false
for arg in "$@"; do
    case "${arg}" in
        --github) github=true ;;
        --test) test_after=true ;;
        *) echo "unknown option: ${arg}" >&2; exit 64 ;;
    esac
done

case "${provider}" in
    sapling) vars=(SAPLING_API_KEY) ;;
    copyleaks) vars=(COPYLEAKS_EMAIL COPYLEAKS_API_KEY) ;;
    gptzero) vars=(GPTZERO_API_KEY) ;;
    pangram) vars=(PANGRAM_API_KEY) ;;
    winston) vars=(WINSTON_AI_API_KEY) ;;
    originality) vars=(ORIGINALITY_API_KEY) ;;
    hive) vars=(HIVE_API_KEY) ;;
    zerogpt) vars=(ZEROGPT_API_KEY) ;;
    *) sed -n '5,17p' "$0" | sed 's/^# \{0,1\}//'; exit 64 ;;
esac

touch .env
chmod 600 .env
for var in "${vars[@]}"; do
    read -r -s -p "${var}: " value
    echo
    [[ -n "${value}" ]] || { echo "empty value for ${var}" >&2; exit 1; }
    tmp="$(mktemp)"
    grep -v "^${var}=" .env > "${tmp}" || true
    printf '%s=%s\n' "${var}" "${value}" >> "${tmp}"
    mv "${tmp}" .env
    chmod 600 .env
    if [[ "${github}" == true ]]; then
        printf '%s' "${value}" | gh secret set "${var}"
    fi
    unset value
done
echo "stored ${vars[*]} in .env"

if [[ "${github}" == true ]]; then
    current="$(gh variable get E2E_PROVIDERS 2>/dev/null || true)"
    if [[ " ${current} " != *" ${provider} "* ]]; then
        gh variable set E2E_PROVIDERS --body "$(echo "${current} ${provider}" | xargs)"
    fi
    echo "GitHub secrets set; E2E_PROVIDERS=$(gh variable get E2E_PROVIDERS)"
fi

if [[ "${test_after}" == true ]]; then
    scripts/live_e2e.sh --acquire-credential "${provider}"
fi
