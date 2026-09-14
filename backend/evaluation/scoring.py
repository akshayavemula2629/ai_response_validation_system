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
    Computes weighted overall verdict score on 0-100 scale.
    Weights:
        - Accuracy: 35%
        - Relevance: 25%
        - Hallucination-Free: 25%
        - Completeness: 15%
    """
    weighted = (
        (relevance_score * settings.WEIGHT_RELEVANCE) +
        (accuracy_score * settings.WEIGHT_ACCURACY) +
        (hallucination_free_score * settings.WEIGHT_HALLUCINATION) +
        (completeness_score * settings.WEIGHT_COMPLETENESS)
    )
    return round(float(max(0.0, min(100.0, weighted))), 1)


def determine_verdict_label(overall_score: float) -> str:
    """
    Maps composite score to standardized verdict category:
    - >= 85.0: Excellent
    - >= 70.0: Good
    - >= 50.0: Needs Improvement
    - < 50.0:  Poor
    """
    if overall_score >= settings.EXCELLENT_THRESHOLD:
        return "Excellent"
    elif overall_score >= settings.GOOD_THRESHOLD:
        return "Good"
    elif overall_score >= settings.NEEDS_IMPROVEMENT_THRESHOLD:
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
