#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
#
# commit.sh — the one way to commit in this repository.
#
#   scripts/commit.sh [--minor|--major] [--no-push] [--only PATHSPEC]... "type(scope): subject [Txxx]" [PIPELINE_ARGS...]
#
# --only limits what is staged (repeatable); without it every change in the tree is
# committed, and the staged file list is printed so unrelated files are noticed.
#
# 1. sets the version to HEAD's version bumped by patch (default), --minor (major
#    features) or --major — idempotent, so re-running after a red pipeline is safe,
# 2. runs ./localPipeline.sh (extra args are forwarded) — aborts if not green,
# 3. stages everything, commits with the given Conventional Commit message,
# 4. pushes to origin (unless --no-push).
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

part="patch"
push=true
declare -a only=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --minor) part=minor; shift ;;
        --major) part=major; shift ;;
        --no-push) push=false; shift ;;
        --only) only+=("$2"); shift 2 ;;
        *) break ;;
    esac
done
message="${1:?commit message required}"
shift

conventional='^(feat|fix|docs|test|chore|build|ci|refactor|perf|style)(\([a-z0-9._/-]+\))?!?: .+'
if [[ ! "${message}" =~ ${conventional} ]]; then
    printf 'not a Conventional Commit message: %s\n' "${message}" >&2
    exit 64
fi

current="$(uv run --quiet python scripts/bump_version.py --show)"
if git rev-parse -q --verify HEAD >/dev/null; then
    # Always derive the target from HEAD so re-runs after a red pipeline stay idempotent.
    previous="$(git show HEAD:pyproject.toml | sed -n 's/^version = "\(.*\)"$/\1/p' | head -1)"
    current="$(uv run --quiet python scripts/bump_version.py "${part}" --from-version "${previous}")"
fi
printf 'version: %s\n' "${current}"

./localPipeline.sh "$@"

if [[ ${#only[@]} -gt 0 ]]; then
    git add -- "${only[@]}" pyproject.toml uv.lock plan.md
else
    git add -A
fi
printf 'staged:\n'
git diff --cached --name-status
git commit -m "${message}"
if [[ "${push}" == true ]]; then
    git push -u origin "$(git branch --show-current)"
fi
