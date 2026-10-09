#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
#
# localPipeline.sh — the single quality gate for TuringTongue.
#
# GitHub Actions runs exactly this script, so "green locally" == "green in CI".
# Every stage runs even if an earlier one failed; a summary is printed at the end
# and the exit code is non-zero if any stage failed.
#
# Usage: ./localPipeline.sh [--no-docker] [--no-audit] [--fast] [--help]
#   --no-docker  skip the Docker image build/smoke stage
#   --no-audit   skip the dependency vulnerability audit (needs network)
#   --fast       only format, lint, types and tests (inner development loop)
set -u
set -o pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${ROOT_DIR}" || exit 1

RUN_DOCKER=true
RUN_AUDIT=true
FAST=false
for arg in "$@"; do
    case "${arg}" in
        --no-docker) RUN_DOCKER=false ;;
        --no-audit) RUN_AUDIT=false ;;
        --fast) FAST=true ;;
        -h|--help) sed -n '2,15p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) printf 'unknown option: %s\n' "${arg}" >&2; exit 64 ;;
    esac
done

declare -a SUMMARY=()
FAILED=0
PIPELINE_START=${SECONDS}

stage() {
    # stage NAME COMMAND... — run one pipeline stage and record its outcome.
    local name="$1"
    shift
    local start=${SECONDS}
    printf '\n\033[1;34m==> %s\033[0m\n' "${name}"
    if "$@"; then
        SUMMARY+=("PASS  ${name} ($((SECONDS - start))s)")
    else
        SUMMARY+=("FAIL  ${name} ($((SECONDS - start))s)")
        FAILED=1
    fi
}

skip() {
    SUMMARY+=("SKIP  $1 ($2)")
}

stage "sync locked environment" uv sync --locked --all-extras
stage "repository paths contain no whitespace" uv run --locked python scripts/check_paths.py
stage "license headers" uv run --locked python scripts/check_headers.py
stage "format (ruff format --check)" uv run --locked ruff format --check .
stage "lint (ruff check)" uv run --locked ruff check .
stage "types (mypy --strict)" uv run --locked mypy
if command -v shellcheck >/dev/null 2>&1; then
    stage "shell scripts (shellcheck)" shellcheck localPipeline.sh scripts/*.sh
else
    skip "shell scripts (shellcheck)" "shellcheck not installed"
fi
stage "tests + coverage >= 95%" uv run --locked pytest \
    --cov --cov-report=term-missing --cov-report=xml --cov-report=html

if [[ "${FAST}" == true ]]; then
    skip "build / e2e / docker / audit" "--fast"
else
    rm -rf dist
    stage "build sdist + wheel" uv build
    stage "package metadata (twine check)" bash -c 'uv run --locked twine check --strict dist/*'
    if [[ -x scripts/e2e_clean_install.sh ]]; then
        stage "clean wheel install e2e" scripts/e2e_clean_install.sh
    fi
    if [[ "${RUN_AUDIT}" == true ]]; then
        stage "dependency audit (pip-audit)" scripts/audit_dependencies.sh
    else
        skip "dependency audit (pip-audit)" "--no-audit"
    fi
    if [[ "${RUN_DOCKER}" == true && -x scripts/docker_check.sh ]]; then
        stage "docker build + smoke" scripts/docker_check.sh
    elif [[ -x scripts/docker_check.sh ]]; then
        skip "docker build + smoke" "--no-docker"
    fi
fi

printf '\n\033[1m==== Pipeline summary (%ss) ====\033[0m\n' "$((SECONDS - PIPELINE_START))"
printf '%s\n' "${SUMMARY[@]}"
if [[ ${FAILED} -ne 0 ]]; then
    printf '\033[1;31mPIPELINE FAILED\033[0m\n'
    exit 1
fi
printf '\033[1;32mPIPELINE GREEN\033[0m\n'
