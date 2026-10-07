#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
#
# release.sh — cut a release from main.
#
#   scripts/release.sh [--no-chart]
#
# 1. refuses to run with a dirty tree, off main, or when HEAD is not pushed;
# 2. refreshes the project history chart (scripts/history_chart.py) with a marker for
#    the upcoming release and commits it through scripts/commit.sh (full pipeline,
#    patch bump) — skip with --no-chart;
# 3. tags the resulting version as vX.Y.Z and pushes the tag, which triggers the
#    Release (GitHub Release, provenance, gated PyPI) and Docker (GHCR) workflows.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

chart=true
for arg in "$@"; do
    case "${arg}" in
        --no-chart) chart=false ;;
        *) echo "unknown option: ${arg}" >&2; exit 64 ;;
    esac
done

[[ -z "$(git status --porcelain)" ]] || { echo "working tree not clean" >&2; exit 1; }
[[ "$(git branch --show-current)" == "main" ]] || { echo "not on main" >&2; exit 1; }
git fetch --quiet origin main
[[ "$(git rev-parse HEAD)" == "$(git rev-parse origin/main)" ]] || { echo "HEAD not pushed" >&2; exit 1; }

version() { sed -n 's/^version = "\(.*\)"$/\1/p' pyproject.toml | head -1; }

if [[ "${chart}" == true ]]; then
    upcoming="$(uv run --quiet python -c \
        "from scripts.bump_version import bumped; import sys; \
print('.'.join(map(str, bumped(tuple(map(int, sys.argv[1].split('.'))), 'patch'))))" "$(version)")"
    uv run --quiet python scripts/history_chart.py --pending-release "v${upcoming}"
    if [[ -n "$(git status --porcelain docs/history)" ]]; then
        scripts/commit.sh --only docs/history "docs(history): refresh project history chart for v${upcoming} [T121]"
    fi
fi

tag="v$(version)"
if git rev-parse -q --verify "refs/tags/${tag}" >/dev/null; then
    echo "tag ${tag} already exists" >&2
    exit 1
fi
git tag -a "${tag}" -m "TuringTongue ${tag}"
git push origin "${tag}"
echo "pushed ${tag}; watch: gh run list --workflow release.yml"
