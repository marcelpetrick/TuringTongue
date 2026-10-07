#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""Measure orchestration overhead and the effect of concurrency — fully offline.

Usage: scripts/profile_concurrency.py [--latency-ms 300] [--runs 5]

Five real adapters (Sapling, GPTZero, Winston, Originality, Hive) are pointed at
respx-mocked endpoints that answer after a fixed simulated latency. The script reports
median wall clock for ``max_concurrency`` 1 (serial), 2 and 4, the sum of provider
latencies, and the per-check overhead beyond the simulated network time.
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import sys
from typing import Any

import httpx
import respx

from turingtongue import Checker, Settings

PROVIDERS = ("sapling", "gptzero", "winston", "originality", "hive")
ENV = {
    "SAPLING_API_KEY": "k",
    "GPTZERO_API_KEY": "k",
    "WINSTON_AI_API_KEY": "k",
    "ORIGINALITY_API_KEY": "k",
    "HIVE_API_KEY": "k",
}
TEXT = "Profiling sample sentence with enough characters for every provider minimum. " * 10
RESPONSES: dict[str, Any] = {
    "https://api.sapling.ai/api/v1/aidetect": {"score": 0.2},
    "https://api.gptzero.me/v2/predict/text": {
        "documents": [{"class_probabilities": {"ai": 0.1, "human": 0.9, "mixed": 0.0}}]
    },
    "https://api.gowinston.ai/v2/ai-content-detection": {"score": 85},
    "https://api.originality.ai/api/v3/scan": {"results": {"ai": {"confidence": {"AI": 0.1}}}},
    "https://api.thehive.ai/api/v2/task/sync": {
        "status": [
            {
                "status": {"code": "0"},
                "response": {"aggregate_score": [{"class": "ai_generated", "score": 0.1}]},
            }
        ]
    },
}


def _route(latency_s: float, body: Any) -> Any:
    async def respond(request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(latency_s)
        return httpx.Response(200, json=body)

    return respond


async def measure(concurrency: int, latency_s: float, runs: int) -> dict[str, float]:
    """Median wall clock / latency sum / overhead for one concurrency setting."""
    checker = Checker(Settings(env=ENV, max_concurrency=concurrency))
    walls, sums = [], []
    with respx.mock:
        for url, body in RESPONSES.items():
            respx.post(url).mock(side_effect=_route(latency_s, body))
        for _ in range(runs):
            result = await checker.acheck(TEXT, providers=list(PROVIDERS))
            if any(not p.ok for p in result.providers):
                raise RuntimeError("profiling run had failures")
            walls.append(result.timing.wall_clock_ms)
            sums.append(result.timing.provider_latency_sum_ms)
    wall = statistics.median(walls)
    ideal = latency_s * 1000 * -(-len(PROVIDERS) // concurrency)
    return {"wall_ms": wall, "latency_sum_ms": statistics.median(sums), "overhead_ms": wall - ideal}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--latency-ms", type=float, default=300.0)
    parser.add_argument("--runs", type=int, default=5)
    args = parser.parse_args(argv)
    print(
        f"{len(PROVIDERS)} providers, simulated latency {args.latency_ms:g} ms, "
        f"median of {args.runs} runs\n"
    )
    print(
        "| max_concurrency | wall clock ms | sum of provider latencies ms | overhead vs ideal ms |"
    )
    print("| ---: | ---: | ---: | ---: |")
    for concurrency in (1, 2, 4):
        m = asyncio.run(measure(concurrency, args.latency_ms / 1000, args.runs))
        print(
            f"| {concurrency} | {m['wall_ms']:.0f} | {m['latency_sum_ms']:.0f} "
            f"| {m['overhead_ms']:.1f} |"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
