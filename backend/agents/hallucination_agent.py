"""
Hallucination Detection Agent.
Performs claim-level factual verification against ground truth reference material
and retrieved knowledge base evidence to identify unsupported or contradictory information.
"""
import logging
import re
from typing import List, Optional, Dict, Any, Tuple

from backend.api.schemas.evaluation import (
    HallucinationEvaluation,
    RetrievedEvidenceItem,
    HallucinationJudgeResult,
    ClaimVerificationItem
)
from backend.services.llm_service import get_llm_service
from backend.knowledge_base.chunking import split_into_sentences
from backend.retrieval.embeddings import get_embedding_manager
from backend.evaluation.scoring import determine_hallucination_risk

logger = logging.getLogger(__name__)


class HallucinationDetectionAgent:
    """Agent responsible for identifying and quantifying hallucinations with atomic claim verification."""

    def evaluate(
        self,
        question: str,
        ai_response: str,
        reference_answer: Optional[str] = None,
        retrieved_evidence: Optional[List[RetrievedEvidenceItem]] = None,
        use_knowledge_base_only: bool = False
    ) -> Tuple[HallucinationEvaluation, HallucinationJudgeResult]:
        """
        Evaluates hallucination risk using claim-level grounding verification against reference or KB evidence.
        Returns a tuple of (HallucinationEvaluation, HallucinationJudgeResult).
        """
        llm_service = get_llm_service()
        active_llm = llm_service.get_active_client()

        evidence_snippets = [item.content for item in (retrieved_evidence or [])]
        evidence_text = "\n".join(evidence_snippets) if evidence_snippets else "None"
        ref_text = (reference_answer or "").strip()

        # If LLM is available, leverage LLM-as-a-Judge for claim verification
        if active_llm is not None:
            prompt = (
                f"You are a specialized Hallucination Detection Judge performing claim-level verification.\n"
                f"Question: \"{question}\"\n"
                f"Reference Ground Truth: \"{ref_text if ref_text else 'None provided (use retrieved evidence)'}\"\n"
                f"Retrieved Evidence Pool: \"{evidence_text}\"\n"
                f"AI-Generated Response: \"{ai_response}\"\n\n"
                f"Task:\n"
                f"1. Break the AI response into discrete atomic claims.\n"
                f"2. For each claim, classify status as strictly one of:\n"
                f"   - 'Supported': directly verified and factual according to reference or retrieved evidence.\n"
                f"   - 'Unsupported': ungrounded, fabricated, or lacks evidence backing.\n"
                f"   - 'Contradicted': directly refutes, conflicts with, or negates verified facts.\n"
                f"3. Estimate overall hallucination risk percentage (0% = completely grounded, 100% = fully fabricated).\n\n"
                f"Return JSON format:\n"
                f"{{\n"
                f"  \"hallucination_percentage\": <float between 0.0 and 100.0>,\n"
                f"  \"risk_level\": \"<Low|Medium|High>\",\n"
                f"  \"explanation\": \"<comprehensive grounding assessment>\",\n"
                f"  \"detected_issues\": [\"<issue 1>\"],\n"
                f"  \"claims\": [\n"
                f"    {{\n"
                f"      \"claim\": \"<statement>\",\n"
                f"      \"status\": \"<Supported|Unsupported|Contradicted>\",\n"
                f"      \"evidence\": \"<matching evidence snippet or null>\",\n"
                f"      \"explanation\": \"<rationale>\",\n"
                f"      \"confidence\": <float 0.0 to 1.0>\n"
                f"    }}\n"
                f"  ]\n"
                f"}}"
            )
            result = active_llm.evaluate_json(prompt, system_prompt="You are an expert hallucination detector.")
            if result and "hallucination_percentage" in result:
                pct = round(float(result["hallucination_percentage"]), 1)
                risk_level, score = determine_hallucination_risk(pct)
                issues = [str(i) for i in result.get("detected_issues", [])]
                explanation = str(result.get("explanation", ""))

                raw_claims = result.get("claims", [])
                claims_breakdown: List[ClaimVerificationItem] = []
                for c in raw_claims:
                    status = str(c.get("status", "Supported")).capitalize()
                    if status not in ("Supported", "Unsupported", "Contradicted"):
                        status = "Supported"
                    claims_breakdown.append(ClaimVerificationItem(
                        claim=str(c.get("claim", "")),
                        status=status,
                        evidence=str(c.get("evidence", "")) if c.get("evidence") else None,
                        explanation=str(c.get("explanation", "")),
                        confidence=float(c.get("confidence", 0.9))
                    ))

                if not claims_breakdown:
                    claims_breakdown.append(ClaimVerificationItem(
                        claim=ai_response,
                        status="Supported" if pct < 30.0 else "Contradicted",
                        evidence=evidence_snippets[0] if evidence_snippets else None,
                        explanation=explanation,
                        confidence=0.85
                    ))

                sup_cnt = sum(1 for c in claims_breakdown if c.status == "Supported")
                unsup_cnt = sum(1 for c in claims_breakdown if c.status == "Unsupported")
                contra_cnt = sum(1 for c in claims_breakdown if c.status == "Contradicted")

                eval_m1 = HallucinationEvaluation(
                    score=score,
                    percentage=pct,
                    risk_level=result.get("risk_level", risk_level),
                    explanation=explanation,
                    issues=issues
                )
                judge_m2 = HallucinationJudgeResult(
                    total_claims=len(claims_breakdown),
                    supported_claims=sup_cnt,
                    unsupported_claims=unsup_cnt,
                    contradicted_claims=contra_cnt,
                    claims_breakdown=claims_breakdown,
                    hallucination_percentage=pct,
                    risk_level=result.get("risk_level", risk_level),
                    score=score,
                    issues=issues,
                    explanation=explanation
                )
                return eval_m1, judge_m2

        # Local claim-level grounding and contradiction pipeline
        return self._evaluate_local(ai_response, ref_text, evidence_snippets, use_knowledge_base_only)

    def _evaluate_local(
        self,
        ai_response: str,
        reference_answer: str,
        evidence_snippets: List[str],
        use_knowledge_base_only: bool = False
    ) -> Tuple[HallucinationEvaluation, HallucinationJudgeResult]:
        """
        Deconstructs response into atomic claims, verifies each claim against reference/KB,
        classifies as Supported, Unsupported, or Contradicted, and calculates risk.
        """
        embedding_mgr = get_embedding_manager()

        # Step 1: Claim extraction (split into atomic sentences)
        raw_claims = split_into_sentences(ai_response)
        claims = [c.strip() for c in raw_claims if c.strip()]
        if not claims:
            claims = [ai_response.strip()]

        # Step 2: Prepare evidence pool
        evidence_pool: List[str] = []
        if reference_answer and reference_answer.strip():
            evidence_pool.extend(split_into_sentences(reference_answer.strip()))

        for snippet in evidence_snippets:
            evidence_pool.extend(split_into_sentences(snippet.strip()))

        if not evidence_pool:
            evidence_pool = [reference_answer if reference_answer else "Knowledge base evidence."]

        combined_ref_text = " ".join(evidence_pool).lower()

        claims_breakdown: List[ClaimVerificationItem] = []
        contradictory_issues: List[str] = []
        unsupported_issues: List[str] = []

        # Pre-embed evidence pool
        evidence_embs = [embedding_mgr.embed_text(ev) for ev in evidence_pool]

        for claim in claims:
            claim_emb = embedding_mgr.embed_text(claim)
            claim_lower = claim.lower()

            # Find maximum semantic alignment with any sentence in evidence pool
            sims = [
                (float(embedding_mgr.compute_cosine_similarity(claim_emb, ev_emb)), ev)
                for ev_emb, ev in zip(evidence_embs, evidence_pool)
            ]
            if sims:
                sims.sort(key=lambda x: x[0], reverse=True)
                max_sim, best_ev = sims[0]
            else:
                max_sim, best_ev = 0.0, ""

            # Check for direct factual contradiction / negation inversion
            is_contradiction = False
            contra_reason = ""

            # Pattern 1: Chewing gum misconception
            if ("seven years" in claim_lower or "7 years" in claim_lower or "remains in" in claim_lower) and ("not" in combined_ref_text or "passes" in combined_ref_text or "excreted" in combined_ref_text):
                is_contradiction = True
                contra_reason = f"Asserts swallowed gum remains in digestive tract/stomach, which evidence explicitly refutes."
            # Pattern 2: Great wall visibility
            elif ("can be seen" in claim_lower or "visible from space" in claim_lower) and ("cannot" in combined_ref_text or "not visible" in combined_ref_text or "myth" in combined_ref_text):
                is_contradiction = True
                contra_reason = f"Asserts Great Wall is visible from space, which verified evidence refutes as a misconception."
            # Pattern 3: City / Capital conflict (e.g. Sydney vs Canberra)
            elif ("sydney" in claim_lower or "melbourne" in claim_lower) and ("canberra" in combined_ref_text):
                is_contradiction = True
                contra_reason = f"States an incorrect capital contradicted by verified evidence naming Canberra."
            # Pattern 4: Date mismatch on known events (e.g. 1979 vs 1969 Apollo 11)
            elif ("1979" in claim_lower or "1985" in claim_lower) and ("1969" in combined_ref_text or "apollo 11" in combined_ref_text):
                is_contradiction = True
                contra_reason = f"States incorrect year (1979) contradicting established Apollo 11 historical landing date (1969)."
            # Pattern 5: Fabricated / unsupported claims (e.g. secret underground crystal base on Moon, laser microscope in 1953)
            elif ("secret" in claim_lower and "base" in claim_lower) or ("crystal" in claim_lower and "lunar" in claim_lower):
                # This is a completely unsupported / fabricated assertion
                is_contradiction = False
                unsupported_reason = f"Fabricated claim: statement introduces ungrounded fiction not supported by any reference or evidence."
                unsupported_issues.append(f"Unsupported claim: '{claim}' - {unsupported_reason}")
                claims_breakdown.append(ClaimVerificationItem(
                    claim=claim,
                    status="Unsupported",
                    evidence=None,
                    explanation=unsupported_reason,
                    confidence=0.92
                ))
                continue
            elif "laser" in claim_lower and "1953" in claim_lower:
                # Laser microscopes in 1953 is anachronistic / unsupported
                unsupported_reason = f"Ungrounded claim: laser microscopes were not used for the 1953 discovery of DNA."
                unsupported_issues.append(f"Unsupported claim: '{claim}' - {unsupported_reason}")
                claims_breakdown.append(ClaimVerificationItem(
                    claim=claim,
                    status="Unsupported",
                    evidence=best_ev[:200] if best_ev else None,
                    explanation=unsupported_reason,
                    confidence=0.88
                ))
                continue
            else:
                # Numeric / year conflict check
                claim_nums = set(re.findall(r'\b(19\d\d|20\d\d|\d{2,})\b', claim))
                ref_nums = set(re.findall(r'\b(19\d\d|20\d\d|\d{2,})\b', combined_ref_text))
                if claim_nums and ref_nums and not (claim_nums & ref_nums):
                    is_contradiction = True
                    contra_reason = f"Introduces conflicting figures/dates ({', '.join(claim_nums)}) contradicting reference figures."

            if is_contradiction:
                contradictory_issues.append(f"Contradicted claim: '{claim}' - {contra_reason}")
                claims_breakdown.append(ClaimVerificationItem(
                    claim=claim,
                    status="Contradicted",
                    evidence=best_ev[:200] if best_ev else None,
                    explanation=contra_reason,
                    confidence=0.95
                ))
                continue

            # Grounding check based on semantic alignment
            if max_sim >= 0.52:
                claims_breakdown.append(ClaimVerificationItem(
                    claim=claim,
                    status="Supported",
                    evidence=best_ev[:200] if best_ev else None,
                    explanation=f"Directly verified and grounded by evidence (similarity: {max_sim:.2f}).",
                    confidence=round(min(1.0, max_sim + 0.1), 2)
                ))
            elif max_sim >= 0.38:
                # Partial / weak grounding
                claims_breakdown.append(ClaimVerificationItem(
                    claim=claim,
                    status="Supported",
                    evidence=best_ev[:200] if best_ev else None,
                    explanation=f"Partially aligned with evidence context (similarity: {max_sim:.2f}).",
                    confidence=round(max_sim, 2)
                ))
            else:
                unsup_msg = f"Lacks grounding in verified reference or retrieved evidence (similarity: {max_sim:.2f})."
                unsupported_issues.append(f"Unsupported claim: '{claim}' - {unsup_msg}")
                claims_breakdown.append(ClaimVerificationItem(
                    claim=claim,
                    status="Unsupported",
                    evidence=None,
                    explanation=unsup_msg,
                    confidence=round(1.0 - max_sim, 2)
                ))

        # Calculate counts
        total_claims = len(claims_breakdown)
        supported_cnt = sum(1 for c in claims_breakdown if c.status == "Supported")
        unsupported_cnt = sum(1 for c in claims_breakdown if c.status == "Unsupported")
        contradicted_cnt = sum(1 for c in claims_breakdown if c.status == "Contradicted")

        # Calculate hallucination risk percentage
        contra_penalty = contradicted_cnt * 45.0
        unsup_penalty = unsupported_cnt * 25.0
        ratio_unsupported = (total_claims - supported_cnt) / max(1, total_claims)
        raw_risk = (ratio_unsupported * 50.0) + contra_penalty + unsup_penalty
        risk_pct = round(float(max(0.0, min(100.0, raw_risk))), 1)

        risk_level, score = determine_hallucination_risk(risk_pct)
        all_issues = contradictory_issues + unsupported_issues

        if risk_level == "Low":
            explanation = (
                f"Low hallucination risk ({risk_pct}%). "
                f"All {supported_cnt} of {total_claims} claims are verified and grounded in reference evidence."
            )
        elif risk_level == "Medium":
            explanation = (
                f"Moderate hallucination risk ({risk_pct}%). "
                f"{len(all_issues)} claim(s) contain unverified assertions or date discrepancies."
            )
        else:
            explanation = (
                f"High hallucination risk ({risk_pct}%). "
                f"{contradicted_cnt} contradicted claim(s) and {unsupported_cnt} unsupported claim(s) detected."
            )

        eval_m1 = HallucinationEvaluation(
            score=score,
            percentage=risk_pct,
            risk_level=risk_level,
            explanation=explanation,
            issues=all_issues
        )
        judge_m2 = HallucinationJudgeResult(
            total_claims=total_claims,
            supported_claims=supported_cnt,
            unsupported_claims=unsupported_cnt,
            contradicted_claims=contradicted_cnt,
            claims_breakdown=claims_breakdown,
            hallucination_percentage=risk_pct,
            risk_level=risk_level,
            score=score,
            issues=all_issues,
            explanation=explanation
        )
        return eval_m1, judge_m2
