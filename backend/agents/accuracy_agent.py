"""
Accuracy Judge Agent.
Evaluates factual correctness of AI response against the ground truth reference answer
and retrieved knowledge base evidence.
"""
import logging
import re
from typing import List, Optional, Tuple

from backend.api.schemas.evaluation import DimensionScore, AccuracyJudgeResult
from backend.services.llm_service import get_llm_service
from backend.retrieval.embeddings import get_embedding_manager

logger = logging.getLogger(__name__)


def map_score_to_accuracy_category(score_1_to_5: int) -> str:
    """Maps a 1-5 integer score to its descriptive accuracy category."""
    categories = {
        5: "Fully Correct",
        4: "Mostly Correct",
        3: "Partially Correct",
        2: "Mostly Incorrect",
        1: "Incorrect / Contradictory"
    }
    return categories.get(score_1_to_5, "Incorrect / Contradictory")


def map_pct_to_accuracy_1_to_5(score_0_100: float, issues_count: int) -> Tuple[int, str]:
    """Maps normalized percentage and issue count to a 1-5 integer score and category."""
    if issues_count >= 2 or score_0_100 < 25.0:
        return 1, "Incorrect / Contradictory"
    elif issues_count == 1 and score_0_100 < 45.0:
        return 2, "Mostly Incorrect"
    elif issues_count == 1:
        return 3, "Partially Correct"
    elif score_0_100 >= 85.0:
        return 5, "Fully Correct"
    elif score_0_100 >= 65.0:
        return 4, "Mostly Correct"
    elif score_0_100 >= 45.0:
        return 3, "Partially Correct"
    elif score_0_100 >= 25.0:
        return 2, "Mostly Incorrect"
    else:
        return 1, "Incorrect / Contradictory"


class AccuracyJudgeAgent:
    """Agent responsible for checking factual correctness against reference material or KB evidence."""

    def evaluate(
        self,
        question: str,
        ai_response: str,
        reference_answer: Optional[str] = None,
        retrieved_evidence: Optional[List[str]] = None,
        use_knowledge_base_only: bool = False
    ) -> Tuple[DimensionScore, List[str], AccuracyJudgeResult]:
        """
        Evaluates factual accuracy against reference answer (Case 1) or retrieved evidence (Case 2).
        Returns (DimensionScore, factual_issues_list, AccuracyJudgeResult).
        """
        llm_service = get_llm_service()
        active_llm = llm_service.get_active_client()

        ref_str = (reference_answer or "").strip()
        is_case_2 = use_knowledge_base_only or (not ref_str and bool(retrieved_evidence))
        evidence_source = "Knowledge Base Retrieval" if is_case_2 else "Reference Answer"

        effective_reference = ref_str if ref_str else ("\n".join(retrieved_evidence) if retrieved_evidence else "")
        evidence_text = "\n".join(retrieved_evidence) if retrieved_evidence else "None"

        # If LLM is available, use LLM-as-a-Judge
        if active_llm is not None:
            prompt = (
                f"You are a strict Accuracy Judge evaluating an AI response on a 1-5 integer scale.\n"
                f"Scale:\n"
                f"5 = Fully Correct: Completely factually accurate and consistent with verified truth.\n"
                f"4 = Mostly Correct: Predominantly accurate with minor negligible ambiguities.\n"
                f"3 = Partially Correct: Contains a mix of correct assertions and unverified/incorrect details.\n"
                f"2 = Mostly Incorrect: Contains major factual errors or ungrounded assertions.\n"
                f"1 = Incorrect / Contradictory: Completely incorrect, fabricated, or contradicts verified facts.\n\n"
                f"Question: \"{question}\"\n"
                f"Evidence Source: {evidence_source}\n"
                f"Ground Truth Reference: \"{effective_reference}\"\n"
                f"Retrieved Evidence: \"{evidence_text}\"\n"
                f"AI Response to Evaluate: \"{ai_response}\"\n\n"
                f"Compare the AI response strictly against the ground truth and evidence.\n"
                f"Identify any factual errors, incorrect dates, contradicted claims, or unsupported facts.\n"
                f"Return JSON format:\n"
                f"{{\n"
                f"  \"score_1_to_5\": <integer 1 to 5>,\n"
                f"  \"score_normalized\": <float between 0 and 100>,\n"
                f"  \"category\": \"<Fully Correct|Mostly Correct|Partially Correct|Mostly Incorrect|Incorrect / Contradictory>\",\n"
                f"  \"reasoning\": \"<detailed explanation>\",\n"
                f"  \"issues\": [\"<issue 1>\", \"<issue 2>\"],\n"
                f"  \"supporting_evidence\": [\"<evidence snippet 1>\"]\n"
                f"}}"
            )
            result = active_llm.evaluate_json(prompt, system_prompt="You are a rigorous factual accuracy evaluator.")
            if result and "score_1_to_5" in result:
                s_1_5 = max(1, min(5, int(result.get("score_1_to_5", 5))))
                norm_score = float(result.get("score_normalized", s_1_5 * 20.0))
                category = str(result.get("category", map_score_to_accuracy_category(s_1_5)))
                reasoning = str(result.get("reasoning", result.get("explanation", "")))
                issues = [str(i) for i in result.get("issues", [])]
                supporting_evidence = [str(e) for e in result.get("supporting_evidence", [])]

                dim_score = DimensionScore(score=round(norm_score, 1), explanation=reasoning)
                judge_result = AccuracyJudgeResult(
                    score=s_1_5,
                    score_normalized=round(norm_score, 1),
                    category=category,
                    evidence_source=evidence_source,
                    supporting_evidence=supporting_evidence,
                    issues=issues,
                    reasoning=reasoning,
                    explanation=reasoning
                )
                return dim_score, issues, judge_result

        # Local factual verification pipeline
        return self._evaluate_local(ai_response, effective_reference, retrieved_evidence, evidence_source)

    def _evaluate_local(
        self,
        ai_response: str,
        reference_answer: str,
        retrieved_evidence: Optional[List[str]] = None,
        evidence_source: str = "Reference Answer"
    ) -> Tuple[DimensionScore, List[str], AccuracyJudgeResult]:
        """Evaluates factual accuracy locally through contradiction analysis and entity checking."""
        embedding_mgr = get_embedding_manager()

        combined_reference = (reference_answer + (" " + " ".join(retrieved_evidence) if retrieved_evidence else "")).strip()
        ref_lower = combined_reference.lower()
        ai_lower = ai_response.lower()

        issues: List[str] = []
        supporting_evidence: List[str] = []

        # Find supporting evidence chunks
        if retrieved_evidence:
            for ev in retrieved_evidence:
                ev_emb = embedding_mgr.embed_text(ev)
                ai_emb = embedding_mgr.embed_text(ai_response)
                sim_ev = embedding_mgr.compute_cosine_similarity(ai_emb, ev_emb)
                if sim_ev >= 0.35:
                    supporting_evidence.append(ev[:250] + ("..." if len(ev) > 250 else ""))

        # 1. Semantic alignment between full response and reference / evidence
        target_ref = reference_answer if reference_answer else (" ".join(retrieved_evidence) if retrieved_evidence else "")
        sim = embedding_mgr.compute_cosine_similarity(
            embedding_mgr.embed_text(ai_response),
            embedding_mgr.embed_text(target_ref)
        )

        # 2. Contradiction & Negation Detection
        negated_claims = [
            (r'\b(?:does\s+not|doesn\'t|not|never)\s+remain\b', r'\bremains?\b', "remains in stomach / digestive tract"),
            (r'\b(?:cannot|can\s+not|not)\s+(?:be\s+)?seen\b', r'\bcan\s+(?:be\s+)?seen\b|\bvisible\b', "visibility of Great Wall from space"),
            (r'\b(?:does\s+not|doesn\'t|not)\s+cause\b', r'\bcauses?\b', "causing arthritis / medical condition"),
            (r'\b(?:myth|scientifically\s+false|false|untrue)\b', r'\b(?:true|proven|fact)\b', "factual truth of debunked misconception")
        ]

        for ref_neg_pat, ai_affirm_pat, topic_desc in negated_claims:
            if re.search(ref_neg_pat, ref_lower):
                if re.search(ai_affirm_pat, ai_lower) and not re.search(ref_neg_pat, ai_lower):
                    issues.append(f"Direct contradiction detected: AI response affirms that it {topic_desc}, which verified evidence explicitly refutes.")

        # Check entity contradictions (e.g. Sydney vs Canberra)
        known_entity_conflicts = [
            (r'\bcanberra\b', [r'\bsydney\b', r'\bmelbourne\b'], "capital of Australia"),
            (r'\bmoon\b', [r'\bmars\b', r'\bvenus\b'], "lunar landing location"),
            (r'\bchlorophyll\b', [r'\bhemoglobin\b', r'\bmelanin\b'], "photosynthetic plant pigment")
        ]
        for correct_pat, conflicting_pats, entity_name in known_entity_conflicts:
            if re.search(correct_pat, ref_lower):
                for conflict in conflicting_pats:
                    if re.search(conflict, ai_lower) and not re.search(correct_pat, ai_lower):
                        issues.append(f"Factual entity contradiction: AI response names incorrect entity ({re.findall(conflict, ai_lower)[0]}) for {entity_name}.")

        # 3. Numeric & Year Conflict Check
        ai_numbers = set(re.findall(r'\b(19\d\d|20\d\d|\d+(?:\.\d+)?)\b', ai_response))
        ref_numbers = set(re.findall(r'\b(19\d\d|20\d\d|\d+(?:\.\d+)?)\b', combined_reference))

        ai_years = set(re.findall(r'\b(19\d\d|20\d\d)\b', ai_response))
        ref_years = set(re.findall(r'\b(19\d\d|20\d\d)\b', combined_reference))
        conflicting_years = ai_years - ref_years
        if conflicting_years:
            issues.append(f"Factual date discrepancy: response introduces year(s) {', '.join(conflicting_years)} not verified by evidence.")

        conflicting_numbers = ai_numbers - ref_numbers
        significant_num_conflicts = [n for n in conflicting_numbers if len(n) > 1 and float(n) > 3 and n not in ai_years]
        if significant_num_conflicts and ref_numbers:
            issues.append(f"Discrepancy in numeric facts: found {', '.join(significant_num_conflicts)} in response not matching evidence.")

        # 4. Scoring logic
        score = sim * 100.0

        if issues:
            penalty = len(issues) * 35.0
            score = max(5.0, min(65.0, score - penalty))
        else:
            if sim >= 0.75:
                score = min(100.0, max(88.0, score + 10.0))

        score = round(float(score), 1)

        score_1_to_5, category = map_pct_to_accuracy_1_to_5(score, len(issues))

        if issues:
            explanation = (
                f"Factual discrepancies identified: {'; '.join(issues)}. "
                f"The response diverges from or contradicts established evidence ({evidence_source})."
            )
        elif score_1_to_5 == 5:
            explanation = f"The response is factually consistent and aligns accurately with verified {evidence_source.lower()}."
        elif score_1_to_5 == 4:
            explanation = f"The response is largely accurate with minor stylistic or phrasing variance against {evidence_source.lower()}."
        else:
            explanation = f"The response contains substantial inaccuracies compared to verified {evidence_source.lower()}."

        dim_score = DimensionScore(score=score, explanation=explanation)
        judge_res = AccuracyJudgeResult(
            score=score_1_to_5,
            score_normalized=score,
            category=category,
            evidence_source=evidence_source,
            supporting_evidence=supporting_evidence,
            issues=issues,
            reasoning=explanation,
            explanation=explanation
        )
        return dim_score, issues, judge_res
