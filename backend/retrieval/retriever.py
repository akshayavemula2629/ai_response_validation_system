"""
RAG Semantic Retrieval Pipeline.
Exposes independent, testable retrieval interface for querying the Knowledge Base.
"""
import logging
from typing import List, Optional
from backend.config import settings
from backend.retrieval.embeddings import get_embedding_manager
from backend.retrieval.vector_store import get_vector_store
from backend.api.schemas.evaluation import RetrievedEvidenceItem

logger = logging.getLogger(__name__)


def retrieve_relevant_context(
    question: str,
    top_k: Optional[int] = None,
    threshold: Optional[float] = None
) -> List[RetrievedEvidenceItem]:
    """
    Retrieves top-k relevant evidence chunks from the knowledge base for a given question.
    
    Args:
        question: The user query to search against the indexed evidence.
        top_k: Number of chunks to retrieve (defaults to settings.TOP_K_RETRIEVAL).
        threshold: Minimum cosine similarity score (defaults to settings.SIMILARITY_THRESHOLD).
        
    Returns:
        List of RetrievedEvidenceItem instances.
    """
    if not question or not question.strip():
        return []

    k = top_k if top_k is not None else settings.TOP_K_RETRIEVAL
    sim_threshold = threshold if threshold is not None else settings.SIMILARITY_THRESHOLD

    vector_store = get_vector_store()
    if not vector_store.is_ready():
        logger.warning("Retrieval invoked but vector store is not initialized or empty.")
        return []

    embedding_mgr = get_embedding_manager()
    query_emb = embedding_mgr.embed_text(question.strip())

    matches = vector_store.search(query_emb, top_k=k, threshold=sim_threshold)

    results: List[RetrievedEvidenceItem] = []
    for meta, score in matches:
        # Build readable content string
        content = meta.get("chunk_text") or meta.get("context") or meta.get("answer") or ""
        results.append(RetrievedEvidenceItem(
            chunk_id=meta.get("chunk_id", "unknown"),
            content=content,
            source=meta.get("source", meta.get("dataset", "Knowledge Base")),
            similarity_score=round(float(score), 4)
        ))

    logger.info("Retrieved %d relevant evidence chunks for query: '%s'", len(results), question[:50])
    return results
