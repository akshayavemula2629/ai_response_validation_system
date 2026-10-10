"""
Evaluation Orchestrator.
Coordinates the end-to-end evaluation pipeline: input validation, KB retrieval,
relevance, accuracy, hallucination detection, completeness, better-answer synthesis,
verdict aggregation, and structured response construction.
"""
import logging
from typing import Optional, List

from backend.api.schemas.evaluation import (
    EvaluationRequest,
    EvaluationResponse,
    EvaluationMetrics,
    RetrievedEvidenceItem
)
from backend.retrieval.retriever import retrieve_relevant_context
from backend.evaluation.similarity import calculate_semantic_similarity
from backend.agents.relevance_agent import RelevanceJudgeAgent
from backend.agents.accuracy_agent import AccuracyJudgeAgent
from backend.agents.hallucination_agent import HallucinationDetectionAgent
from backend.agents.completeness_agent import CompletenessJudgeAgent
from backend.agents.verdict_agent import VerdictAgent
from backend.evaluation.better_answer import generate_better_answer

logger = logging.getLogger(__name__)


class EvaluationOrchestrator:
    """Central orchestrator coordinating multi-agent evaluation and synthesis."""

    def __init__(self):
        self.relevance_agent = RelevanceJudgeAgent()
        self.accuracy_agent = AccuracyJudgeAgent()
        self.hallucination_agent = HallucinationDetectionAgent()
        self.completeness_agent = CompletenessJudgeAgent()
        self.verdict_agent = VerdictAgent()

    def evaluate(self, request: EvaluationRequest) -> EvaluationResponse:
        """
        Executes the full evaluation pipeline for an EvaluationRequest.
        """
        question = request.question.strip()
        ai_response = request.ai_response.strip()
        reference_answer = (request.reference_answer or "").strip()
        source_doc = request.source_document.strip() if request.source_document else None

        # Mandatory Reference Answer validation
        if not reference_answer:
            raise ValueError("Reference answer is required: Please enter the reference answer before submitting the evaluation.")

        case_mode_label = "Case 1: Reference Ground Truth"
        logger.info("Executing evaluation pipeline (%s) for question: '%s'...", case_mode_label, question[:60])

        # Step 1: Semantic Retrieval from Knowledge Base
        retrieved_evidence = retrieve_relevant_context(question)

        # If user supplied an optional source document, prepend it as high-priority evidence
        if source_doc:
            user_doc_item = RetrievedEvidenceItem(
                chunk_id="user_supplied_doc",
                content=source_doc,
                source="User Supplied Document",
                similarity_score=1.0
            )
            retrieved_evidence.insert(0, user_doc_item)

        evidence_texts = [e.content for e in retrieved_evidence]

        # Step 2: Calculate Semantic Similarity
        similarity_eval = calculate_semantic_similarity(
            ai_response=ai_response,
            reference_answer=reference_answer,
            retrieved_evidence=evidence_texts
        )

        # Step 3: Run Relevance Judge Agent (M2: 1-5 scale & categories)
        relevance_eval, relevance_judge = self.relevance_agent.evaluate(
            question=question,
            ai_response=ai_response
        )

        # Step 4: Run Accuracy Judge Agent (M2: 1-5 scale, Reference Ground Truth)
        accuracy_eval, factual_issues, accuracy_judge = self.accuracy_agent.evaluate(
            question=question,
            ai_response=ai_response,
            reference_answer=reference_answer,
            retrieved_evidence=evidence_texts,
            use_knowledge_base_only=False
        )

        # Step 5: Run Hallucination Detection Agent (M2: atomic claims: Supported, Unsupported, Contradicted)
        hallucination_eval, hallucination_judge = self.hallucination_agent.evaluate(
            question=question,
            ai_response=ai_response,
            reference_answer=reference_answer,
            retrieved_evidence=retrieved_evidence,
            use_knowledge_base_only=False,
            factual_issues=factual_issues
        )

        # Step 6: Run Completeness Judge Agent (M3: requirement extraction, 3-tier classification)
        completeness_eval, missing_items, completeness_judge = self.completeness_agent.evaluate(
            question=question,
            ai_response=ai_response,
            reference_answer=reference_answer
        )

        # Step 7: Synthesize Grounded Better Answer & Comparison Metrics
        all_detected_issues = factual_issues + hallucination_eval.issues + missing_items
        better_answer, better_answer_reason, comparison_data = generate_better_answer(
            question=question,
            original_response=ai_response,
            reference_answer=reference_answer,
            accuracy_score=accuracy_eval.score,
            hallucination_pct=hallucination_eval.percentage,
            completeness_score=completeness_eval.score,
            retrieved_evidence=retrieved_evidence,
            detected_issues=all_detected_issues
        )

        # Step 8: Run Verdict Agent (M3: weighted 25/30/25/20 arbitration, severe hallucination override)
        verdict_result = self.verdict_agent.evaluate(
            relevance=relevance_eval,
            accuracy=accuracy_eval,
            hallucination=hallucination_eval,
            completeness=completeness_eval,
            similarity=similarity_eval,
            hallucination_judge=hallucination_judge,
            completeness_judge=completeness_judge
        )

        # Step 9: Assemble Structured Response Module (preserving M1/M2 and adding M3)
        metrics = EvaluationMetrics(
            relevance=relevance_eval,
            accuracy=accuracy_eval,
            hallucination=hallucination_eval,
            completeness=completeness_eval,
            similarity=similarity_eval,
            overall_score=verdict_result["overall_score"],
            verdict=verdict_result["verdict"],
            summary=verdict_result["summary"]
        )

        response = EvaluationResponse(
            question=question,
            original_response=ai_response,
            reference_answer=reference_answer,
            better_answer=better_answer,
            better_answer_reason=better_answer_reason,
            evaluation=metrics,
            retrieved_evidence=retrieved_evidence,
            comparison=comparison_data,
            relevance_judge=relevance_judge,
            accuracy_judge=accuracy_judge,
            hallucination_judge=hallucination_judge,
            case_mode=case_mode_label,
            completeness_judge=completeness_judge,
            verdict_judge=verdict_result.get("verdict_judge")
        )

        logger.info(
            "Evaluation completed (%s). Overall score: %.1f, Verdict: %s | Rel: %d/5, Acc: %d/5 (%s), Hal: %d/%d supported, Comp: %.1f",
            case_mode_label,
            metrics.overall_score,
            metrics.verdict,
            relevance_judge.score,
            accuracy_judge.score,
            accuracy_judge.evidence_source,
            hallucination_judge.supported_claims,
            hallucination_judge.total_claims,
            completeness_judge.completeness_score
        )
        return response

    def evaluate_stream(self, request: EvaluationRequest):
        """
        Executes the evaluation pipeline stage-by-stage and yields genuine progress events:
        Stage 1: Relevance
        Stage 2: Accuracy
        Stage 3: Hallucination Detection
        Stage 4: Completeness
        Stage 5: Verdict
        Followed by final EVALUATION_COMPLETED event containing the full response.
        """
        question = request.question.strip()
        ai_response = request.ai_response.strip()
        reference_answer = (request.reference_answer or "").strip()
        source_doc = request.source_document.strip() if request.source_document else None

        if not reference_answer:
            raise ValueError("Reference answer is required: Please enter the reference answer before submitting the evaluation.")

        case_mode_label = "Case 1: Reference Ground Truth"

        # Pre-pipeline setup: Retrieval & Similarity
        retrieved_evidence = retrieve_relevant_context(question)
        if source_doc:
            user_doc_item = RetrievedEvidenceItem(
                chunk_id="user_supplied_doc",
                content=source_doc,
                source="User Supplied Document",
                similarity_score=1.0
            )
            retrieved_evidence.insert(0, user_doc_item)
        evidence_texts = [e.content for e in retrieved_evidence]

        similarity_eval = calculate_semantic_similarity(
            ai_response=ai_response,
            reference_answer=reference_answer,
            retrieved_evidence=evidence_texts
        )

        # Stage 1: Relevance
        yield {
            "event": "STAGE_STARTED",
            "stage": "RELEVANCE",
            "stage_index": 1,
            "total_stages": 5,
            "stage_name": "Relevance",
            "percentage": 0
        }
        relevance_eval, relevance_judge = self.relevance_agent.evaluate(
            question=question,
            ai_response=ai_response
        )
        yield {
            "event": "STAGE_COMPLETED",
            "stage": "RELEVANCE",
            "stage_index": 1,
            "total_stages": 5,
            "stage_name": "Relevance",
            "percentage": 20
        }

        # Stage 2: Accuracy
        yield {
            "event": "STAGE_STARTED",
            "stage": "ACCURACY",
            "stage_index": 2,
            "total_stages": 5,
            "stage_name": "Accuracy",
            "percentage": 20
        }
        accuracy_eval, factual_issues, accuracy_judge = self.accuracy_agent.evaluate(
            question=question,
            ai_response=ai_response,
            reference_answer=reference_answer,
            retrieved_evidence=evidence_texts,
            use_knowledge_base_only=False
        )
        yield {
            "event": "STAGE_COMPLETED",
            "stage": "ACCURACY",
            "stage_index": 2,
            "total_stages": 5,
            "stage_name": "Accuracy",
            "percentage": 40
        }

        # Stage 3: Hallucination Detection
        yield {
            "event": "STAGE_STARTED",
            "stage": "HALLUCINATION",
            "stage_index": 3,
            "total_stages": 5,
            "stage_name": "Hallucination Detection",
            "percentage": 40
        }
        hallucination_eval, hallucination_judge = self.hallucination_agent.evaluate(
            question=question,
            ai_response=ai_response,
            reference_answer=reference_answer,
            retrieved_evidence=retrieved_evidence,
            use_knowledge_base_only=False,
            factual_issues=factual_issues
        )
        yield {
            "event": "STAGE_COMPLETED",
            "stage": "HALLUCINATION",
            "stage_index": 3,
            "total_stages": 5,
            "stage_name": "Hallucination Detection",
            "percentage": 60
        }

        # Stage 4: Completeness
        yield {
            "event": "STAGE_STARTED",
            "stage": "COMPLETENESS",
            "stage_index": 4,
            "total_stages": 5,
            "stage_name": "Completeness",
            "percentage": 60
        }
        completeness_eval, missing_items, completeness_judge = self.completeness_agent.evaluate(
            question=question,
            ai_response=ai_response,
            reference_answer=reference_answer
        )
        yield {
            "event": "STAGE_COMPLETED",
            "stage": "COMPLETENESS",
            "stage_index": 4,
            "total_stages": 5,
            "stage_name": "Completeness",
            "percentage": 80
        }

        # Stage 5: Verdict Arbitration & Better Answer Synthesis
        yield {
            "event": "STAGE_STARTED",
            "stage": "VERDICT",
            "stage_index": 5,
            "total_stages": 5,
            "stage_name": "Verdict",
            "percentage": 80
        }
        all_detected_issues = factual_issues + hallucination_eval.issues + missing_items
        better_answer, better_answer_reason, comparison_data = generate_better_answer(
            question=question,
            original_response=ai_response,
            reference_answer=reference_answer,
            accuracy_score=accuracy_eval.score,
            hallucination_pct=hallucination_eval.percentage,
            completeness_score=completeness_eval.score,
            retrieved_evidence=retrieved_evidence,
            detected_issues=all_detected_issues
        )

        verdict_result = self.verdict_agent.evaluate(
            relevance=relevance_eval,
            accuracy=accuracy_eval,
            hallucination=hallucination_eval,
            completeness=completeness_eval,
            similarity=similarity_eval,
            hallucination_judge=hallucination_judge,
            completeness_judge=completeness_judge
        )

        metrics = EvaluationMetrics(
            relevance=relevance_eval,
            accuracy=accuracy_eval,
            hallucination=hallucination_eval,
            completeness=completeness_eval,
            similarity=similarity_eval,
            overall_score=verdict_result["overall_score"],
            verdict=verdict_result["verdict"],
            summary=verdict_result["summary"]
        )

        response = EvaluationResponse(
            question=question,
            original_response=ai_response,
            reference_answer=reference_answer,
            better_answer=better_answer,
            better_answer_reason=better_answer_reason,
            evaluation=metrics,
            retrieved_evidence=retrieved_evidence,
            comparison=comparison_data,
            relevance_judge=relevance_judge,
            accuracy_judge=accuracy_judge,
            hallucination_judge=hallucination_judge,
            case_mode=case_mode_label,
            completeness_judge=completeness_judge,
            verdict_judge=verdict_result.get("verdict_judge")
        )

        yield {
            "event": "STAGE_COMPLETED",
            "stage": "VERDICT",
            "stage_index": 5,
            "total_stages": 5,
            "stage_name": "Verdict",
            "percentage": 100
        }

        yield {
            "event": "EVALUATION_COMPLETED",
            "stage": "COMPLETE",
            "stage_index": 5,
            "total_stages": 5,
            "percentage": 100,
            "result": response.model_dump()
        }


# Global singleton orchestrator
_orchestrator = None

def get_orchestrator() -> EvaluationOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = EvaluationOrchestrator()
    return _orchestrator
