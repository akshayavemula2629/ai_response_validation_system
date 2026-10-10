"""
Automated tests for comprehensive evaluation pipeline:
- Test 1: Valid question + AI response + reference answer.
- Test 6: AI answer containing obvious hallucinated information.
- Test 7: AI answer that is partially correct.
- Test 8: AI answer that is incomplete.
- Test 10: Better-answer generation.
- Test 11: Final verdict generation.
"""
import unittest
from fastapi.testclient import TestClient
from backend.main import app


class TestEvaluationPipeline(unittest.TestCase):
    """End-to-end evaluation pipeline verification."""

    def setUp(self):
        self.client = TestClient(app)

    def test_test1_valid_evaluation(self):
        """Test 1: Valid question + AI response + reference answer."""
        payload = {
            "question": "What is the capital of Australia?",
            "ai_response": "The capital of Australia is Canberra.",
            "reference_answer": "The capital of Australia is Canberra."
        }
        res = self.client.post("/api/evaluate", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()

        # Check top-level fields
        self.assertEqual(data["question"], payload["question"])
        self.assertEqual(data["original_response"], payload["ai_response"])
        self.assertEqual(data["reference_answer"], payload["reference_answer"])

        # Check evaluation dimensions
        eval_data = data["evaluation"]
        self.assertGreaterEqual(eval_data["relevance"]["score"], 80.0)
        self.assertGreaterEqual(eval_data["accuracy"]["score"], 85.0)
        self.assertLessEqual(eval_data["hallucination"]["percentage"], 20.0)
        self.assertEqual(eval_data["hallucination"]["risk_level"], "Low")
        self.assertGreaterEqual(eval_data["completeness"]["score"], 80.0)
        self.assertGreaterEqual(eval_data["overall_score"], 85.0)
        self.assertEqual(eval_data["verdict"], "Excellent")

        # Check comparison structure
        comp = data["comparison"]
        self.assertEqual(comp["reference_answer_score"], 100.0)
        self.assertGreaterEqual(comp["better_answer_score"], 85.0)
        self.assertGreaterEqual(comp["similarity_percentage"], 80.0)

    def test_test6_obvious_hallucination(self):
        """Test 6: AI answer containing obvious hallucinated information."""
        payload = {
            "question": "What happens if you swallow chewing gum?",
            "ai_response": "Swallowed chewing gum gets stuck in your digestive tract and remains in your stomach for seven years, requiring surgical extraction in 1985.",
            "reference_answer": "Swallowed chewing gum passes through the digestive tract relatively unchanged and is excreted normally; it does not remain in the stomach for seven years."
        }
        res = self.client.post("/api/evaluate", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()

        hallucination = data["evaluation"]["hallucination"]
        # Must detect hallucination risk > 50% or High risk level
        self.assertGreaterEqual(hallucination["percentage"], 40.0)
        self.assertIn(hallucination["risk_level"], ["Medium", "High"])
        self.assertGreater(len(hallucination["issues"]), 0)

        # Accuracy should also be severely downgraded
        self.assertLess(data["evaluation"]["accuracy"]["score"], 70.0)

        # Better answer must be generated to replace hallucinated content
        self.assertIsNotNone(data["better_answer"])
        self.assertIn("removes unsupported", data["better_answer_reason"].lower())

    def test_test7_partially_correct(self):
        """Test 7: AI answer that is partially correct."""
        payload = {
            "question": "Who was the first person to walk on the Moon and when?",
            "ai_response": "Neil Armstrong was the first person to walk on the Moon, landing there in 1979.",
            "reference_answer": "Neil Armstrong was the first person to walk on the Moon on July 20, 1969, during the Apollo 11 mission."
        }
        res = self.client.post("/api/evaluate", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()

        accuracy = data["evaluation"]["accuracy"]
        # Partial correctness should result in intermediate score and flagged issue
        self.assertLess(accuracy["score"], 85.0)
        self.assertGreater(len(data["evaluation"]["hallucination"]["issues"]), 0)
        self.assertIn(data["evaluation"]["verdict"], ["Good", "Needs Improvement", "Poor"])

    def test_test8_incomplete_answer(self):
        """Test 8: AI answer that is incomplete."""
        payload = {
            "question": "What is photosynthesis and where does it occur in plants?",
            "ai_response": "Photosynthesis produces chemical energy.",
            "reference_answer": "Photosynthesis is a biological process used by plants to convert light energy into chemical energy. In plants and algae, photosynthesis takes place in chloroplasts using the pigment chlorophyll."
        }
        res = self.client.post("/api/evaluate", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()

        completeness = data["evaluation"]["completeness"]
        self.assertLess(completeness["score"], 75.0)
        self.assertTrue("omit" in completeness["explanation"].lower())

    def test_test10_better_answer_generation(self):
        """Test 10: Better-answer generation and comparison data."""
        payload = {
            "question": "What is the capital of Australia?",
            "ai_response": "The capital of Australia is Sydney.",
            "reference_answer": "The capital of Australia is Canberra."
        }
        res = self.client.post("/api/evaluate", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()

        # Better answer should correct Sydney -> Canberra
        better_answer = data["better_answer"]
        self.assertIn("Canberra", better_answer)
        self.assertNotIn("Sydney", better_answer)

        # Comparison metrics should exist
        comp = data["comparison"]
        self.assertEqual(comp["reference_answer_score"], 100.0)
        self.assertGreaterEqual(comp["better_answer_score"], 85.0)
        self.assertGreaterEqual(comp["similarity_percentage"], 50.0)

    def test_test11_verdict_generation_and_thresholds(self):
        """Test 11: Final verdict generation and threshold labeling."""
        from backend.evaluation.scoring import determine_verdict_label, compute_overall_score

        # Test threshold boundaries
        self.assertEqual(determine_verdict_label(95.0), "Excellent")
        self.assertEqual(determine_verdict_label(85.0), "Excellent")
        self.assertEqual(determine_verdict_label(75.0), "Good")
        self.assertEqual(determine_verdict_label(70.0), "Good")
        self.assertEqual(determine_verdict_label(60.0), "Needs Improvement")
        self.assertEqual(determine_verdict_label(50.0), "Needs Improvement")
        self.assertEqual(determine_verdict_label(45.0), "Poor")
        self.assertEqual(determine_verdict_label(15.0), "Poor")

        # Test composite score calculation
        score = compute_overall_score(
            relevance_score=100.0,
            accuracy_score=100.0,
            hallucination_free_score=100.0,
            completeness_score=100.0
        )
        self.assertEqual(score, 100.0)


if __name__ == "__main__":
    unittest.main()
