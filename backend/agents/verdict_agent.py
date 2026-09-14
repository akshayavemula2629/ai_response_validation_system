"""
Verdict Agent.
Synthesizes dimensional evaluation results into a unified overall score, verdict category,
summary, and actionable recommendation.
"""
import logging
from typing import Dict, Any

from backend.api.schemas.evaluation import (
    DimensionScore,
    HallucinationEvaluation,
    SimilarityEvaluation
)
from backend.evaluation.scoring import compute_overall_score, determine_verdict_label

logger = logging.getLogger(__name__)


class VerdictAgent:
    """Agent responsible for final evaluation arbitration and verdict synthesis."""

    def evaluate(
        self,
        relevance: DimensionScore,
        accuracy: DimensionScore,
        hallucination: HallucinationEvaluation,
        completeness: DimensionScore,
        similarity: SimilarityEvaluation
    ) -> Dict[str, Any]:
        """
        Combines individual dimension scores into composite score, verdict label,
        summary, and recommendation.
        """
        # Hallucination evaluation provides 'score' as the hallucination-free metric (100 = clean)
        overall_score = compute_overall_score(
            relevance_score=relevance.score,
            accuracy_score=accuracy.score,
            hallucination_free_score=hallucination.score,
            completeness_score=completeness.score
        )

        verdict_label = determine_verdict_label(overall_score)

        # Formulate comprehensive executive summary
        summary = (
            f"The response achieved an overall verdict score of {overall_score}/100, classified as '{verdict_label}'. "
            f"Key metrics: Relevance: {relevance.score}/100, Accuracy: {accuracy.score}/100, "
            f"Hallucination Risk: {hallucination.percentage}% ({hallucination.risk_level} risk), "
            f"Completeness: {completeness.score}/100, and Semantic Similarity: {similarity.percentage}%."
        )

        # Formulate actionable recommendation
        if verdict_label == "Excellent":
            recommendation = "The AI response meets high standards of factuality, completeness, and relevance. Suitable for direct presentation."
        elif verdict_label == "Good":
            recommendation = "The response is generally sound with minor gaps. Consider reviewing suggested improvements for optimal clarity."
        elif verdict_label == "Needs Improvement":
            recommendation = (
                "The response exhibits noticeable deficiencies, such as unsupported claims or incomplete context. "
                "Adopting the provided 'Better Answer' is strongly recommended."
            )
        else:  # Poor
            recommendation = (
                "The response contains severe factual inaccuracies, hallucinations, or irrelevance. "
                "Do NOT rely on the original response; substitute with the grounded 'Better Answer'."
            )

        return {
            "overall_score": overall_score,
            "verdict": verdict_label,
            "summary": f"{summary} {recommendation}"
        }
