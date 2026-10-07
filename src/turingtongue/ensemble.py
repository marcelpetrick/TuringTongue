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


def combine(
    results: Sequence[ProviderResult],
    *,
    reliability: Mapping[str, float] | None = None,
    policy: EnsemblePolicy = DEFAULT_POLICY,
) -> tuple[Verdict, Aggregate]:
    """Aggregate provider results. Annotates each result with its weight/inclusion."""
    weights_by_provider = reliability or {}
    used: list[tuple[float, float]] = []
    for result in results:
        if not result.ok or result.normalized_evidence is None:
            result.included_in_ensemble = False
            result.exclusion_reason = result.exclusion_reason or "no usable evidence"
            continue
        weight = _weigh(result, weights_by_provider, policy)
        if weight <= 0:
            result.included_in_ensemble = False
            result.exclusion_reason = "zero vote weight"
            continue
        result.included_in_ensemble = True
        result.exclusion_reason = None
        used.append((result.normalized_evidence, weight))

    def aggregate(
        evidence: float | None,
        agreement: float | None,
        total: float,
        diagnostic: Diagnostic,
        reasons: list[str],
    ) -> Aggregate:
        strength = abs(evidence) if evidence is not None else 0.0
        support = min(1.0, total / policy.full_support_weight)
        confidence = strength * (agreement or 0.0) * support
        return Aggregate(
            evidence_score=evidence,
            strength=strength,
            confidence=confidence,
            agreement=agreement,
            effective_weight=total,
            providers_used=len(used),
            diagnostic=diagnostic,
            reasons=reasons,
            weights_version=policy.version,
            policy=policy.as_dict(),
        )

    if not used:
        reasons = ["no provider returned usable evidence"]
        return Verdict.NO_VERDICT, aggregate(None, None, 0.0, Diagnostic.NO_EVIDENCE, reasons)

    total = sum(w for _, w in used)
    evidence = sum(e * w for e, w in used) / total
    ai_weight = sum(w for e, w in used if e > policy.neutral_epsilon)
    human_weight = sum(w for e, w in used if e < -policy.neutral_epsilon)
    directional = ai_weight + human_weight
    agreement = abs(ai_weight - human_weight) / directional if directional > 0 else None

    if total < policy.min_effective_weight:
        reasons = [
            f"effective vote weight {total:.2f} is below the minimum "
            f"{policy.min_effective_weight:.2f}"
        ]
        return Verdict.NO_VERDICT, aggregate(
            evidence, agreement, total, Diagnostic.NO_EVIDENCE, reasons
        )
    if agreement is not None and agreement < policy.min_agreement:
        reasons = [
            f"providers disagree (agreement {agreement:.2f} < {policy.min_agreement:.2f}); "
            "inspect individual results"
        ]
        return Verdict.NO_VERDICT, aggregate(
            evidence, agreement, total, Diagnostic.CONFLICTED, reasons
        )
    diagnostic = _diagnostic(evidence, policy)
    if diagnostic is Diagnostic.BORDERLINE:
        reasons = [f"ensemble evidence {evidence:+.2f} lies inside the ±{policy.deadband} deadband"]
        return Verdict.NO_VERDICT, aggregate(evidence, agreement, total, diagnostic, reasons)
    verdict = Verdict.AI if evidence > 0 else Verdict.HUMAN
    reasons = [f"weighted evidence {evidence:+.2f} from {len(used)} provider(s)"]
    if agreement is not None and agreement < 1.0:
        reasons.append("providers partially disagree; inspect individual results")
    return verdict, aggregate(evidence, agreement, total, diagnostic, reasons)
