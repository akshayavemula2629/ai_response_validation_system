"""
Evaluation and Retrieval API Routes.
Exposes POST /api/evaluate and GET /api/retrieval endpoints.
"""
import logging
from typing import List, Optional
from fastapi import APIRouter, Query, status

from backend.api.schemas.evaluation import (
    EvaluationRequest,
    EvaluationResponse,
    RetrievedEvidenceItem
)
from backend.agents.orchestrator import get_orchestrator
from backend.retrieval.retriever import retrieve_relevant_context

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Evaluation"])


@router.post(
    "/evaluate",
    response_model=EvaluationResponse,
    status_code=status.HTTP_200_OK,
    summary="Evaluate an AI Response against Question and Reference Ground Truth",
    description=(
        "Performs comprehensive evaluation across Relevance, Accuracy, Hallucination Risk, "
        "and Completeness. Retrieves relevant Knowledge Base evidence, computes semantic similarity, "
        "detects factual contradictions, generates a grounded Better Answer when needed, "
        "and delivers an overall verdict score with comparison metrics."
    )
)
def evaluate_response(request: EvaluationRequest) -> EvaluationResponse:
    """Evaluates the submitted AI response."""
    orchestrator = get_orchestrator()
    return orchestrator.evaluate(request)


@router.get(
    "/retrieval",
    response_model=List[RetrievedEvidenceItem],
    status_code=status.HTTP_200_OK,
    summary="Independent Semantic Retrieval from Knowledge Base",
    description="Query the indexed TruthfulQA and SQuAD knowledge base for top-k relevant evidence chunks."
)
def search_knowledge_base(
    question: str = Query(..., description="Query string to search in the knowledge base"),
    top_k: int = Query(3, ge=1, le=10, description="Number of evidence chunks to retrieve"),
    threshold: float = Query(0.1, ge=0.0, le=1.0, description="Minimum cosine similarity threshold")
) -> List[RetrievedEvidenceItem]:
    """Retrieves relevant context chunks independently."""
    return retrieve_relevant_context(question, top_k=top_k, threshold=threshold)
