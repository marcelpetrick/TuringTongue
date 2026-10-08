# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""Transparent weighted mixture-of-experts over provider results (vision §8).

For every provider that returned usable evidence ``e_i`` in [-1, +1]::

    vote_weight_i = reliability_i          # equal (1.0) until benchmarks justify more
                  * confidence_factor_i    # 0.5 + 0.5·c, or 0.75 when c is unknown
                  * applicability_i        # 0.5 below the provider's recommended minimum
                  * coverage_i             # submitted / total characters (truncation)

    evidence  = Σ e_i·w_i / Σ w_i                       (ensemble evidence)
    strength  = |evidence|
    agreement = |W_ai − W_human| / (W_ai + W_human)     (directional; neutral votes excluded)
    support   = min(1, Σ w_i / full_support_weight)
    confidence = strength · agreement · support         (ensemble certainty, NOT a probability)

Verdict policy: ``NO_VERDICT`` when nothing usable came back, when ``Σ w_i`` is below
``min_effective_weight``, when agreement is below ``min_agreement`` (conflicted), or
when ``strength`` lies inside the ``deadband``. Otherwise the sign decides HUMAN / AI.

Provider-native confidence, ensemble strength and cross-provider agreement are kept
as separate numbers; they are never collapsed into one fake percentage.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass

from turingtongue.models import Aggregate, Diagnostic, ProviderResult, Verdict
from turingtongue.normalization.confidence import confidence_factor

WARN_BELOW_RECOMMENDED_MINIMUM = "BELOW_RECOMMENDED_MINIMUM"
WARN_TRUNCATED = "TRUNCATED"


@dataclass(frozen=True, slots=True)
class EnsemblePolicy:
    """Versioned, reproducible ensemble configuration."""

    version: str = "v0-equal-weights"
    default_reliability: float = 1.0
    below_recommended_minimum_factor: float = 0.5
    neutral_epsilon: float = 0.05
    """|e| at or below this counts as an abstention for agreement purposes."""
    deadband: float = 0.15
    strong_threshold: float = 0.6
    min_effective_weight: float = 0.3
    min_agreement: float = 0.3
    full_support_weight: float = 2.0

    def as_dict(self) -> dict[str, float]:
        """Numeric policy parameters for reporting."""
        return {k: v for k, v in asdict(self).items() if isinstance(v, float)}


DEFAULT_POLICY = EnsemblePolicy()


def _weigh(
    result: ProviderResult, reliability: Mapping[str, float], policy: EnsemblePolicy
) -> float:
    factors = {
        "reliability": reliability.get(result.provider_id, policy.default_reliability),
        "confidence": confidence_factor(result.normalized_confidence),
        "applicability": (
            policy.below_recommended_minimum_factor
            if WARN_BELOW_RECOMMENDED_MINIMUM in result.warning_codes
            else 1.0
        ),
        "coverage": result.input_coverage,
    }
    weight = 1.0
    for value in factors.values():
        weight *= value
    result.weight_factors = factors
    result.vote_weight = weight
    return weight


def _diagnostic(evidence: float, policy: EnsemblePolicy) -> Diagnostic:
    if evidence <= -policy.strong_threshold:
        return Diagnostic.STRONGLY_HUMAN
    if evidence <= -policy.deadband:
        return Diagnostic.HUMAN_LEANING
    if evidence >= policy.strong_threshold:
        return Diagnostic.STRONGLY_AI
    if evidence >= policy.deadband:
        return Diagnostic.AI_LEANING
    return Diagnostic.BORDERLINE


def _collect_votes(
    results: Sequence[ProviderResult], reliability: Mapping[str, float], policy: EnsemblePolicy
) -> list[tuple[float, float]]:
    """``(evidence, weight)`` per usable result; annotates inclusion on every result."""
    used: list[tuple[float, float]] = []
    for result in results:
        if not result.ok or result.normalized_evidence is None:
            result.included_in_ensemble = False
            result.exclusion_reason = result.exclusion_reason or "no usable evidence"
            continue
        weight = _weigh(result, reliability, policy)
        result.included_in_ensemble = weight > 0
        result.exclusion_reason = None if weight > 0 else "zero vote weight"
        if weight > 0:
            used.append((result.normalized_evidence, weight))
    return used


def _agreement(used: Sequence[tuple[float, float]], policy: EnsemblePolicy) -> float | None:
    """Directional agreement; neutral votes (|e| <= epsilon) do not count."""
    ai_weight = sum(w for e, w in used if e > policy.neutral_epsilon)
    human_weight = sum(w for e, w in used if e < -policy.neutral_epsilon)
    directional = ai_weight + human_weight
    return abs(ai_weight - human_weight) / directional if directional > 0 else None


def _decide(
    evidence: float, agreement: float | None, total: float, voters: int, policy: EnsemblePolicy
) -> tuple[Verdict, Diagnostic, list[str]]:
    """Apply the NO_VERDICT policy, then map the evidence sign to HUMAN / AI."""
    if total < policy.min_effective_weight:
        return (
            Verdict.NO_VERDICT,
            Diagnostic.NO_EVIDENCE,
            [
                f"effective vote weight {total:.2f} is below the minimum "
                f"{policy.min_effective_weight:.2f}"
            ],
        )
    if agreement is not None and agreement < policy.min_agreement:
        return (
            Verdict.NO_VERDICT,
            Diagnostic.CONFLICTED,
            [
                f"providers disagree (agreement {agreement:.2f} < {policy.min_agreement:.2f}); "
                "inspect individual results"
            ],
        )
    diagnostic = _diagnostic(evidence, policy)
    if diagnostic is Diagnostic.BORDERLINE:
        return (
            Verdict.NO_VERDICT,
            diagnostic,
            [f"ensemble evidence {evidence:+.2f} lies inside the ±{policy.deadband} deadband"],
        )
    reasons = [f"weighted evidence {evidence:+.2f} from {voters} provider(s)"]
    if agreement is not None and agreement < 1.0:
        reasons.append("providers partially disagree; inspect individual results")
    return (Verdict.AI if evidence > 0 else Verdict.HUMAN), diagnostic, reasons


def _aggregate(
    evidence: float | None,
    agreement: float | None,
    total: float,
    voters: int,
    diagnostic: Diagnostic,
    reasons: list[str],
    policy: EnsemblePolicy,
) -> Aggregate:
    strength = abs(evidence) if evidence is not None else 0.0
    support = min(1.0, total / policy.full_support_weight)
    return Aggregate(
        evidence_score=evidence,
        strength=strength,
        confidence=strength * (agreement or 0.0) * support,
        agreement=agreement,
        effective_weight=total,
        providers_used=voters,
        diagnostic=diagnostic,
        reasons=reasons,
        weights_version=policy.version,
        policy=policy.as_dict(),
    )


def combine(
    results: Sequence[ProviderResult],
    *,
    reliability: Mapping[str, float] | None = None,
    policy: EnsemblePolicy = DEFAULT_POLICY,
) -> tuple[Verdict, Aggregate]:
    """Aggregate provider results. Annotates each result with its weight/inclusion."""
    used = _collect_votes(results, reliability or {}, policy)
    if not used:
        reasons = ["no provider returned usable evidence"]
        aggregate = _aggregate(None, None, 0.0, 0, Diagnostic.NO_EVIDENCE, reasons, policy)
        return Verdict.NO_VERDICT, aggregate
    total = sum(w for _, w in used)
    evidence = sum(e * w for e, w in used) / total
    agreement = _agreement(used, policy)
    verdict, diagnostic, reasons = _decide(evidence, agreement, total, len(used), policy)
    aggregate = _aggregate(evidence, agreement, total, len(used), diagnostic, reasons, policy)
    return verdict, aggregate
