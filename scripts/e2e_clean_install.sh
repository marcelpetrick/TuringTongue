#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
#
# e2e_clean_install.sh — release-readiness check of the *built wheel* (vision §18.6).
#
#   1. create a clean Python 3.14 virtual environment outside the source tree
#   2. build sdist + wheel if dist/ is empty
#   3. install the built wheel (not the source tree)
#   4. import the package and prove it comes from site-packages (no source leakage)
#   5. run CLI --help / --version
#   6. offline smoke test through the mock provider (HUMAN, AI, exit codes)
#   7. real provider smoke tests — only with TURINGTONGUE_E2E_LIVE=1 (may cost credits)
#   8. missing credentials fail gracefully (NOT_CONFIGURED, exit 2)
#   9. JSON output carries schema_version and the documented top-level keys
#
# Usage: scripts/e2e_clean_install.sh [WHEEL]
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "${WORK}"' EXIT

fail() { printf 'E2E FAIL: %s\n' "$*" >&2; exit 1; }
step() { printf -- '--- %s\n' "$*"; }

wheel="${1:-}"
if [[ -z "${wheel}" ]]; then
    if ! compgen -G "${ROOT}/dist/*.whl" >/dev/null; then
        (cd "${ROOT}" && uv build --quiet)
    fi
    wheel="$(find "${ROOT}/dist" -name "*.whl" -printf "%T@ %p\n" | sort -nr | head -1 | cut -d" " -f2-)"
fi

step "clean Python 3.14 venv + wheel install: $(basename "${wheel}")"
uv venv --quiet --python 3.14 "${WORK}/venv"
uv pip install --quiet --python "${WORK}/venv/bin/python" "${wheel}"
BIN="${WORK}/venv/bin"
cd "${WORK}"

# Isolated environment: no developer credentials, no user config, no .env.
iso() { env -i HOME="${WORK}" PATH="${BIN}:/usr/bin:/bin" TURINGTONGUE_NO_DOTENV=1 "$@"; }

step "import from site-packages, not the source tree"
location="$(iso python -c 'import turingtongue; print(turingtongue.__file__)')"
[[ "${location}" == "${WORK}/venv/"*"/site-packages/"* ]] || fail "imported from ${location}"
[[ "${location}" != "${ROOT}"* ]] || fail "source-tree leakage: ${location}"

step "CLI help and version"
[[ "$(iso turingtongue --help)" == *"Privacy:"* ]] || fail "help lacks privacy note"
expected="$(iso python -c 'import turingtongue; print(turingtongue.__version__)')"
[[ "$(iso turingtongue --version)" == "turingtongue ${expected}" ]] || fail "version mismatch"
iso turingtongue providers >/dev/null || fail "providers command"

step "offline mock smoke test"
out="$(iso turingtongue check --text "A short sample text." -p mock)" || fail "mock exit code"
[[ "${out}" == "HUMAN" ]] || fail "expected HUMAN, got ${out}"
out="$(iso env TURINGTONGUE_MOCK_RESULT=ai turingtongue check --text "Sample." -p mock)"
[[ "${out}" == "AI" ]] || fail "expected AI, got ${out}"
verbose="$(printf 'Text from stdin.\n' | iso turingtongue check - -p mock -v)"
[[ "${verbose}" == *"Verdict: HUMAN"* ]] || fail "verbose stdin run"

step "exit codes: NO_VERDICT=2, usage=3"
set +e
iso turingtongue check --text "No providers configured." >/dev/null; rc=$?
[[ ${rc} -eq 2 ]] || fail "expected exit 2 without providers, got ${rc}"
iso turingtongue check --text "x" -p does-not-exist 2>/dev/null; rc=$?
[[ ${rc} -eq 3 ]] || fail "expected exit 3 for unknown provider, got ${rc}"
set -e

step "missing credentials fail gracefully + JSON schema"
set +e
iso turingtongue check --text "Some text." -p sapling -p gptzero --json > result.json; rc=$?
set -e
[[ ${rc} -eq 2 ]] || fail "expected exit 2 for unconfigured providers, got ${rc}"
iso python - <<'PY' || fail "JSON schema check"
import json
data = json.load(open("result.json", encoding="utf-8"))
assert data["schema_version"] == "1.0", data["schema_version"]
for key in ("package_version", "verdict", "aggregate", "input", "providers", "errors", "timing", "selection", "warnings"):
    assert key in data, key
assert data["verdict"] == "no_verdict"
assert {e["category"] for e in data["errors"]} == {"NOT_CONFIGURED"}
assert {e["provider_id"] for e in data["errors"]} == {"sapling", "gptzero"}
PY

if [[ "${TURINGTONGUE_E2E_LIVE:-0}" == "1" ]]; then
    step "LIVE provider smoke tests (may consume credits)"
    sample="It was on a dreary night of November that I beheld the accomplishment of my toils."
    for id in $(iso turingtongue providers --json | python3 -c 'import json,sys; print(" ".join(r["id"] for r in json.load(sys.stdin) if r["id"] != "mock"))'); do
        if env TURINGTONGUE_NO_DOTENV=1 "${BIN}/turingtongue" providers --json \
            | python3 -c "import json,sys; sys.exit(0 if any(r['id']=='${id}' and r['credentials_present'] for r in json.load(sys.stdin)) else 1)"; then
            set +e
            "${BIN}/turingtongue" check --text "${sample}" -p "${id}" -v; rc=$?
            set -e
            printf 'live %s: exit %s\n' "${id}" "${rc}"
        else
            printf 'live %s: skipped (no credentials)\n' "${id}"
        fi
    done
else
    step "live provider smoke tests skipped (set TURINGTONGUE_E2E_LIVE=1 to enable)"
fi

printf 'E2E clean install: OK (%s)\n' "$(basename "${wheel}")"
