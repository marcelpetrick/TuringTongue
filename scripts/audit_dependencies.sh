#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
#
# audit_dependencies.sh — scan every locked dependency (incl. extras and dev tools)
# for known vulnerabilities with pip-audit. Needs network access to the PyPI
# advisory database. Exits non-zero when a vulnerability is found.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
audit_dir="$(mktemp -d)"
trap 'rm -rf "${audit_dir}"' EXIT
requirements="${audit_dir}/requirements.txt"
uv export --locked --no-hashes --no-emit-project --all-extras --all-groups > "${requirements}"
uvx --quiet --python 3.14 pip-audit==2.10.1 --cache-dir "${audit_dir}/cache" \
    --strict --disable-pip --no-deps -r "${requirements}"
