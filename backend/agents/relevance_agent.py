"""
Relevance Judge Agent.
Evaluates how directly and appropriately the AI response addresses the user's question.
"""
import logging
import re
from typing import Dict, Any, Optional, Tuple

from backend.api.schemas.evaluation import DimensionScore, RelevanceJudgeResult
from backend.services.llm_service import get_llm_service
from backend.retrieval.embeddings import get_embedding_manager

logger = logging.getLogger(__name__)


def map_score_to_relevance_category(score_1_to_5: int) -> str:
    """Maps a 1-5 score to its descriptive category."""
    categories = {
        5: "Fully Relevant",
        4: "Mostly Relevant",
        3: "Partially Relevant",
        2: "Barely Relevant",
        1: "Irrelevant / Off-topic"
    }
    return categories.get(score_1_to_5, "Irrelevant / Off-topic")


def map_pct_to_relevance_1_to_5(score_0_100: float) -> Tuple[int, str]:
    """Maps a 0-100 normalized score to a 1-5 integer score and category."""
    if score_0_100 >= 85.0:
        return 5, "Fully Relevant"
    elif score_0_100 >= 68.0:
        return 4, "Mostly Relevant"
    elif score_0_100 >= 48.0:
        return 3, "Partially Relevant"
    elif score_0_100 >= 28.0:
        return 2, "Barely Relevant"
    else:
        return 1, "Irrelevant / Off-topic"


class RelevanceJudgeAgent:
    """Agent responsible for assessing question-answer relevance and intent alignment on 1-5 scale."""

    def evaluate(self, question: str, ai_response: str) -> Tuple[DimensionScore, RelevanceJudgeResult]:
        """
        Evaluates relevance of AI response to the submitted question.
        Returns a tuple of (DimensionScore, RelevanceJudgeResult).
        """
        llm_service = get_llm_service()
        active_llm = llm_service.get_active_client()

        # If external LLM is available, use LLM-as-a-Judge
        if active_llm is not None:
            prompt = (
                f"You are a strict Relevance Judge evaluating an AI response on a 1-5 integer scale.\n"
                f"Scale:\n"
                f"5 = Fully Relevant: Directly and completely addresses the prompt without digressions.\n"
                f"4 = Mostly Relevant: Directly addresses the prompt with minor extra or indirect context.\n"
                f"3 = Partially Relevant: Partially addresses the prompt but drifts into tangential topics.\n"
                f"2 = Barely Relevant: Touches loosely on the topic but fails to directly answer the question.\n"
                f"1 = Irrelevant / Off-topic: Completely off-topic or unresponsive.\n\n"
                f"Question: \"{question}\"\n"
                f"AI Response: \"{ai_response}\"\n\n"
                f"Return JSON format:\n"
                f"{{\n"
                f"  \"score_1_to_5\": <integer 1 to 5>,\n"
                f"  \"score_normalized\": <float between 0 and 100>,\n"
                f"  \"category\": \"<Fully Relevant|Mostly Relevant|Partially Relevant|Barely Relevant|Irrelevant / Off-topic>\",\n"
                f"  \"reasoning\": \"<concise explanation>\"\n"
                f"}}"
            )
            result = active_llm.evaluate_json(prompt, system_prompt="You are an expert AI relevance judge.")
            if result and "score_1_to_5" in result:
                s_1_5 = max(1, min(5, int(result.get("score_1_to_5", 5))))
                norm_score = float(result.get("score_normalized", s_1_5 * 20.0))
                category = str(result.get("category", map_score_to_relevance_category(s_1_5)))
                reasoning = str(result.get("reasoning", result.get("explanation", "")))

                dim_score = DimensionScore(score=round(norm_score, 1), explanation=reasoning)
                judge_result = RelevanceJudgeResult(
                    score=s_1_5,
                    score_normalized=round(norm_score, 1),
                    category=category,
                    reasoning=reasoning,
                    explanation=reasoning
                )
                return dim_score, judge_result

        # Local semantic and intent alignment evaluation
        return self._evaluate_local(question, ai_response)

    def _evaluate_local(self, question: str, ai_response: str) -> Tuple[DimensionScore, RelevanceJudgeResult]:
        """Algorithmic evaluation of relevance using embedding alignment and intent matching."""
        embedding_mgr = get_embedding_manager()

        emb_q = embedding_mgr.embed_text(question)
        emb_a = embedding_mgr.embed_text(ai_response)

        sem_similarity = embedding_mgr.compute_cosine_similarity(emb_q, emb_a)

        # Keyword and entity overlap analysis
        q_words = set(re.findall(r'\b[a-zA-Z0-9]{3,}\b', question.lower()))
        stopwords = {"what", "when", "where", "which", "who", "whom", "whose", "why", "how", "the", "and", "for", "are", "is", "was", "were", "did", "does"}
        meaningful_q_words = q_words - stopwords

        a_lower = ai_response.lower()
        if meaningful_q_words:
            matched_words = [w for w in meaningful_q_words if w in a_lower]
            keyword_overlap_ratio = len(matched_words) / len(meaningful_q_words)
        else:
            keyword_overlap_ratio = 1.0

        # Interrogative intent check
        penalty = 0.0
        q_lower = question.lower()
        if any(q_lower.startswith(w) for w in ["when", "what year", "what date"]) and not re.search(r'\b(19\d\d|20\d\d|century|january|february|march|april|may|june|july|august|september|october|november|december)\b', a_lower):
            penalty += 20.0
        elif any(q_lower.startswith(w) for w in ["who", "whose", "which person"]) and not re.search(r'\b[A-Z][a-z]+\b', ai_response):
            penalty += 15.0

        # Weighted calculation: 60% semantic similarity + 40% keyword overlap - penalties
        raw_score = (sem_similarity * 65.0) + (keyword_overlap_ratio * 35.0) - penalty
        score = round(max(5.0, min(100.0, raw_score)), 1)

        score_1_to_5, category = map_pct_to_relevance_1_to_5(score)

        if score_1_to_5 == 5:
            explanation = "The response directly and clearly addresses the core intent and specific subject of the question."
        elif score_1_to_5 == 4:
            explanation = "The response addresses the general topic of the question but includes tangential or indirect information."
        elif score_1_to_5 == 3:
            explanation = "The response only partially relates to the question, diverting into off-topic or ambiguous details."
        elif score_1_to_5 == 2:
            explanation = "The response barely touches upon the requested subject and largely deviates from user intent."
        else:
            explanation = "The response fails to address the question and is completely irrelevant or unresponsive to the prompt."

        dim_score = DimensionScore(score=score, explanation=explanation)
        judge_res = RelevanceJudgeResult(
            score=score_1_to_5,
            score_normalized=score,
            category=category,
            reasoning=explanation,
            explanation=explanation
        )
        return dim_score, judge_res
