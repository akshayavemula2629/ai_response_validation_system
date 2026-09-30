"""
Completeness Judge Agent.
Evaluates the extent to which the AI response covers the necessary information
provided in the reference answer.
"""
import logging
import re
from typing import List, Tuple

from backend.api.schemas.evaluation import DimensionScore, CompletenessJudgeResult
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
    ) -> Tuple[DimensionScore, List[str], CompletenessJudgeResult]:
        """
        Evaluates completeness of AI response relative to question requirements and reference ground truth.
        Returns:
            Tuple[DimensionScore, missing_items, CompletenessJudgeResult]
        """
        llm_service = get_llm_service()
        active_llm = llm_service.get_active_client()

        # If LLM is available, use LLM-as-a-Judge
        if active_llm is not None:
            prompt = (
                f"You are a strict Completeness Judge evaluating an AI response.\n"
                f"Question: \"{question}\"\n"
                f"Reference Answer (Mandatory Ground Truth): \"{reference_answer}\"\n"
                f"AI Response to Evaluate: \"{ai_response}\"\n\n"
                f"Identify the key requirements/aspects expected from the question and reference answer.\n"
                f"Classify each requirement as Addressed, Partially Addressed, or Missing in the AI response.\n"
                f"Return JSON format:\n"
                f"{{\n"
                f"  \"score\": <float between 0 and 100>,\n"
                f"  \"addressed_aspects\": [\"<aspect 1>\", ...],\n"
                f"  \"partially_addressed_aspects\": [\"<aspect>\", ...],\n"
                f"  \"missing_aspects\": [\"<missing aspect 1>\", ...],\n"
                f"  \"reasoning\": \"<detailed qualitative explanation>\"\n"
                f"}}"
            )
            result = active_llm.evaluate_json(prompt, system_prompt="You are an expert completeness evaluator.")
            if result and "score" in result and "reasoning" in result:
                score = round(float(result["score"]), 1)
                addressed = [str(a) for a in result.get("addressed_aspects", [])]
                partial = [str(p) for p in result.get("partially_addressed_aspects", [])]
                missing = [str(m) for m in result.get("missing_aspects", [])]
                reasoning = str(result["reasoning"])

                judge_res = CompletenessJudgeResult(
                    completeness_score=score,
                    score=score,
                    addressed_aspects=addressed,
                    partially_addressed_aspects=partial,
                    missing_aspects=missing,
                    reasoning=reasoning
                )
                dim_score = DimensionScore(score=score, explanation=reasoning)
                return dim_score, missing, judge_res

        # Local deterministic coverage & aspect extraction analysis
        return self._evaluate_local(question, ai_response, reference_answer)

    def _extract_requirements(self, question: str, reference_answer: str) -> List[str]:
        """
        Extracts key expected requirements, sub-questions, and factual aspects from question and reference truth.
        """
        requirements: List[str] = []

        # 1. Extract sub-question clauses from question
        q_clean = question.strip()
        # Split on commas, conjunctions, semicolons, question marks
        sub_clauses = re.split(r'[,;]|\band\b|\balso\b|\bmention\b|\bexplain\b|\bdescribe\b|\blist\b|\bgive\b', q_clean, flags=re.IGNORECASE)
        for clause in sub_clauses:
            cleaned = clause.strip().rstrip('?').strip()
            if len(cleaned.split()) >= 3 and not re.match(r'^(what is|how to|why does|can you)$', cleaned.lower()):
                requirements.append(cleaned)

        # 2. Extract key factual sentences/concepts from reference answer
        ref_sentences = split_into_sentences(reference_answer)
        if not ref_sentences:
            ref_sentences = [reference_answer]

        for s in ref_sentences:
            s_clean = s.strip()
            if len(s_clean.split()) >= 3:
                # Add if not redundant
                if not any(s_clean.lower() in r.lower() or r.lower() in s_clean.lower() for r in requirements):
                    requirements.append(s_clean)

        # If no distinct requirements were extracted, use reference sentences directly
        if not requirements:
            requirements = ref_sentences

        return requirements

    def _evaluate_local(
        self,
        question: str,
        ai_response: str,
        reference_answer: str
    ) -> Tuple[DimensionScore, List[str], CompletenessJudgeResult]:
        """
        Algorithmic evaluation of informational completeness using aspect classification and embedding coverage.
        """
        embedding_mgr = get_embedding_manager()

        requirements = self._extract_requirements(question, reference_answer)
        if not requirements:
            requirements = [reference_answer]

        addressed_aspects: List[str] = []
        partially_addressed_aspects: List[str] = []
        missing_aspects: List[str] = []

        ai_sentences = split_into_sentences(ai_response)
        if not ai_sentences:
            ai_sentences = [ai_response]

        # Pre-embed AI sentences
        ai_embs = [embedding_mgr.embed_text(s) for s in ai_sentences]
        ai_lower = ai_response.lower()

        stopwords = {
            "the", "and", "for", "with", "that", "this", "from", "are", "was",
            "were", "been", "have", "has", "had", "does", "will", "would", "about"
        }

        for req in requirements:
            req_emb = embedding_mgr.embed_text(req)

            # Max similarity against any sentence in response
            similarities = [
                embedding_mgr.compute_cosine_similarity(req_emb, emb)
                for emb in ai_embs
            ]
            max_sim = max(similarities) if similarities else 0.0

            # Keyword coverage
            req_words = set(re.findall(r'\b[A-Za-z0-9]{3,}\b', req.lower()))
            key_words = req_words - stopwords
            keyword_cov = (
                sum(1 for w in key_words if w in ai_lower) / len(key_words)
                if key_words else 1.0
            )

            # 3-Tier Classification: Addressed, Partially Addressed, Missing
            if max_sim >= 0.65 or (keyword_cov >= 0.65 and max_sim >= 0.45):
                addressed_aspects.append(req)
            elif max_sim >= 0.42 or (keyword_cov >= 0.35 and max_sim >= 0.28):
                partially_addressed_aspects.append(req)
            else:
                trimmed = req[:120] + ("..." if len(req) > 120 else "")
                missing_aspects.append(trimmed)

        total_reqs = len(requirements)
        # Normalized weighted coverage
        coverage_score = (
            (len(addressed_aspects) * 1.0) +
            (len(partially_addressed_aspects) * 0.5)
        ) / total_reqs if total_reqs > 0 else 1.0

        # Word length sufficiency ratio
        length_ratio = min(1.0, len(ai_response.split()) / max(1, len(reference_answer.split()) * 0.70))

        raw_score = (coverage_score * 80.0) + (length_ratio * 20.0)
        score = round(max(5.0, min(100.0, raw_score)), 1)

        # Formulate M3 qualitative reasoning
        if score >= 90.0:
            category = "Fully Complete"
            reasoning = (
                f"The response is {category} ({score}/100). It thoroughly addresses all {len(addressed_aspects)} key "
                f"requirements and expected information points established in the reference ground truth without notable omissions."
            )
        elif score >= 75.0:
            category = "Mostly Complete"
            reasoning = (
                f"The response is {category} ({score}/100). It addresses primary aspects ({len(addressed_aspects)} covered) "
                f"with minor omissions ({len(missing_aspects)} unaddressed concept(s))."
            )
        elif score >= 50.0:
            category = "Partially Complete"
            omission_summary = "; ".join(missing_aspects[:2]) if missing_aspects else "certain contextual details"
            reasoning = (
                f"The response is {category} ({score}/100). While partial context is provided, significant expected "
                f"aspects are omitted: {omission_summary}."
            )
        elif score >= 25.0:
            category = "Substantially Incomplete"
            reasoning = (
                f"The response is {category} ({score}/100). Major portions of the required explanation are omitted "
                f"({len(missing_aspects)} essential aspect(s) omitted)."
            )
        else:
            category = "Severely Incomplete"
            reasoning = (
                f"The response is {category} ({score}/100). It omits virtually all of the expected information "
                f"points and context from the ground truth reference."
            )

        judge_result = CompletenessJudgeResult(
            completeness_score=score,
            score=score,
            addressed_aspects=addressed_aspects,
            partially_addressed_aspects=partially_addressed_aspects,
            missing_aspects=missing_aspects,
            reasoning=reasoning
        )
        dimension_score = DimensionScore(score=score, explanation=reasoning)

        return dimension_score, missing_aspects, judge_result
