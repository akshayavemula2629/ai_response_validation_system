"""
Completeness Judge Agent.
Evaluates the extent to which the AI response covers the necessary information
provided in the reference answer.
"""
import logging
import re
from typing import List, Tuple

from backend.api.schemas.evaluation import DimensionScore
from backend.services.llm_service import get_llm_service
from backend.knowledge_base.chunking import split_into_sentences
from backend.retrieval.embeddings import get_embedding_manager

logger = logging.getLogger(__name__)


class CompletenessJudgeAgent:
    """Agent responsible for measuring informational coverage and recall against the reference answer."""

    def evaluate(
        self,
        question: str,
        ai_response: str,
        reference_answer: str
    ) -> Tuple[DimensionScore, List[str]]:
        """
        Evaluates completeness of AI response relative to the ground truth reference answer.
        Returns (DimensionScore, missing_information_list).
        """
        llm_service = get_llm_service()
        active_llm = llm_service.get_active_client()

        # If LLM is available, use LLM-as-a-Judge
        if active_llm is not None:
            prompt = (
                f"You are a strict Completeness Judge evaluating an AI response.\n"
                f"Question: \"{question}\"\n"
                f"Reference Answer (Required Information): \"{reference_answer}\"\n"
                f"AI Response to Evaluate: \"{ai_response}\"\n\n"
                f"Determine whether the AI response covers all crucial factual elements from the reference answer.\n"
                f"Return JSON format:\n"
                f"{{\n"
                f"  \"score\": <float between 0 and 100>,\n"
                f"  \"missing_information\": [\"<missing element 1>\", \"<missing element 2>\"],\n"
                f"  \"explanation\": \"<concise explanation>\"\n"
                f"}}"
            )
            result = active_llm.evaluate_json(prompt, system_prompt="You are an expert completeness evaluator.")
            if result and "score" in result and "explanation" in result:
                missing = result.get("missing_information", [])
                return DimensionScore(
                    score=round(float(result["score"]), 1),
                    explanation=str(result["explanation"])
                ), [str(m) for m in missing]

        # Local coverage analysis
        return self._evaluate_local(ai_response, reference_answer)

    def _evaluate_local(self, ai_response: str, reference_answer: str) -> Tuple[DimensionScore, List[str]]:
        """Algorithmic evaluation of informational completeness using sentence and concept coverage."""
        embedding_mgr = get_embedding_manager()

        ref_sentences = split_into_sentences(reference_answer)
        if not ref_sentences:
            ref_sentences = [reference_answer]

        missing_items: List[str] = []
        covered_count = 0

        # Embed all sentences
        ai_emb = embedding_mgr.embed_text(ai_response)

        for sentence in ref_sentences:
            s_emb = embedding_mgr.embed_text(sentence)
            similarity = embedding_mgr.compute_cosine_similarity(s_emb, ai_emb)

            # Also check if critical nouns/numbers from this sentence are in the response
            words = set(re.findall(r'\b[A-Za-z0-9]{3,}\b', sentence.lower()))
            stopwords = {"the", "and", "for", "with", "that", "this", "from", "are", "was", "were", "been"}
            key_words = words - stopwords

            ai_lower = ai_response.lower()
            keyword_coverage = (
                sum(1 for w in key_words if w in ai_lower) / len(key_words)
                if key_words else 1.0
            )

            # Sentence is considered covered if either semantic similarity is high or keyword coverage is strong
            if similarity >= 0.65 or (keyword_coverage >= 0.60 and similarity >= 0.45):
                covered_count += 1
            else:
                # Add summary of missing concept
                trimmed = sentence[:100] + ("..." if len(sentence) > 100 else "")
                missing_items.append(f"Missing context: \"{trimmed}\"")

        total_points = len(ref_sentences)
        coverage_ratio = covered_count / total_points if total_points > 0 else 1.0

        # Word length sufficiency ratio
        length_ratio = min(1.0, len(ai_response.split()) / max(1, len(reference_answer.split()) * 0.75))

        raw_score = (coverage_ratio * 80.0) + (length_ratio * 20.0)
        score = round(max(5.0, min(100.0, raw_score)), 1)

        if score >= 85.0:
            explanation = "The response thoroughly addresses all key factual aspects and necessary context found in the reference answer."
        elif score >= 60.0:
            explanation = f"The response covers primary points but omits notable details ({len(missing_items)} aspects unaddressed)."
        else:
            explanation = f"The response is deficient in necessary information, omitting {len(missing_items)} critical reference concepts."

        return DimensionScore(score=score, explanation=explanation), missing_items
