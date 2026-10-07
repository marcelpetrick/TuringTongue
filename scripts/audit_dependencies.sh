#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
#
# audit_dependencies.sh — scan every locked dependency (incl. extras and dev tools)
# for known vulnerabilities with pip-audit. Needs network access to the PyPI
# advisory database. Exits non-zero when a vulnerability is found.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
requirements="$(mktemp)"
trap 'rm -f "${requirements}"' EXIT
uv export --locked --no-hashes --no-emit-project --all-extras --all-groups > "${requirements}"
uvx --quiet pip-audit --strict --disable-pip --no-deps -r "${requirements}"
