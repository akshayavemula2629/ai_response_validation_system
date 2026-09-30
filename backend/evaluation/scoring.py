"""
Scoring and threshold rules for evaluation dimensions and overall verdict.
Provides consistent 0-100 scale normalization, risk tiering, and composite score computation.
"""
from typing import Dict, Any, Tuple
from backend.config import settings


def compute_overall_score(
    relevance_score: float,
    accuracy_score: float,
    hallucination_free_score: float,
    completeness_score: float
) -> float:
    """
    Computes weighted overall verdict score on 0-100 scale according to Milestone 3 specification:
        - Relevance: 25%
        - Accuracy: 30%
        - Completeness: 25%
        - Hallucination-Free Quality: 20%
    Formula:
        Overall Score = (Relevance * 0.25) + (Accuracy * 0.30) + (Completeness * 0.25) + (Hallucination * 0.20)
    """
    weighted = (
        (relevance_score * settings.WEIGHT_RELEVANCE) +
        (accuracy_score * settings.WEIGHT_ACCURACY) +
        (completeness_score * settings.WEIGHT_COMPLETENESS) +
        (hallucination_free_score * settings.WEIGHT_HALLUCINATION)
    )
    return round(float(max(0.0, min(100.0, weighted))), 1)


def determine_m3_verdict(
    overall_score: float,
    hallucination_risk_percentage: float = 0.0,
    contradicted_claims_count: int = 0
) -> Tuple[str, bool]:
    """
    Milestone 3 Verdict Determination with Severe Hallucination Override:
    - 80.0 - 100.0 -> PASS
    - 60.0 - 79.99 -> NEEDS IMPROVEMENT
    - 0.0  - 59.99 -> FAIL

    Severe Hallucination Handling:
    A high numerical average must NOT hide critical factual contradictions or severe hallucination.
    If hallucination risk > 50% or contradicted claims are detected:
        - 'PASS' is strictly blocked and downgraded to 'FAIL' or 'NEEDS IMPROVEMENT'.
    Returns:
        (verdict_label: 'PASS' | 'NEEDS IMPROVEMENT' | 'FAIL', override_triggered: bool)
    """
    if overall_score >= settings.PASS_THRESHOLD:
        base_verdict = "PASS"
    elif overall_score >= settings.NEEDS_IMPROVEMENT_THRESHOLD:
        base_verdict = "NEEDS IMPROVEMENT"
    else:
        base_verdict = "FAIL"

    override_triggered = False
    final_verdict = base_verdict

    # Severe Hallucination Override Rule
    is_severe_hallucination = (
        hallucination_risk_percentage > settings.HALLUCINATION_MED_MAX  # > 50.0%
        or contradicted_claims_count > 0
    )

    if is_severe_hallucination:
        if base_verdict == "PASS":
            override_triggered = True
            # Downgrade to FAIL if risk is critical or contradicted claims exist
            if hallucination_risk_percentage >= 75.0 or contradicted_claims_count >= 1:
                final_verdict = "FAIL"
            else:
                final_verdict = "NEEDS IMPROVEMENT"
        elif base_verdict == "NEEDS IMPROVEMENT" and hallucination_risk_percentage >= 75.0:
            override_triggered = True
            final_verdict = "FAIL"

    return final_verdict, override_triggered


def determine_verdict_label(
    overall_score: float,
    hallucination_risk_percentage: float = 0.0,
    contradicted_claims_count: int = 0
) -> str:
    """
    Milestone 1 verdict label for backward compatibility with existing tests and API consumers:
    - >= 85.0: Excellent
    - >= 70.0: Good
    - >= 50.0: Needs Improvement
    - < 50.0:  Poor
    """
    if overall_score >= settings.EXCELLENT_THRESHOLD:
        return "Excellent"
    elif overall_score >= settings.GOOD_THRESHOLD:
        return "Good"
    elif overall_score >= 50.0:
        return "Needs Improvement"
    else:
        return "Poor"


def determine_hallucination_risk(risk_percentage: float) -> Tuple[str, float]:
    """
    Calculates hallucination risk tier and corresponding hallucination-free score.
    Returns:
        (risk_level: "Low" | "Medium" | "High", hallucination_free_score: 0-100)
    """
    clamped_pct = max(0.0, min(100.0, float(risk_percentage)))
    hallucination_free = round(100.0 - clamped_pct, 1)

    if clamped_pct <= settings.HALLUCINATION_LOW_MAX:
        risk_level = "Low"
    elif clamped_pct <= settings.HALLUCINATION_MED_MAX:
        risk_level = "Medium"
    else:
        risk_level = "High"

    return risk_level, hallucination_free

