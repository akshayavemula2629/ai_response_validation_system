"""
Verdict Agent.
Synthesizes dimensional evaluation results into a unified overall score, verdict category,
major issues compilation, actionable recommendation, and consolidated reasoning.
"""
import logging
from typing import Dict, Any, Optional, List

from backend.api.schemas.evaluation import (
    DimensionScore,
    HallucinationEvaluation,
    SimilarityEvaluation,
    HallucinationJudgeResult,
    CompletenessJudgeResult,
    VerdictJudgeResult
)
from backend.evaluation.scoring import compute_overall_score, determine_m3_verdict, determine_verdict_label

logger = logging.getLogger(__name__)


class VerdictAgent:
    """Agent responsible for final evaluation arbitration and verdict synthesis."""

    def evaluate(
        self,
        relevance: DimensionScore,
        accuracy: DimensionScore,
        hallucination: HallucinationEvaluation,
        completeness: DimensionScore,
        similarity: SimilarityEvaluation,
        hallucination_judge: Optional[HallucinationJudgeResult] = None,
        completeness_judge: Optional[CompletenessJudgeResult] = None
    ) -> Dict[str, Any]:
        """
        Combines individual dimension scores into composite weighted score, final verdict,
        major issues list, and consolidated reasoning according to Milestone 3 specification.
        """
        # Hallucination evaluation provides 'score' as the hallucination-free quality metric (100 = completely factual)
        hallucination_quality_score = max(0.0, min(100.0, hallucination.score))

        # Milestone 3 weighted overall score:
        # (Relevance * 0.25) + (Accuracy * 0.30) + (Completeness * 0.25) + (Hallucination * 0.20)
        overall_score = compute_overall_score(
            relevance_score=relevance.score,
            accuracy_score=accuracy.score,
            hallucination_free_score=hallucination_quality_score,
            completeness_score=completeness.score
        )

        # Count contradicted claims for severe hallucination evaluation
        contradicted_count = 0
        if hallucination_judge:
            contradicted_count = hallucination_judge.contradicted_claims
        elif hallucination.issues:
            contradicted_count = sum(1 for issue in hallucination.issues if "contradict" in issue.lower())

        # Determine Milestone 3 verdict ('PASS', 'NEEDS IMPROVEMENT', 'FAIL') with Severe Hallucination Override
        final_verdict, override_triggered = determine_m3_verdict(
            overall_score=overall_score,
            hallucination_risk_percentage=hallucination.percentage,
            contradicted_claims_count=contradicted_count
        )

        # Determine Milestone 1 verdict for backward compatibility
        m1_verdict = determine_verdict_label(overall_score)
        if override_triggered and m1_verdict in ("Excellent", "Good"):
            m1_verdict = "Needs Improvement" if final_verdict == "NEEDS IMPROVEMENT" else "Poor"

        # Compile major issues list
        major_issues: List[str] = []
        if override_triggered:
            major_issues.append(
                f"Severe hallucination override triggered: High hallucination risk ({hallucination.percentage}%) "
                f"or {contradicted_count} factual contradiction(s) detected. Final verdict cannot be PASS."
            )
        for issue in hallucination.issues:
            if issue not in major_issues:
                major_issues.append(f"Factual/Hallucination Issue: {issue}")

        if accuracy.score < 60.0:
            major_issues.append(f"Low Accuracy ({accuracy.score}/100): Response contains significant factual inaccuracies.")

        if relevance.score < 60.0:
            major_issues.append(f"Low Relevance ({relevance.score}/100): Response deviates substantially from question intent.")

        if completeness_judge and completeness_judge.missing_aspects:
            omissions_str = ", ".join(f'"{m}"' for m in completeness_judge.missing_aspects[:3])
            major_issues.append(f"Missing Information: Omitted essential context: {omissions_str}.")
        elif completeness.score < 60.0:
            major_issues.append(f"Incomplete Coverage ({completeness.score}/100): Critical reference concepts were omitted.")

        # Formulate consolidated reasoning synthesis
        verdict_descriptions = {
            "PASS": "The response satisfies rigorous quality and factuality benchmarks with high grounding across all dimensions.",
            "NEEDS IMPROVEMENT": "The response demonstrates moderate utility but exhibits factual discrepancies, notable omissions, or borderline grounding.",
            "FAIL": "The response fails essential quality requirements due to severe factual contradictions, high hallucination risk, or major omissions."
        }
        verdict_desc = verdict_descriptions.get(final_verdict, "")

        consolidated_reasoning = (
            f"Final Evaluation Verdict: '{final_verdict}' with Weighted Overall Score of {overall_score}/100. "
            f"{verdict_desc} "
            f"Dimensional Breakdown: Relevance: {relevance.score}/100 (25% weight), Accuracy: {accuracy.score}/100 (30% weight), "
            f"Completeness: {completeness.score}/100 (25% weight), and Hallucination-Free Quality: {hallucination_quality_score}/100 (20% weight; "
            f"Risk: {hallucination.percentage}% - {hallucination.risk_level} risk). "
            f"Semantic Similarity with reference: {similarity.percentage}%."
        )
        if override_triggered:
            consolidated_reasoning += (
                " Note: Verdict was adjusted downward under the Severe Hallucination Override policy to ensure critical factual errors are not masked by high scores in other dimensions."
            )

        # Actionable recommendation
        if final_verdict == "PASS":
            recommendation = "Recommended Action: Suitable for direct presentation and deployment."
        elif final_verdict == "NEEDS IMPROVEMENT":
            recommendation = "Recommended Action: Review highlighted issues or adopt the grounded 'Better Answer' to resolve omissions and minor inaccuracies."
        else:
            recommendation = "Recommended Action: Critical factual errors or severe hallucinations present. Do NOT present the original response; substitute with the grounded 'Better Answer'."

        summary = f"{consolidated_reasoning} {recommendation}"

        verdict_judge = VerdictJudgeResult(
            relevance_score=relevance.score,
            accuracy_score=accuracy.score,
            hallucination_score=hallucination_quality_score,
            completeness_score=completeness.score,
            weighted_overall_score=overall_score,
            final_verdict=final_verdict,
            major_issues=major_issues,
            consolidated_reasoning=consolidated_reasoning,
            severe_hallucination_override=override_triggered
        )

        return {
            "overall_score": overall_score,
            "verdict": m1_verdict,
            "final_verdict": final_verdict,
            "summary": summary,
            "verdict_judge": verdict_judge
        }

