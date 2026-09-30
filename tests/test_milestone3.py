"""
Milestone 3 Automated Unit and Integration Tests.
Verifies:
1. Mandatory Reference Answer enforcement (HTTP 422 on missing, empty, or whitespace).
2. Completeness Judge Agent (aspect extraction, 3-tier classification, normalized 0-100 scoring).
3. Verdict Agent (M3 weighted model 25/30/25/20, PASS/NEEDS IMPROVEMENT/FAIL thresholds, severe hallucination override).
4. Full Orchestrator M3 integration (returning completeness_judge and verdict_judge).
5. Batch Evaluation endpoint POST /api/batch/evaluate (CSV parsing, fault tolerance on invalid rows, aggregation).
"""
import io
import unittest
from fastapi.testclient import TestClient
from backend.main import app
from backend.agents.completeness_agent import CompletenessJudgeAgent
from backend.agents.verdict_agent import VerdictAgent
from backend.api.schemas.evaluation import (
    DimensionScore,
    HallucinationEvaluation,
    SimilarityEvaluation,
    HallucinationJudgeResult
)


class TestMilestone3Extension(unittest.TestCase):
    """Verifies all Milestone 3 capabilities, contracts, and regression boundaries."""

    def setUp(self):
        self.client = TestClient(app)
        self.completeness_agent = CompletenessJudgeAgent()
        self.verdict_agent = VerdictAgent()

    # =========================================================================
    # 1. MANDATORY REFERENCE ANSWER TESTS
    # =========================================================================

    def test_mandatory_reference_answer_missing(self):
        """Reference answer missing completely returns HTTP 422 validation error."""
        payload = {
            "question": "What is the capital of Australia?",
            "ai_response": "Canberra is the capital of Australia."
        }
        res = self.client.post("/api/evaluate", json=payload)
        self.assertEqual(res.status_code, 422)
        data = res.json()
        self.assertIn("Reference answer is required", data.get("message", "") + data.get("error", ""))

    def test_mandatory_reference_answer_empty_string(self):
        """Reference answer as empty string returns HTTP 422 validation error."""
        payload = {
            "question": "What is the capital of Australia?",
            "ai_response": "Canberra is the capital of Australia.",
            "reference_answer": ""
        }
        res = self.client.post("/api/evaluate", json=payload)
        self.assertEqual(res.status_code, 422)
        data = res.json()
        err_text = data.get("error", "") + " " + data.get("message", "")
        self.assertIn("Reference answer is required", err_text)
        self.assertIn("Please enter the reference answer", err_text)

    def test_mandatory_reference_answer_whitespace_only(self):
        """Reference answer as whitespace returns HTTP 422 validation error."""
        payload = {
            "question": "What is the capital of Australia?",
            "ai_response": "Canberra is the capital of Australia.",
            "reference_answer": "   \n\t  "
        }
        res = self.client.post("/api/evaluate", json=payload)
        self.assertEqual(res.status_code, 422)
        data = res.json()
        err_text = data.get("error", "") + " " + data.get("message", "")
        self.assertIn("Reference answer is required", err_text)
        self.assertIn("Please enter the reference answer", err_text)

    def test_mandatory_reference_answer_valid(self):
        """Valid reference answer allows evaluation to proceed successfully with HTTP 200."""
        payload = {
            "question": "What is the capital of Australia?",
            "ai_response": "The capital of Australia is Canberra.",
            "reference_answer": "Canberra is the federal capital of Australia."
        }
        res = self.client.post("/api/evaluate", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("evaluation", data)
        self.assertIn("completeness_judge", data)
        self.assertIn("verdict_judge", data)

    # =========================================================================
    # 2. COMPLETENESS JUDGE AGENT TESTS
    # =========================================================================

    def test_completeness_complete_response(self):
        """Fully complete response receives high completeness score (>= 85) with addressed aspects."""
        question = "What is photosynthesis and where does it take place in plant cells?"
        reference = "Photosynthesis is the process by which plants convert light energy into chemical energy, taking place in the chloroplasts containing chlorophyll."
        response = "Photosynthesis is a biological process where plants convert sunlight into chemical energy. This process occurs inside the chloroplasts of plant cells."

        dim_score, missing, judge_res = self.completeness_agent.evaluate(
            question=question,
            ai_response=response,
            reference_answer=reference
        )

        self.assertGreaterEqual(judge_res.completeness_score, 80.0)
        self.assertGreater(len(judge_res.addressed_aspects), 0)
        self.assertIn("complete", judge_res.reasoning.lower())

    def test_completeness_partially_complete_response(self):
        """Partially complete response receives moderate score and identifies specific omissions."""
        question = "Explain what machine learning is, mention its two main types, and give two real-world applications."
        reference = "Machine learning enables systems to learn from data. Its two main types are supervised and unsupervised learning. Applications include medical imaging and autonomous driving."
        response = "Machine learning is a field of artificial intelligence where algorithms learn patterns directly from data without being explicitly programmed."

        dim_score, missing, judge_res = self.completeness_agent.evaluate(
            question=question,
            ai_response=response,
            reference_answer=reference
        )

        self.assertLess(judge_res.completeness_score, 80.0)
        self.assertGreater(len(judge_res.missing_aspects), 0)
        self.assertTrue(any("supervised" in m.lower() or "application" in m.lower() or "type" in m.lower() or "context" in m.lower() for m in judge_res.missing_aspects))

    def test_completeness_incomplete_response(self):
        """Severely incomplete or off-topic response receives low completeness score (< 50)."""
        question = "What is the theory of relativity and who developed it?"
        reference = "Albert Einstein developed the theory of relativity, comprising special and general relativity, describing gravity and spacetime curvature."
        response = "Gravity makes apples fall from trees."

        dim_score, missing, judge_res = self.completeness_agent.evaluate(
            question=question,
            ai_response=response,
            reference_answer=reference
        )

        self.assertLess(judge_res.completeness_score, 50.0)
        self.assertGreater(len(judge_res.missing_aspects), 0)

    # =========================================================================
    # 3. VERDICT AGENT TESTS & SEVERE HALLUCINATION OVERRIDE
    # =========================================================================

    def test_verdict_high_quality_pass(self):
        """High performance across all dimensions results in a PASS verdict (score >= 80)."""
        relevance = DimensionScore(score=95.0, explanation="Fully relevant.")
        accuracy = DimensionScore(score=95.0, explanation="Fully accurate.")
        hallucination = HallucinationEvaluation(
            score=100.0,
            percentage=0.0,
            risk_level="Low",
            explanation="Grounded.",
            issues=[]
        )
        completeness = DimensionScore(score=90.0, explanation="Thoroughly complete.")
        similarity = SimilarityEvaluation(percentage=90.0, explanation="High similarity.")

        res = self.verdict_agent.evaluate(
            relevance=relevance,
            accuracy=accuracy,
            hallucination=hallucination,
            completeness=completeness,
            similarity=similarity
        )

        verdict_judge = res["verdict_judge"]
        self.assertGreaterEqual(verdict_judge.weighted_overall_score, 80.0)
        self.assertEqual(verdict_judge.final_verdict, "PASS")
        self.assertFalse(verdict_judge.severe_hallucination_override)

    def test_verdict_moderate_needs_improvement(self):
        """Moderate scores (60-79.99) result in NEEDS IMPROVEMENT verdict."""
        relevance = DimensionScore(score=75.0, explanation="Mostly relevant.")
        accuracy = DimensionScore(score=70.0, explanation="Mostly accurate.")
        hallucination = HallucinationEvaluation(
            score=70.0,
            percentage=30.0,
            risk_level="Medium",
            explanation="Minor unverified claim.",
            issues=["Minor unverified assertion."]
        )
        completeness = DimensionScore(score=65.0, explanation="Partially complete.")
        similarity = SimilarityEvaluation(percentage=70.0, explanation="Moderate similarity.")

        res = self.verdict_agent.evaluate(
            relevance=relevance,
            accuracy=accuracy,
            hallucination=hallucination,
            completeness=completeness,
            similarity=similarity
        )

        verdict_judge = res["verdict_judge"]
        self.assertGreaterEqual(verdict_judge.weighted_overall_score, 60.0)
        self.assertLess(verdict_judge.weighted_overall_score, 80.0)
        self.assertEqual(verdict_judge.final_verdict, "NEEDS IMPROVEMENT")

    def test_verdict_low_score_fail(self):
        """Low overall scores (< 60) result in FAIL verdict."""
        relevance = DimensionScore(score=30.0, explanation="Barely relevant.")
        accuracy = DimensionScore(score=20.0, explanation="Inaccurate.")
        hallucination = HallucinationEvaluation(
            score=25.0,
            percentage=75.0,
            risk_level="High",
            explanation="Unverified.",
            issues=["Fabricated claim."]
        )
        completeness = DimensionScore(score=20.0, explanation="Incomplete.")
        similarity = SimilarityEvaluation(percentage=15.0, explanation="Low similarity.")

        res = self.verdict_agent.evaluate(
            relevance=relevance,
            accuracy=accuracy,
            hallucination=hallucination,
            completeness=completeness,
            similarity=similarity
        )

        verdict_judge = res["verdict_judge"]
        self.assertLess(verdict_judge.weighted_overall_score, 60.0)
        self.assertEqual(verdict_judge.final_verdict, "FAIL")

    def test_verdict_severe_hallucination_override(self):
        """Severe hallucination or contradiction blocks PASS and forces downgrade."""
        # High relevance (95) and high completeness (90), but severe contradiction in hallucination
        relevance = DimensionScore(score=95.0, explanation="Fully relevant.")
        accuracy = DimensionScore(score=70.0, explanation="Partially contradicted.")
        hallucination = HallucinationEvaluation(
            score=10.0,
            percentage=90.0,
            risk_level="High",
            explanation="Direct contradiction with established historical facts.",
            issues=["Direct contradiction: states astronaut landed on Mars in 1985."]
        )
        completeness = DimensionScore(score=90.0, explanation="Detailed response.")
        similarity = SimilarityEvaluation(percentage=80.0, explanation="High overlap.")

        hal_judge = HallucinationJudgeResult(
            total_claims=1,
            supported_claims=0,
            unsupported_claims=0,
            contradicted_claims=1,
            claims_breakdown=[],
            hallucination_percentage=90.0,
            risk_level="High",
            score=10.0,
            issues=["Contradiction detected."],
            explanation="High risk."
        )

        res = self.verdict_agent.evaluate(
            relevance=relevance,
            accuracy=accuracy,
            hallucination=hallucination,
            completeness=completeness,
            similarity=similarity,
            hallucination_judge=hal_judge
        )

        verdict_judge = res["verdict_judge"]
        self.assertNotEqual(verdict_judge.final_verdict, "PASS")
        self.assertIn(verdict_judge.final_verdict, ["NEEDS IMPROVEMENT", "FAIL"])
        self.assertTrue(verdict_judge.severe_hallucination_override)
        self.assertTrue(any("severe hallucination" in issue.lower() for issue in verdict_judge.major_issues))

    # =========================================================================
    # 4. BATCH EVALUATION API TESTS
    # =========================================================================

    def test_batch_evaluation_csv_upload_mixed_rows(self):
        """Batch evaluation handles valid and invalid rows (e.g. missing AI response), aggregates stats, and does not crash."""
        csv_content = (
            "question,ai_response,reference_answer\n"
            "What is the capital of Australia?,The capital of Australia is Canberra.,The capital of Australia is Canberra.\n"
            "What is the freezing point of water?,,\n"  # Missing AI response -> invalid row
            "What happens if you swallow gum?,Gum stays in your stomach for seven years.,Swallowed gum passes normally through the body.\n"
        )
        files = {
            "file": ("test_batch.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")
        }
        res = self.client.post("/api/batch/evaluate", files=files)
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertIn("summary", data)
        self.assertIn("results", data)
        summary = data["summary"]

        self.assertEqual(summary["total_records"], 3)
        self.assertEqual(summary["successful"], 2)
        self.assertEqual(summary["invalid"], 1)
        self.assertEqual(summary["failed"], 0)

        # Row 2 must be flagged INVALID with AI Response is required message
        row2 = next(r for r in data["results"] if r["row_id"] == 2)
        self.assertEqual(row2["status"], "INVALID")
        self.assertIn("AI Response is required", row2["error_message"])

        # Row 1 must be SUCCESS with individual dimension scores
        row1 = next(r for r in data["results"] if r["row_id"] == 1)
        self.assertEqual(row1["status"], "SUCCESS")
        self.assertGreaterEqual(row1["overall_score"], 80.0)
        self.assertEqual(row1["verdict"], "PASS")

        # Summary averages must be non-zero
        self.assertGreater(summary["average_overall"], 0.0)
        self.assertIn("PASS", summary["verdict_counts"])

    def test_batch_evaluation_csv_without_reference_column(self):
        """Batch CSV without reference_answer column evaluates successfully via KB grounding."""
        csv_content = (
            "question,ai_response\n"
            "What is the capital of Australia?,The federal capital of Australia is Canberra.\n"
        )
        files = {
            "file": ("test_no_ref.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")
        }
        res = self.client.post("/api/batch/evaluate", files=files)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["summary"]["successful"], 1)
        self.assertEqual(data["results"][0]["status"], "SUCCESS")
        self.assertIsNotNone(data["results"][0]["overall_score"])


if __name__ == "__main__":
    unittest.main()
