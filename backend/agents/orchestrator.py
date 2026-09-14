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
        use_kb_only = getattr(request, "use_knowledge_base_only", False)
        reference_answer = (request.reference_answer or "").strip()
        source_doc = request.source_document.strip() if request.source_document else None

        # Determine evaluation case mode
        is_case_2 = use_kb_only or (not reference_answer)
        case_mode_label = "Case 2: Knowledge Base Ground Truth" if is_case_2 else "Case 1: Reference Ground Truth"

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

        # In Case 2 (KB-only), derive effective ground truth reference from top retrieved evidence
        effective_reference = reference_answer
        if not effective_reference:
            effective_reference = retrieved_evidence[0].content if retrieved_evidence else "Knowledge base retrieval without explicit reference answer."
            reference_answer_for_response = "Knowledge Base Retrieval (No Reference Provided)"
        else:
            reference_answer_for_response = reference_answer

        # Step 2: Calculate Semantic Similarity
        similarity_eval = calculate_semantic_similarity(
            ai_response=ai_response,
            reference_answer=effective_reference,
            retrieved_evidence=evidence_texts
        )

        # Step 3: Run Relevance Judge Agent (M2: 1-5 scale & categories)
        relevance_eval, relevance_judge = self.relevance_agent.evaluate(
            question=question,
            ai_response=ai_response
        )

        # Step 4: Run Accuracy Judge Agent (M2: 1-5 scale, Case 1 & Case 2 RAG)
        accuracy_eval, factual_issues, accuracy_judge = self.accuracy_agent.evaluate(
            question=question,
            ai_response=ai_response,
            reference_answer=reference_answer if reference_answer else None,
            retrieved_evidence=evidence_texts,
            use_knowledge_base_only=use_kb_only
        )

        # Step 5: Run Hallucination Detection Agent (M2: atomic claims: Supported, Unsupported, Contradicted)
        hallucination_eval, hallucination_judge = self.hallucination_agent.evaluate(
            question=question,
            ai_response=ai_response,
            reference_answer=reference_answer if reference_answer else None,
            retrieved_evidence=retrieved_evidence,
            use_knowledge_base_only=use_kb_only
        )

        # Step 6: Run Completeness Judge Agent
        completeness_eval, missing_items = self.completeness_agent.evaluate(
            question=question,
            ai_response=ai_response,
            reference_answer=effective_reference
        )

        # Step 7: Synthesize Grounded Better Answer & Comparison Metrics
        all_detected_issues = factual_issues + hallucination_eval.issues + missing_items
        better_answer, better_answer_reason, comparison_data = generate_better_answer(
            question=question,
            original_response=ai_response,
            reference_answer=effective_reference,
            accuracy_score=accuracy_eval.score,
            hallucination_pct=hallucination_eval.percentage,
            completeness_score=completeness_eval.score,
            retrieved_evidence=retrieved_evidence,
            detected_issues=all_detected_issues
        )

        # Step 8: Run Verdict Agent
        verdict_result = self.verdict_agent.evaluate(
            relevance=relevance_eval,
            accuracy=accuracy_eval,
            hallucination=hallucination_eval,
            completeness=completeness_eval,
            similarity=similarity_eval
        )

        # Step 9: Assemble Structured Response Module (preserving M1 and adding M2)
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
            reference_answer=reference_answer_for_response,
            better_answer=better_answer,
            better_answer_reason=better_answer_reason,
            evaluation=metrics,
            retrieved_evidence=retrieved_evidence,
            comparison=comparison_data,
            relevance_judge=relevance_judge,
            accuracy_judge=accuracy_judge,
            hallucination_judge=hallucination_judge,
            case_mode=case_mode_label
        )

        logger.info(
            "Evaluation completed (%s). Overall score: %.1f, Verdict: %s | Rel: %d/5, Acc: %d/5 (%s), Hal: %d/%d supported",
            case_mode_label,
            metrics.overall_score,
            metrics.verdict,
            relevance_judge.score,
            accuracy_judge.score,
            accuracy_judge.evidence_source,
            hallucination_judge.supported_claims,
            hallucination_judge.total_claims
        )
        return response


# Global singleton orchestrator
_orchestrator = None

def get_orchestrator() -> EvaluationOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = EvaluationOrchestrator()
    return _orchestrator
