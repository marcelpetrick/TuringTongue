# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""Rendering of results for humans (verbose report, provider list)."""

from __future__ import annotations

from collections.abc import Mapping

from rich.console import Console
from rich.table import Table
from rich.text import Text

from turingtongue.models import CheckResult, ErrorCategory, ProviderResult, TransportKind, Verdict
from turingtongue.registry import Registry

DISCLAIMER = "Detector results are probabilistic indicators, not proof of authorship."
SENT_NOTE = "The text was sent to these third-party services: {names}."
NOT_SENT_NOTE = "The text was not sent to any third-party service."
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


_COLUMNS = (
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
)


def _header_lines(result: CheckResult) -> list[str]:
    agg = result.aggregate
    sel = result.selection
    selected = ", ".join(map(str, sel.get("selected", []))) or "none"
    return [
        f"Aggregate evidence: {agg.diagnostic.value.replace('_', '-')}"
        f" (score {_num(agg.evidence_score, '{:+.2f}')}, -1 human … +1 AI)",
        f"Agreement: {_agreement_word(agg.agreement)} ({_num(agg.agreement)})"
        f"   Ensemble confidence: {_num(agg.confidence)}"
        f"   Effective weight: {agg.effective_weight:.2f}",
        f"Wall clock: {_ms(result.timing.wall_clock_ms)}"
        f"   (sum of provider latencies {_ms(result.timing.provider_latency_sum_ms)},"
        f" ensemble {result.timing.ensemble_ms:.2f} ms)",
        f"Input: {result.input.characters} characters, {result.input.words} words,"
        f" sha256 {result.input.sha256[:16]}…",
        f"Providers selected ({sel.get('mode')}, transport {sel.get('transport')}): {selected}",
    ]


def _row(p: ProviderResult) -> tuple[str, ...]:
    coverage = "—" if p.error else f"{p.input_coverage:.0%}" + (" (cut)" if p.truncated else "")
    return (
        p.provider_name,
        p.transport.value.upper(),
        provider_label(p),
        _num(p.raw_score, "{:.3g}"),
        _num(p.normalized_evidence, "{:+.2f}"),
        "—" if p.raw_confidence is None else str(p.raw_confidence),
        _num(p.vote_weight),
        coverage,
        " ".join(x for x in (p.model, p.model_version) if x) or "—",
        _ms(p.latency_ms),
        str(p.attempt_count),
        "ok" if p.error is None else p.error.category.value.lower(),
    )


def _provider_table(result: CheckResult) -> Table:
    table = Table(show_lines=False, header_style="bold")
    for column in _COLUMNS:
        table.add_column(column, overflow="fold")
    for p in result.providers:
        # Text() so provider-controlled strings are never parsed as rich markup.
        table.add_row(*(Text(cell) for cell in _row(p)))
    return table


def _provider_details(p: ProviderResult) -> list[str]:
    name = p.provider_name
    lines = []
    if p.score_semantics:
        lines.append(f"{name}: score = {p.score_semantics}")
    if p.weight_factors:
        factors = ", ".join(f"{k} {v:.2f}" for k, v in p.weight_factors.items())
        lines.append(f"{name}: weight factors {factors}")
    if p.cost is not None:
        lines.append(f"{name}: cost/credits {_mapping(_slots(p.cost))}")
    if p.rate_limit is not None:
        lines.append(f"{name}: rate limit {_mapping(_slots(p.rate_limit))}")
    if p.segments:
        lines.append(f"{name}: {len(p.segments)} {p.segments[0].kind}-level results")
    return lines


def _sent_note(result: CheckResult) -> str:
    contacted = [
        p.provider_name
        for p in result.providers
        if p.transport is not TransportKind.MOCK
        and not (p.error and p.error.category in _NOT_CONTACTED)
    ]
    return SENT_NOTE.format(names=", ".join(contacted)) if contacted else NOT_SENT_NOTE


def _print_section(console: Console, title: str, lines: list[str]) -> None:
    if not lines:
        return
    console.print(f"\n{title}:")
    for line in lines:
        console.print(f"- {line}", markup=False)


def render_verbose(result: CheckResult, console: Console) -> None:
    """Explain every provider attempt, the ensemble inputs and the timing."""
    console.print(Text(f"Verdict: {result.verdict.display}", style=_VERDICT_STYLE[result.verdict]))
    for line in _header_lines(result):
        console.print(line, markup=False)
    console.print()
    if result.providers:
        console.print(_provider_table(result))
    else:
        console.print("No provider ran.")
    details = [line for p in result.providers for line in _provider_details(p)]
    skipped: Mapping[str, str] = result.selection.get("skipped", {})
    details.extend(f"{pid}: skipped — {why}" for pid, why in skipped.items())
    _print_section(console, "Details", details)
    console.print("\nEnsemble reasoning:")
    for reason in result.aggregate.reasons:
        console.print(f"- {reason}", markup=False)
    _print_section(console, "Warnings", result.warnings)
    console.print(f"\n{DISCLAIMER} {_sent_note(result)}", style="dim", markup=False)


_NOT_CONTACTED = {
    ErrorCategory.NOT_CONFIGURED,
    ErrorCategory.INPUT_TOO_SHORT,
    ErrorCategory.INPUT_TOO_LARGE,
    ErrorCategory.TERMS_NOT_PERMITTED,
}
"""Failures raised before any request leaves the machine."""


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
            *(
                Text(cell)
                for cell in (
                    spec.id,
                    spec.name,
                    spec.transport.value,
                    "yes" if spec.enabled_by_default else "no",
                    creds,
                    limit,
                    spec.last_verified,
                    spec.adapter_status,
                )
            )
        )
    console.print(table)
    console.print(
        "[dim]Set the listed environment variables (or a local .env) to enable providers. "
        "Checks send your text to these third-party services.[/dim]"
    )
