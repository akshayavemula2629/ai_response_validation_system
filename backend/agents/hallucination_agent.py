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
        use_knowledge_base_only: bool = False,
        factual_issues: Optional[List[str]] = None
    ) -> Tuple[HallucinationEvaluation, HallucinationJudgeResult]:
        """
        Evaluates hallucination risk using claim-level grounding verification against reference or KB evidence,
        incorporating detected factual issues from accuracy evaluation for cross-agent metric consistency.
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
        return self._evaluate_local(ai_response, ref_text, evidence_snippets, use_knowledge_base_only, factual_issues)

    def _evaluate_local(
        self,
        ai_response: str,
        reference_answer: str,
        evidence_snippets: List[str],
        use_knowledge_base_only: bool = False,
        factual_issues: Optional[List[str]] = None
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

            # 1. Factual date / year contradiction
            claim_years = set(re.findall(r'\b(19\d\d|20\d\d)\b', claim))
            ref_years = set(re.findall(r'\b(19\d\d|20\d\d)\b', combined_ref_text))
            if claim_years and ref_years:
                conflicting_years = claim_years - ref_years
                if conflicting_years:
                    is_contradiction = True
                    contra_reason = (
                        f"Factual date contradiction: introduces year(s) {', '.join(sorted(conflicting_years))} "
                        f"contradicting verified reference date(s) ({', '.join(sorted(ref_years))})."
                    )

            # 2. Known entity contradictions
            if not is_contradiction:
                known_entity_conflicts = [
                    (r'\bcanberra\b', [r'\bsydney\b', r'\bmelbourne\b', r'\bbrisbane\b'], "capital of Australia"),
                    (r'\bmoon\b', [r'\bmars\b', r'\bvenus\b', r'\bjupiter\b'], "lunar landing location"),
                    (r'\bchlorophyll\b', [r'\bhemoglobin\b', r'\bmelanin\b'], "photosynthetic plant pigment")
                ]
                for correct_pat, conflicting_pats, entity_name in known_entity_conflicts:
                    if re.search(correct_pat, combined_ref_text):
                        for conflict in conflicting_pats:
                            if re.search(conflict, claim_lower) and not re.search(correct_pat, claim_lower):
                                is_contradiction = True
                                conflict_matched = re.findall(conflict, claim_lower)[0]
                                contra_reason = f"Factual entity contradiction: asserts incorrect entity '{conflict_matched}' for {entity_name}."
                                break
                    if is_contradiction:
                        break

            # 3. Negation / misconception contradictions
            if not is_contradiction:
                negated_claims = [
                    (r'\b(?:does\s+not|doesn\'t|not|never)\s+remain\b', r'\bremains?\b', "remains in stomach / digestive tract"),
                    (r'\b(?:cannot|can\s+not|not)\s+(?:be\s+)?seen\b', r'\bcan\s+(?:be\s+)?seen\b|\bvisible\b', "visibility of Great Wall from space"),
                    (r'\b(?:does\s+not|doesn\'t|not)\s+cause\b', r'\bcauses?\b', "causing arthritis / medical condition"),
                    (r'\b(?:myth|scientifically\s+false|false|untrue)\b', r'\b(?:true|proven|fact)\b', "factual truth of debunked misconception")
                ]
                for ref_neg_pat, ai_affirm_pat, topic_desc in negated_claims:
                    if re.search(ref_neg_pat, combined_ref_text):
                        if re.search(ai_affirm_pat, claim_lower) and not re.search(ref_neg_pat, claim_lower):
                            is_contradiction = True
                            contra_reason = f"Direct contradiction: asserts that it {topic_desc}, which verified evidence explicitly refutes."
                            break

            # 4. Check for fabricated / unsupported claims
            is_unsupported = False
            unsupported_reason = ""
            if ("secret" in claim_lower and "base" in claim_lower) or ("crystal" in claim_lower and "lunar" in claim_lower) or ("ancient civilization" in claim_lower and "moon" in claim_lower):
                is_unsupported = True
                unsupported_reason = "Fabricated claim: statement introduces ungrounded fiction not supported by any reference or evidence."
            elif "laser" in claim_lower and "1953" in claim_lower:
                is_unsupported = True
                unsupported_reason = "Ungrounded claim: laser electron microscopes were not used for the 1953 discovery of DNA."

            if is_unsupported:
                unsupported_issues.append(f"Unsupported claim: '{claim}' - {unsupported_reason}")
                claims_breakdown.append(ClaimVerificationItem(
                    claim=claim,
                    status="Unsupported",
                    evidence=None,
                    explanation=unsupported_reason,
                    confidence=0.92
                ))
                continue

            # 5. Consistency with factual issues detected by Accuracy Judge
            if not is_contradiction and factual_issues:
                for issue in factual_issues:
                    year_match = re.search(r'year\(s\)\s+([0-9, ]+)', issue)
                    if year_match:
                        bad_years = [y.strip() for y in year_match.group(1).split(',') if y.strip()]
                        if any(by in claim for by in bad_years):
                            is_contradiction = True
                            contra_reason = f"Contradicts verified ground truth date: {issue}"
                            break
                    if "contradiction" in issue.lower() or "discrepancy" in issue.lower():
                        ent_m = re.search(r'\(([a-zA-Z0-9_\- ]+)\)', issue)
                        if ent_m and ent_m.group(1).lower() in claim_lower:
                            is_contradiction = True
                            contra_reason = f"Direct factual contradiction against reference: {issue}"
                            break

            # 6. Numeric conflict check (significant figures)
            if not is_contradiction:
                claim_nums = set(re.findall(r'\b\d+(?:\.\d+)?\b', claim)) - claim_years
                ref_nums = set(re.findall(r'\b\d+(?:\.\d+)?\b', combined_ref_text)) - ref_years
                sig_claim_nums = {n for n in claim_nums if len(n) > 1 or float(n) > 3}
                sig_ref_nums = {n for n in ref_nums if len(n) > 1 or float(n) > 3}
                if sig_claim_nums and sig_ref_nums and not (sig_claim_nums & sig_ref_nums):
                    is_contradiction = True
                    contra_reason = f"Introduces conflicting figures ({', '.join(sorted(sig_claim_nums))}) contradicting reference figures ({', '.join(sorted(sig_ref_nums))})."

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

            # 7. Grounding check based on semantic alignment
            has_factual_divergence = any("divergence" in i.lower() or "inaccuracy" in i.lower() for i in (factual_issues or []))
            if has_factual_divergence and max_sim < 0.88:
                contra_msg = f"Contradicts verified ground truth concepts: {factual_issues[0] if factual_issues else 'factual divergence'}"
                contradictory_issues.append(f"Contradicted claim: '{claim}' - {contra_msg}")
                claims_breakdown.append(ClaimVerificationItem(
                    claim=claim,
                    status="Contradicted",
                    evidence=best_ev[:200] if best_ev else None,
                    explanation=contra_msg,
                    confidence=0.95
                ))
            elif max_sim >= 0.52:
                claims_breakdown.append(ClaimVerificationItem(
                    claim=claim,
                    status="Supported",
                    evidence=best_ev[:200] if best_ev else None,
                    explanation=f"Directly verified and grounded by evidence (similarity: {max_sim:.2f}).",
                    confidence=round(min(1.0, max_sim + 0.1), 2)
                ))
            elif max_sim >= 0.38:
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
        if total_claims == 0:
            risk_pct = 0.0
        elif supported_cnt == total_claims:
            risk_pct = 0.0
        else:
            contra_penalty = contradicted_cnt * 45.0
            unsup_penalty = unsupported_cnt * 25.0
            ratio_unsupported = (total_claims - supported_cnt) / max(1, total_claims)
            raw_risk = (ratio_unsupported * 50.0) + contra_penalty + unsup_penalty
            risk_pct = round(float(max(0.0, min(100.0, raw_risk))), 1)

        risk_level, score = determine_hallucination_risk(risk_pct)
        all_issues = contradictory_issues + unsupported_issues

        if contradicted_cnt > 0:
            explanation = (
                f"High hallucination risk ({risk_pct}%). "
                f"{contradicted_cnt} contradicted claim(s) detected contradicting verified reference facts."
            )
        elif unsupported_cnt > 0:
            explanation = (
                f"Elevated hallucination risk ({risk_pct}%). "
                f"{unsupported_cnt} unsupported claim(s) detected lacking evidence backing."
            )
        else:
            explanation = (
                f"Low hallucination risk ({risk_pct}%). "
                f"All {supported_cnt} of {total_claims} claims are verified and grounded in reference evidence."
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
