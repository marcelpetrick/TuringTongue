<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# ADR 0001 — Python 3.14, uv, httpx, rich, stdlib dataclasses

- Status: accepted
- Date: 2026-10-07

## Decision

- **CPython 3.14 only** (`requires-python = ">=3.14"`, `.python-version` = 3.14); no
  compatibility code for older versions.
- **uv** for environments, locking (`uv.lock` committed) and building (`uv_build` backend).
- **httpx** (async) for all provider calls; **respx** to mock it in tests.
- **rich** only for the verbose/provider tables; imported lazily by the CLI.
- **Standard-library dataclasses + enums** for the result model instead of a validation
  library: the model is produced by our own code, and defensive parsing of provider
  JSON lives in each adapter (malformed shapes → `SCHEMA_CHANGED`).
- **argparse** for the CLI (no extra dependency, custom exit codes).
- Quality gate: ruff (lint + format), mypy `--strict`, pytest + pytest-asyncio +
  pytest-cov (≥ 95 % branch coverage), twine metadata check, pip-audit, shellcheck.
- Runtime dependencies use bounded ranges (`httpx>=0.28.1,<1`, `rich>=15,<16`) so
  library consumers are not pinned to patch versions; dev tools are pinned exactly.
