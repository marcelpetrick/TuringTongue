# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
import pytest

from turingtongue.ensemble import (
    WARN_BELOW_RECOMMENDED_MINIMUM,
    EnsemblePolicy,
    combine,
)
from turingtongue.models import (
    Diagnostic,
    ErrorCategory,
    ProviderError,
    ProviderResult,
    ProviderStatus,
    TransportKind,
    Verdict,
)

pytestmark = pytest.mark.unit


def ok(
    pid: str,
    evidence: float,
    confidence: float | None = None,
    coverage: float = 1.0,
    warnings: list[str] | None = None,
) -> ProviderResult:
    return ProviderResult(
        provider_id=pid,
        provider_name=pid,
        transport=TransportKind.API,
        status=ProviderStatus.OK,
        normalized_evidence=evidence,
        normalized_confidence=confidence,
        input_coverage=coverage,
        warning_codes=warnings or [],
    )


def failed(pid: str) -> ProviderResult:
    return ProviderResult(
        provider_id=pid,
        provider_name=pid,
        transport=TransportKind.API,
        status=ProviderStatus.FAILED,
        error=ProviderError(pid, ErrorCategory.TIMEOUT, "t"),
    )


def test_no_results_is_no_verdict() -> None:
    verdict, agg = combine([])
    assert verdict is Verdict.NO_VERDICT
    assert agg.diagnostic is Diagnostic.NO_EVIDENCE
    assert agg.evidence_score is None
    assert agg.confidence == 0


def test_all_failed_is_no_verdict_and_annotated() -> None:
    results = [failed("a"), failed("b")]
    verdict, agg = combine(results)
    assert verdict is Verdict.NO_VERDICT
    assert agg.providers_used == 0
    assert all(r.exclusion_reason == "no usable evidence" for r in results)


def test_partial_success_still_decides() -> None:
    results = [ok("a", -0.9, 0.9), failed("b"), ok("c", -0.7)]
    verdict, agg = combine(results)
    assert verdict is Verdict.HUMAN
    assert agg.providers_used == 2
    assert agg.agreement == 1.0
    assert agg.diagnostic is Diagnostic.STRONGLY_HUMAN
    assert results[0].included_in_ensemble
    assert not results[1].included_in_ensemble


def test_weighted_mean_formula() -> None:
    a = ok("a", 1.0, confidence=1.0)  # weight 1.0
    b = ok("b", -1.0, confidence=None)  # weight 0.75
    c = ok("c", 1.0, confidence=0.0, coverage=0.5)  # weight 0.25
    _, agg = combine([a, b, c])
    expected = (1.0 * 1.0 - 0.75 + 0.25) / 2.0
    assert agg.evidence_score == pytest.approx(expected)
    assert (a.vote_weight, b.vote_weight, c.vote_weight) == (1.0, 0.75, 0.25)
    assert c.weight_factors == {
        "reliability": 1.0,
        "confidence": 0.5,
        "applicability": 1.0,
        "coverage": 0.5,
    }
    assert agg.agreement == pytest.approx((1.25 - 0.75) / 2.0)


def test_reliability_override_and_applicability() -> None:
    a = ok("a", 0.8, 1.0, warnings=[WARN_BELOW_RECOMMENDED_MINIMUM])
    combine([a], reliability={"a": 2.0})
    assert a.vote_weight == pytest.approx(1.0)


def test_conflict_is_no_verdict() -> None:
    verdict, agg = combine([ok("a", 0.9, 1), ok("b", -0.9, 1)])
    assert verdict is Verdict.NO_VERDICT
    assert agg.diagnostic is Diagnostic.CONFLICTED
    assert agg.agreement == 0
    assert "disagree" in agg.reasons[0]


def test_high_individual_confidence_low_agreement_low_certainty() -> None:
    _, agg = combine([ok("a", 1, 1), ok("b", 1, 1), ok("c", -1, 1)])
    assert agg.agreement == pytest.approx(1 / 3)
    assert agg.confidence < 0.2


def test_deadband_is_no_verdict() -> None:
    verdict, agg = combine([ok("a", 0.1, 1), ok("b", 0.05, 1)])
    assert verdict is Verdict.NO_VERDICT
    assert agg.diagnostic is Diagnostic.BORDERLINE


def test_neutral_only_votes_have_no_agreement() -> None:
    verdict, agg = combine([ok("a", 0.0, 1)])
    assert agg.agreement is None
    assert verdict is Verdict.NO_VERDICT


def test_low_weight_is_no_verdict() -> None:
    verdict, agg = combine([ok("a", 0.9, 0.0, coverage=0.1)])
    assert verdict is Verdict.NO_VERDICT
    assert "below the minimum" in agg.reasons[0]


def test_zero_weight_excluded() -> None:
    a = ok("a", 0.9, coverage=0.0)
    verdict, _ = combine([a])
    assert verdict is Verdict.NO_VERDICT
    assert a.exclusion_reason == "zero vote weight"


@pytest.mark.parametrize(
    ("evidence", "diagnostic", "verdict"),
    [
        (0.3, Diagnostic.AI_LEANING, Verdict.AI),
        (0.9, Diagnostic.STRONGLY_AI, Verdict.AI),
        (-0.3, Diagnostic.HUMAN_LEANING, Verdict.HUMAN),
    ],
)
def test_diagnostics(evidence: float, diagnostic: Diagnostic, verdict: Verdict) -> None:
    got, agg = combine([ok("a", evidence, 1.0), ok("b", evidence, 1.0)])
    assert (got, agg.diagnostic) == (verdict, diagnostic)
    assert agg.weights_version == "v0-equal-weights"
    assert agg.policy["deadband"] == 0.15


def test_partial_disagreement_reason() -> None:
    verdict, agg = combine([ok("a", 0.9, 1), ok("b", 0.9, 1), ok("c", 0.9, 1), ok("d", -0.2, 1)])
    assert verdict is Verdict.AI
    assert any("partially disagree" in r for r in agg.reasons)


def test_custom_policy() -> None:
    policy = EnsemblePolicy(version="test", deadband=0.5)
    verdict, agg = combine([ok("a", 0.4, 1), ok("b", 0.4, 1)], policy=policy)
    assert verdict is Verdict.NO_VERDICT
    assert agg.weights_version == "test"
