#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
#
# release.sh — tag the current pyproject version as vX.Y.Z and push the tag, which
# triggers the Release (GitHub Release + assets) and Docker (GHCR) workflows.
# Refuses to run with a dirty tree, off main, or when HEAD is not pushed.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
version="$(sed -n 's/^version = "\(.*\)"$/\1/p' pyproject.toml | head -1)"
tag="v${version}"
[[ -z "$(git status --porcelain)" ]] || { echo "working tree not clean" >&2; exit 1; }
[[ "$(git branch --show-current)" == "main" ]] || { echo "not on main" >&2; exit 1; }
git fetch --quiet origin main
[[ "$(git rev-parse HEAD)" == "$(git rev-parse origin/main)" ]] || { echo "HEAD not pushed" >&2; exit 1; }
if git rev-parse -q --verify "refs/tags/${tag}" >/dev/null; then
    echo "tag ${tag} already exists" >&2
    exit 1
fi
git tag -a "${tag}" -m "TuringTongue ${tag}"
git push origin "${tag}"
echo "pushed ${tag}; watch: gh run list --workflow release.yml"
