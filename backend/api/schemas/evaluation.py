"""
Pydantic schemas for evaluation requests, responses, and validation error models.
"""
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


class EvaluationRequest(BaseModel):
    """Input payload for AI response evaluation with mandatory Reference Answer."""
    question: str = Field(
        ...,
        description="The original user question or prompt being addressed."
    )
    ai_response: str = Field(
        ...,
        description="The AI-generated response under evaluation."
    )
    reference_answer: str = Field(
        ...,
        description="The reference ground truth answer. Mandatory for evaluation."
    )
    use_knowledge_base_only: bool = Field(
        False,
        description="Retained for backward compatibility. Reference answer is strictly mandatory."
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

    @field_validator("reference_answer", mode="after")
    @classmethod
    def validate_reference_answer(cls, v: Optional[str]) -> str:
        if v is None or not str(v).strip():
            raise ValueError("Reference answer is required: Please enter the reference answer before submitting the evaluation.")
        if len(str(v).strip()) > 20000:
            raise ValueError("Reference answer is too long: Maximum allowed length is 20,000 characters.")
        return str(v).strip()


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
# Milestone 3 Completeness & Verdict Models
# ==========================================

class CompletenessJudgeResult(BaseModel):
    """Milestone 3: Structured Completeness Judge output."""
    completeness_score: float = Field(..., ge=0.0, le=100.0, description="Normalized completeness score between 0 and 100.")
    score: float = Field(..., ge=0.0, le=100.0, description="Alias for completeness_score.")
    addressed_aspects: List[str] = Field(default_factory=list, description="List of question aspects and sub-requirements adequately addressed.")
    partially_addressed_aspects: List[str] = Field(default_factory=list, description="List of aspects partially covered with notable omissions.")
    missing_aspects: List[str] = Field(default_factory=list, description="List of essential requirements or expected concepts completely omitted.")
    reasoning: str = Field(..., description="Qualitative completeness and coverage analysis.")


class VerdictJudgeResult(BaseModel):
    """Milestone 3: Structured Verdict Agent output combining all dimensions."""
    relevance_score: float = Field(..., ge=0.0, le=100.0, description="Relevance score (0-100).")
    accuracy_score: float = Field(..., ge=0.0, le=100.0, description="Accuracy score (0-100).")
    hallucination_score: float = Field(..., ge=0.0, le=100.0, description="Hallucination-free quality score (0-100).")
    completeness_score: float = Field(..., ge=0.0, le=100.0, description="Completeness score (0-100).")
    weighted_overall_score: float = Field(..., ge=0.0, le=100.0, description="Weighted composite score: 25% Rel + 30% Acc + 25% Comp + 20% Hal.")
    weighted_score: Optional[float] = Field(None, description="Alias for weighted_overall_score.")
    final_verdict: str = Field(..., description="Verdict label: PASS, NEEDS IMPROVEMENT, or FAIL.")
    major_issues: List[str] = Field(default_factory=list, description="Major issues across all evaluation dimensions.")
    consolidated_reasoning: str = Field(..., description="Consolidated multi-agent reasoning synthesis.")
    severe_hallucination_override: bool = Field(False, description="Whether severe hallucination override was triggered.")

    def model_post_init(self, __context):
        if self.weighted_score is None:
            self.weighted_score = self.weighted_overall_score


# ==========================================
# Milestone 3 Batch Evaluation Schemas
# ==========================================

class BatchItemResult(BaseModel):
    """Evaluation result for a single record within a batch."""
    row_id: int = Field(..., description="1-indexed row number in the batch.")
    row_index: Optional[int] = None
    response_id: Optional[str] = Field(None, description="Optional external identifier.")
    question: str = Field(..., description="The user question evaluated.")
    ai_response: str = Field(..., description="The AI response evaluated.")
    reference_answer: Optional[str] = Field("", description="The ground truth reference answer (optional in batch).")
    status: str = Field(..., description="Status: 'SUCCESS', 'INVALID', or 'FAILED'.")
    error_message: Optional[str] = None
    relevance_score: Optional[float] = None
    accuracy_score: Optional[float] = None
    hallucination_score: Optional[float] = None
    hallucination_percentage: Optional[float] = None
    completeness_score: Optional[float] = None
    overall_score: Optional[float] = None
    verdict: Optional[str] = None
    final_verdict: Optional[str] = None
    expected_status: Optional[str] = Field(None, description="Optional benchmark comparison label (valid/invalid).")
    record_status: Optional[str] = Field(None, description="Status in result table: 'VALID' or 'INVALID'")
    similarity_score: Optional[float] = Field(None, description="Semantic similarity percentage.")
    evaluation_detail: Optional["EvaluationResponse"] = None
    evaluation_response: Optional["EvaluationResponse"] = None

    def model_post_init(self, __context):
        if self.row_index is None:
            self.row_index = self.row_id
        if self.final_verdict is None:
            self.final_verdict = self.verdict
        if self.evaluation_response is None:
            self.evaluation_response = self.evaluation_detail
        if self.record_status is None:
            self.record_status = "VALID" if (self.verdict == "PASS" and self.status == "SUCCESS") else "INVALID"
        if self.similarity_score is None and self.evaluation_detail and getattr(self.evaluation_detail, "evaluation", None):
            sim = getattr(self.evaluation_detail.evaluation, "similarity", None)
            if sim:
                self.similarity_score = getattr(sim, "percentage", None)


class BatchSummary(BaseModel):
    """Aggregated statistics for a batch evaluation run."""
    total_records: int = Field(..., ge=0)
    total_rows: Optional[int] = None
    file_total: Optional[int] = Field(None, description="Total records in the uploaded file.")
    valid_total: Optional[int] = Field(None, description="Total valid records in the uploaded file.")
    invalid_total: Optional[int] = Field(None, description="Total invalid records in the uploaded file.")
    selected_filter: Optional[str] = Field("All", description="Filter applied to batch.")
    available_records: Optional[int] = Field(None, description="Number of records matching the filter.")
    requested_records: Optional[int] = Field(None, description="Number of records requested to evaluate.")
    actually_evaluated: Optional[int] = Field(None, description="Number of records actually evaluated.")
    successful: int = Field(..., ge=0)
    valid_rows: Optional[int] = None
    invalid: int = Field(..., ge=0)
    invalid_rows: Optional[int] = None
    failed: int = Field(..., ge=0)
    average_relevance: float = Field(0.0, ge=0.0, le=100.0)
    average_accuracy: float = Field(0.0, ge=0.0, le=100.0)
    average_hallucination: float = Field(0.0, ge=0.0, le=100.0)
    average_completeness: float = Field(0.0, ge=0.0, le=100.0)
    average_overall: float = Field(0.0, ge=0.0, le=100.0)
    average_score: Optional[float] = None
    verdict_counts: dict = Field(default_factory=dict)
    verdict_distribution: Optional[dict] = None
    hallucination_frequency: float = Field(0.0, ge=0.0, le=100.0)
    average_hallucination_percentage: Optional[float] = None
    high_hallucination_risk_count: Optional[int] = 0

    def model_post_init(self, __context):
        if self.total_rows is None:
            self.total_rows = self.total_records
        if self.file_total is None:
            self.file_total = self.total_records
        if self.available_records is None:
            self.available_records = self.total_records
        if self.requested_records is None:
            self.requested_records = self.total_records
        if self.actually_evaluated is None:
            self.actually_evaluated = self.total_records
        if self.valid_rows is None:
            self.valid_rows = self.successful
        if self.invalid_rows is None:
            self.invalid_rows = self.invalid
        if self.average_score is None:
            self.average_score = self.average_overall
        if self.verdict_distribution is None:
            self.verdict_distribution = self.verdict_counts
        if self.average_hallucination_percentage is None:
            self.average_hallucination_percentage = self.hallucination_frequency


class BatchEvaluationResponse(BaseModel):
    """Complete response for a batch evaluation request."""
    summary: BatchSummary
    results: List[BatchItemResult]


class BatchRecordValidationItem(BaseModel):
    """Validation status for a single extracted batch record (Section 33)."""
    row_id: int
    status: str = Field(..., description="Status: 'VALID' or 'INVALID'")
    reason: Optional[str] = Field(None, description="Diagnostic reason if status is INVALID")
    question: str
    ai_response: str
    reference_answer: Optional[str] = ""
    expected_status: Optional[str] = None


class BatchInputValidationSummary(BaseModel):
    """Overall pre-evaluation validation summary of uploaded batch file."""
    total_records: int
    valid_count: int
    invalid_count: int
    records: List[BatchRecordValidationItem]
    valid_records: Optional[int] = None
    invalid_records: Optional[int] = None
    validation_items: Optional[List[dict]] = None


# ==========================================
# Complete API Response
# ==========================================

class EvaluationResponse(BaseModel):
    """Complete evaluation response schema containing M1, M2, and M3 structures."""
    question: str
    original_response: str
    reference_answer: str
    better_answer: Optional[str] = None
    better_answer_reason: Optional[str] = None
    evaluation: EvaluationMetrics
    retrieved_evidence: List[RetrievedEvidenceItem] = Field(default_factory=list)
    comparison: ComparisonData
    # Milestone 2 extensions (populated by orchestrator)
    relevance_judge: Optional[RelevanceJudgeResult] = None
    accuracy_judge: Optional[AccuracyJudgeResult] = None
    hallucination_judge: Optional[HallucinationJudgeResult] = None
    case_mode: str = Field("Case 1: Reference Ground Truth", description="Case mode used for evaluation.")
    # Milestone 3 extensions (populated by orchestrator)
    completeness_judge: Optional[CompletenessJudgeResult] = None
    verdict_judge: Optional[VerdictJudgeResult] = None


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    environment: str
    vector_index_loaded: bool
    total_indexed_chunks: int
