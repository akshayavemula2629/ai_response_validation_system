"""
Semantic similarity calculation between AI-generated response and reference material.
Uses embedding-based cosine similarity while maintaining clear distinction from factual correctness.
"""
from typing import List, Optional
from backend.retrieval.embeddings import get_embedding_manager
from backend.api.schemas.evaluation import SimilarityEvaluation


def calculate_semantic_similarity(
    ai_response: str,
    reference_answer: str,
    retrieved_evidence: Optional[List[str]] = None
) -> SimilarityEvaluation:
    """
    Computes embedding-based semantic similarity percentage between the AI response
    and the reference answer (and optional retrieved evidence).

    Returns a SimilarityEvaluation containing the similarity percentage (0-100)
    and an explanation emphasizing that semantic similarity does not equate to factual accuracy.
    """
    embedding_mgr = get_embedding_manager()

    emb_ai = embedding_mgr.embed_text(ai_response)
    emb_ref = embedding_mgr.embed_text(reference_answer)

    base_similarity = embedding_mgr.compute_cosine_similarity(emb_ai, emb_ref)

    # If retrieved evidence is provided, also measure alignment with the strongest evidence chunk
    if retrieved_evidence and len(retrieved_evidence) > 0:
        evidence_similarities = [
            embedding_mgr.compute_cosine_similarity(emb_ai, embedding_mgr.embed_text(ev))
            for ev in retrieved_evidence if ev.strip()
        ]
        if evidence_similarities:
            max_evidence_sim = max(evidence_similarities)
            # Weighted blend: 75% direct reference match, 25% highest evidence alignment
            combined_similarity = 0.75 * base_similarity + 0.25 * max_evidence_sim
        else:
            combined_similarity = base_similarity
    else:
        combined_similarity = base_similarity

    percentage = round(float(combined_similarity * 100.0), 1)

    # Generate explanatory note distinguishing similarity from truth
    if percentage >= 85.0:
        tier_desc = f"The AI response exhibits high semantic similarity ({percentage}%) with the reference material, sharing substantially similar vocabulary and conceptual themes."
    elif percentage >= 60.0:
        tier_desc = f"The AI response exhibits moderate semantic similarity ({percentage}%) with the reference material. While core topics align, there are notable deviations in phrasing, coverage, or supporting details."
    else:
        tier_desc = f"The AI response exhibits low semantic similarity ({percentage}%) with the reference material, indicating significant divergence in subject matter, vocabulary, or topical focus."

    explanation = (
        f"{tier_desc} Note: Semantic similarity measures structural and lexical alignment and is distinct from factual correctness or truthfulness."
    )

    return SimilarityEvaluation(
        percentage=percentage,
        explanation=explanation
    )
