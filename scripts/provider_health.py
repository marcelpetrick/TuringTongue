#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""Live provider health check: one short public-domain sample per configured provider.

Usage: scripts/provider_health.py [--json]

Only providers whose credentials are present run (each gets exactly one request, a
cost guardrail). Prints a Markdown table (or JSON) of status, category, latency and
model version. Provider failures are *health findings* and do not change the exit
code; the exit code is non-zero only if our own code crashes.
"""

from __future__ import annotations

import argparse
import json
import sys

from turingtongue import Checker, Settings

SAMPLE = (
    "It was on a dreary night of November that I beheld the accomplishment of my toils. "
    "With an anxiety that almost amounted to agony, I collected the instruments of life "
    "around me, that I might infuse a spark of being into the lifeless thing that lay at "
    "my feet. It was already one in the morning; the rain pattered dismally against the "
    "panes, and my candle was nearly burnt out, when, by the glimmer of the half-"
    "extinguished light, I saw the dull yellow eye of the creature open; it breathed hard, "
    "and a convulsive motion agitated its limbs."
)
"""Mary Shelley, *Frankenstein* (1818), chapter 5 — public domain, known human text."""


def rows(checker: Checker) -> list[dict[str, object]]:
    """Run every configured real provider once and summarize the outcome."""
    configured = [
        spec.id
        for spec in checker.registry
        if spec.transport.value != "mock" and not spec.missing_credentials(checker.settings.env)
    ]
    if not configured:
        return []
    result = checker.check(SAMPLE, providers=configured)
    return [
        {
            "provider": p.provider_id,
            "status": p.status.value,
            "category": p.error.category.value if p.error else "",
            "evidence": p.normalized_evidence,
            "latency_ms": round(p.latency_ms or 0.0),
            "model_version": p.model_version or "",
        }
        for p in result.providers
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    table = rows(Checker(Settings.load()))
    if args.json:
        print(json.dumps(table, indent=2))
        return 0
    print("## Provider health (sample: Frankenstein ch. 5, known human)\n")
    if not table:
        print("No provider credentials configured — nothing was sent.")
        return 0
    print("| Provider | Status | Category | Evidence (-1 human … +1 AI) | Latency ms | Model |")
    print("| --- | --- | --- | --- | --- | --- |")
    for row in table:
        evidence = row["evidence"]
        shown = f"{evidence:+.2f}" if isinstance(evidence, float) else "—"
        print(
            f"| {row['provider']} | {row['status']} | {row['category'] or '—'} | {shown} | "
            f"{row['latency_ms']} | {row['model_version'] or '—'} |"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
