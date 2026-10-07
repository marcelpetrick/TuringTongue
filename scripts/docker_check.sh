#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
#
# docker_check.sh — build the Docker image and smoke-test it offline.
#
#   scripts/docker_check.sh [IMAGE_TAG]     (default: turingtongue:local)
#
# Checks: image builds, version matches pyproject, runs as non-root, the mock
# provider yields HUMAN/AI with exit 0, stdin input works, and missing credentials
# give a versioned JSON NO_VERDICT with exit 2.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
tag="${1:-turingtongue:local}"
version="$(sed -n 's/^version = "\(.*\)"$/\1/p' pyproject.toml | head -1)"
fail() { printf 'DOCKER CHECK FAIL: %s\n' "$*" >&2; exit 1; }

docker build --quiet --build-arg "VERSION=${version}" -t "${tag}" . >/dev/null

[[ "$(docker run --rm "${tag}" --version)" == "turingtongue ${version}" ]] || fail "version"
[[ "$(docker run --rm --entrypoint id "${tag}" -u)" != "0" ]] || fail "runs as root"
[[ "$(docker run --rm "${tag}" check --text "Some text." -p mock)" == "HUMAN" ]] || fail "mock HUMAN"
[[ "$(docker run --rm -e TURINGTONGUE_MOCK_RESULT=ai "${tag}" check --text "x" -p mock)" == "AI" ]] \
    || fail "mock AI"
[[ "$(printf 'From stdin.\n' | docker run --rm -i "${tag}" check - -p mock)" == "HUMAN" ]] \
    || fail "stdin"
set +e
json="$(docker run --rm "${tag}" check --text "Some text." -p sapling --json)"
rc=$?
set -e
[[ ${rc} -eq 2 ]] || fail "expected exit 2 without credentials, got ${rc}"
[[ "${json}" == *'"schema_version": "1.0"'* && "${json}" == *NOT_CONFIGURED* ]] || fail "json"
printf 'Docker image %s OK (version %s)\n' "${tag}" "${version}"
