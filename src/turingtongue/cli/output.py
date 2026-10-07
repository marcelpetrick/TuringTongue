# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""Rendering of results for humans (verbose report, provider list)."""

from __future__ import annotations

from collections.abc import Mapping

from rich.console import Console
from rich.table import Table
from rich.text import Text

from turingtongue.models import CheckResult, ProviderResult, Verdict
from turingtongue.registry import Registry

DISCLAIMER = (
    "Detector results are probabilistic indicators, not proof of authorship. "
    "The text was sent to the third-party services listed above."
)
_VERDICT_STYLE = {
    Verdict.HUMAN: "bold green",
    Verdict.AI: "bold red",
    Verdict.NO_VERDICT: "bold yellow",
}


def _num(value: float | None, fmt: str = "{:.2f}") -> str:
    return "—" if value is None else fmt.format(value)


def _ms(value: float | None) -> str:
    return "—" if value is None else f"{value / 1000:.2f} s"


def provider_label(result: ProviderResult) -> str:
    """Provider's own lean as HUMAN / AI / MIXED, derived from normalized evidence."""
    if result.normalized_evidence is None:
        return "—"
    if result.normalized_evidence > 0.05:
        return "AI"
    if result.normalized_evidence < -0.05:
        return "HUMAN"
    return "MIXED"


def _agreement_word(agreement: float | None) -> str:
    if agreement is None:
        return "n/a"
    if agreement >= 0.8:
        return "high"
    if agreement >= 0.4:
        return "moderate"
    return "low"


def render_verbose(result: CheckResult, console: Console) -> None:
    """Explain every provider attempt, the ensemble inputs and the timing."""
    agg = result.aggregate
    console.print(Text(f"Verdict: {result.verdict.display}", style=_VERDICT_STYLE[result.verdict]))
    console.print(
        f"Aggregate evidence: {agg.diagnostic.value.replace('_', '-')}"
        f" (score {_num(agg.evidence_score, '{:+.2f}')}, -1 human … +1 AI)"
    )
    console.print(
        f"Agreement: {_agreement_word(agg.agreement)} ({_num(agg.agreement)})"
        f"   Ensemble confidence: {_num(agg.confidence)}"
        f"   Effective weight: {agg.effective_weight:.2f}"
    )
    console.print(
        f"Wall clock: {_ms(result.timing.wall_clock_ms)}"
        f"   (sum of provider latencies {_ms(result.timing.provider_latency_sum_ms)},"
        f" ensemble {result.timing.ensemble_ms:.2f} ms)"
    )
    console.print(
        f"Input: {result.input.characters} characters, {result.input.words} words,"
        f" sha256 {result.input.sha256[:16]}…"
    )
    sel = result.selection
    console.print(
        f"Providers selected ({sel.get('mode')}, transport {sel.get('transport')}):"
        f" {', '.join(map(str, sel.get('selected', []))) or 'none'}"
    )
    console.print()

    table = Table(show_lines=False, header_style="bold")
    for column in (
        "Provider",
        "Transport",
        "Result",
        "Raw score",
        "Evidence",
        "Confidence",
        "Weight",
        "Coverage",
        "Model",
        "Time",
        "Tries",
        "Status",
    ):
        table.add_column(column, overflow="fold")
    for p in result.providers:
        status = "ok" if p.error is None else p.error.category.value.lower()
        model = " ".join(x for x in (p.model, p.model_version) if x) or "—"
        table.add_row(
            p.provider_name,
            p.transport.value.upper(),
            provider_label(p),
            _num(p.raw_score, "{:.3g}"),
            _num(p.normalized_evidence, "{:+.2f}"),
            str(p.raw_confidence) if p.raw_confidence is not None else "—",
            _num(p.vote_weight),
            "—" if p.error else f"{p.input_coverage:.0%}" + (" (cut)" if p.truncated else ""),
            model,
            _ms(p.latency_ms),
            str(p.attempt_count),
            status,
        )
    if result.providers:
        console.print(table)
    else:
        console.print("No provider ran.")

    details: list[str] = []
    for p in result.providers:
        if p.score_semantics:
            details.append(f"{p.provider_name}: score = {p.score_semantics}")
        if p.weight_factors:
            factors = ", ".join(f"{k} {v:.2f}" for k, v in p.weight_factors.items())
            details.append(f"{p.provider_name}: weight factors {factors}")
        if p.cost is not None:
            details.append(f"{p.provider_name}: cost/credits {_mapping(_slots(p.cost))}")
        if p.rate_limit is not None:
            details.append(f"{p.provider_name}: rate limit {_mapping(_slots(p.rate_limit))}")
        if p.segments:
            details.append(
                f"{p.provider_name}: {len(p.segments)} {p.segments[0].kind}-level results"
            )
    skipped: Mapping[str, str] = sel.get("skipped", {})
    details.extend(f"{pid}: skipped — {why}" for pid, why in skipped.items())
    if details:
        console.print("\nDetails:")
        for line in details:
            console.print(f"- {line}", markup=False)
    console.print("\nEnsemble reasoning:")
    for reason in agg.reasons:
        console.print(f"- {reason}", markup=False)
    if result.warnings:
        console.print("\nWarnings:")
        for warning in result.warnings:
            console.print(f"- {warning}", markup=False)
    console.print(f"\n[dim]{DISCLAIMER}[/dim]")


def _slots(obj: object) -> dict[str, object]:
    return {name: getattr(obj, name) for name in getattr(obj, "__slots__", ())}


def _mapping(values: Mapping[str, object]) -> str:
    return ", ".join(f"{k}={v}" for k, v in values.items() if v is not None) or "none reported"


def render_providers(registry: Registry, env: Mapping[str, str], console: Console) -> None:
    """Show the registry with credential presence (never the values)."""
    table = Table(header_style="bold")
    for column in (
        "ID",
        "Name",
        "Transport",
        "Default",
        "Credentials",
        "Max input",
        "Verified",
        "Status",
    ):
        table.add_column(column, overflow="fold")
    for spec in registry:
        missing = spec.missing_credentials(env)
        if not spec.credential_env:
            creds = "not needed"
        elif missing:
            creds = "missing: " + ", ".join(missing)
        else:
            creds = "set"
        limit = f"{spec.known_max_input:,} {spec.limit_unit.value}" if spec.known_max_input else "—"
        table.add_row(
            spec.id,
            spec.name,
            spec.transport.value,
            "yes" if spec.enabled_by_default else "no",
            creds,
            limit,
            spec.last_verified,
            spec.adapter_status,
        )
    console.print(table)
    console.print(
        "[dim]Set the listed environment variables (or a local .env) to enable providers. "
        "Checks send your text to these third-party services.[/dim]"
    )
