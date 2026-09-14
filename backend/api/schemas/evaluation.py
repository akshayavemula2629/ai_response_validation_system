"""
Pydantic schemas for evaluation requests, responses, and validation error models.
"""
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


class EvaluationRequest(BaseModel):
    """Input payload for AI response evaluation."""
    question: str = Field(
        ...,
        description="The original user question or prompt being addressed."
    )
    ai_response: str = Field(
        ...,
        description="The AI-generated response under evaluation."
    )
    use_knowledge_base_only: bool = Field(
        False,
        description="Case 2 toggle: when True, evaluates accuracy against retrieved RAG chunks without requiring a reference answer."
    )
    reference_answer: Optional[str] = Field(
        None,
        description="The reference ground truth answer. Required unless use_knowledge_base_only is True."
    )
    source_document: Optional[str] = Field(
        None,
        description="Optional source document or reference material text."
    )

    @field_validator("question", mode="after")
    @classmethod
    def validate_question(cls, v: Optional[str]) -> str:
        if v is None or not str(v).strip():
            raise ValueError("Question is required: Please enter the question before submitting the evaluation.")
        if len(str(v).strip()) > 5000:
            raise ValueError("Question is too long: Maximum allowed length is 5,000 characters.")
        return str(v).strip()

    @field_validator("ai_response", mode="after")
    @classmethod
    def validate_ai_response(cls, v: Optional[str]) -> str:
        if v is None or not str(v).strip():
            raise ValueError("AI response is required: Please enter the AI response before submitting the evaluation.")
        if len(str(v).strip()) > 20000:
            raise ValueError("AI response is too long: Maximum allowed length is 20,000 characters.")
        return str(v).strip()

    @model_validator(mode="after")
    def validate_case_and_reference(self) -> "EvaluationRequest":
        if not self.use_knowledge_base_only:
            if self.reference_answer is None or not str(self.reference_answer).strip():
                raise ValueError("Reference answer is required: Please enter the reference answer before submitting the evaluation.")
            if len(str(self.reference_answer).strip()) > 20000:
                raise ValueError("Reference answer is too long: Maximum allowed length is 20,000 characters.")
            self.reference_answer = str(self.reference_answer).strip()
        else:
            if self.reference_answer and str(self.reference_answer).strip():
                self.reference_answer = str(self.reference_answer).strip()
            else:
                self.reference_answer = ""
        return self


class ValidationErrorResponse(BaseModel):
    """Structured validation error response for API clients."""
    error: str = Field(..., description="Short error title or category.")
    message: str = Field(..., description="Actionable user message.")


class DimensionScore(BaseModel):
    """Score and qualitative explanation for an evaluation dimension."""
    score: float = Field(..., ge=0.0, le=100.0, description="Evaluation score between 0 and 100.")
    explanation: str = Field(..., description="Detailed rationale explaining the score.")


class HallucinationEvaluation(BaseModel):
    """Evaluation result for hallucination analysis."""
    score: float = Field(..., ge=0.0, le=100.0, description="Hallucination-free score (100 = completely factual, 0 = pure hallucination).")
    percentage: float = Field(..., ge=0.0, le=100.0, description="Hallucination risk percentage (0% = no hallucination, 100% = complete hallucination).")
    risk_level: str = Field(..., description="Risk tier: Low, Medium, or High.")
    explanation: str = Field(..., description="Detailed explanation of detected claims and grounding.")
    issues: List[str] = Field(default_factory=list, description="List of detected unsupported or contradictory claims.")


class SimilarityEvaluation(BaseModel):
    """Semantic similarity between AI response and reference/evidence."""
    percentage: float = Field(..., ge=0.0, le=100.0, description="Cosine semantic similarity percentage.")
    explanation: str = Field(..., description="Explanation distinguishing semantic similarity from factual correctness.")


class EvaluationMetrics(BaseModel):
    """Nested evaluation dimensions matching Milestone 1 requirements."""
    relevance: DimensionScore
    accuracy: DimensionScore
    hallucination: HallucinationEvaluation
    completeness: DimensionScore
    similarity: SimilarityEvaluation
    overall_score: float = Field(..., ge=0.0, le=100.0, description="Weighted composite verdict score.")
    verdict: str = Field(..., description="Verdict label: Excellent, Good, Needs Improvement, or Poor.")
    summary: str = Field(..., description="Overall evaluation summary and recommendation.")


class RetrievedEvidenceItem(BaseModel):
    """Individual retrieved chunk of knowledge base evidence."""
    chunk_id: str
    content: str
    source: str
    similarity_score: float


class ComparisonData(BaseModel):
    """Structured data comparing the reference answer vs the generated better answer."""
    reference_answer_score: float = Field(100.0, description="Baseline reference answer score.")
    better_answer_score: float = Field(..., ge=0.0, le=100.0, description="Calculated score of the generated better answer.")
    similarity_percentage: float = Field(..., ge=0.0, le=100.0, description="Semantic similarity percentage between reference and better answer.")


# ==========================================
# Milestone 2 Advanced Judge Models
# ==========================================

class RelevanceJudgeResult(BaseModel):
    """Milestone 2: Structured Relevance Judge output on 1-5 scale."""
    score: int = Field(..., ge=1, le=5, description="Relevance score on a 1-5 integer scale.")
    score_normalized: float = Field(..., ge=0.0, le=100.0, description="Normalized score 0-100 for composite verdict calculations.")
    category: str = Field(..., description="Category: Fully Relevant, Mostly Relevant, Partially Relevant, Barely Relevant, or Irrelevant / Off-topic.")
    reasoning: str = Field(..., description="Qualitative reasoning supporting the relevance score.")
    explanation: str = Field(..., description="Backward-compatible alias for reasoning.")


class AccuracyJudgeResult(BaseModel):
    """Milestone 2: Structured Accuracy Judge output on 1-5 scale with Case 1 & Case 2 support."""
    score: int = Field(..., ge=1, le=5, description="Accuracy score on a 1-5 integer scale.")
    score_normalized: float = Field(..., ge=0.0, le=100.0, description="Normalized score 0-100 for composite verdict calculations.")
    category: str = Field(..., description="Category: Fully Correct, Mostly Correct, Partially Correct, Mostly Incorrect, or Incorrect / Contradictory.")
    evidence_source: str = Field(..., description="Source of truth used: 'Reference Answer' (Case 1) or 'Knowledge Base Retrieval' (Case 2).")
    supporting_evidence: List[str] = Field(default_factory=list, description="Grounding evidence snippets used for factual verification.")
    issues: List[str] = Field(default_factory=list, description="Detected factual inaccuracies, contradictions, or date/entity errors.")
    reasoning: str = Field(..., description="Qualitative factual accuracy analysis.")
    explanation: str = Field(..., description="Backward-compatible alias for reasoning.")


class ClaimVerificationItem(BaseModel):
    """Milestone 2: Atomic claim-level verification result."""
    claim: str = Field(..., description="Atomic claim or statement extracted from AI response.")
    status: str = Field(..., description="Classification: 'Supported' (✓), 'Unsupported' (⚠), or 'Contradicted' (✕).")
    evidence: Optional[str] = Field(None, description="Matched grounding evidence snippet or reference sentence.")
    explanation: str = Field(..., description="Rationale for the claim classification.")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence level of classification (0.0 to 1.0).")


class HallucinationJudgeResult(BaseModel):
    """Milestone 2: Structured Hallucination Detection output with atomic claim breakdown."""
    total_claims: int = Field(..., ge=0, description="Total number of discrete claims evaluated.")
    supported_claims: int = Field(..., ge=0, description="Number of fully verified claims.")
    unsupported_claims: int = Field(..., ge=0, description="Number of unverified/fabricated claims.")
    contradicted_claims: int = Field(..., ge=0, description="Number of directly contradicted claims.")
    claims_breakdown: List[ClaimVerificationItem] = Field(default_factory=list, description="Detailed list of atomic claim evaluations.")
    hallucination_percentage: float = Field(..., ge=0.0, le=100.0, description="Hallucination risk percentage.")
    risk_level: str = Field(..., description="Hallucination risk level: Low, Medium, or High.")
    score: float = Field(..., ge=0.0, le=100.0, description="Hallucination-free score (100.0 - percentage).")
    issues: List[str] = Field(default_factory=list, description="List of detected hallucinated or contradicted claim statements.")
    explanation: str = Field(..., description="Overall qualitative grounding assessment.")


# ==========================================
# Complete API Response
# ==========================================

class EvaluationResponse(BaseModel):
    """Complete evaluation response schema containing both M1 and M2 structures."""
    question: str
    original_response: str
    reference_answer: str
    better_answer: Optional[str] = None
    better_answer_reason: Optional[str] = None
    evaluation: EvaluationMetrics
    retrieved_evidence: List[RetrievedEvidenceItem] = Field(default_factory=list)
    comparison: ComparisonData
    # Milestone 2 extensions (optional for backward compatibility, populated by M2 orchestrator)
    relevance_judge: Optional[RelevanceJudgeResult] = None
    accuracy_judge: Optional[AccuracyJudgeResult] = None
    hallucination_judge: Optional[HallucinationJudgeResult] = None
    case_mode: str = Field("Case 1: Reference Ground Truth", description="Case mode used for evaluation.")


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    environment: str
    vector_index_loaded: bool
    total_indexed_chunks: int
