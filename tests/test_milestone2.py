"""
Milestone 2 Automated Unit and Integration Tests.
Verifies:
1. Relevance Judge 1-5 scale and category mapping.
2. Accuracy Judge Case 1 (Reference Ground Truth) and Case 2 (Knowledge Base Ground Truth).
3. Hallucination Detection Agent atomic claim breakdown with Supported, Unsupported, Contradicted classifications.
4. Orchestrator dual-mode contract compliance (M1 and M2 co-existence).
"""
import unittest
from fastapi.testclient import TestClient
from backend.main import app


class TestMilestone2Extension(unittest.TestCase):
    """Verifies all Milestone 2 capabilities and backward compatibility."""

    def setUp(self):
        self.client = TestClient(app)

    def test_m2_relevance_judge_1_to_5_scale(self):
        """Test Relevance Judge returns 1-5 integer score and proper qualitative category."""
        # Case A: Fully relevant
        payload_relevant = {
            "question": "What is the capital of Australia?",
            "ai_response": "The capital of Australia is Canberra.",
            "reference_answer": "The capital of Australia is Canberra."
        }
        res = self.client.post("/api/evaluate", json=payload_relevant)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("relevance_judge", data)
        rel = data["relevance_judge"]
        self.assertIn(rel["score"], [4, 5])
        self.assertIn(rel["category"], ["Fully Relevant", "Mostly Relevant"])
        self.assertGreaterEqual(rel["score_normalized"], 70.0)
        self.assertIsNotNone(rel["reasoning"])

        # Case B: Completely irrelevant / off-topic
        payload_irrelevant = {
            "question": "What caused the French Revolution?",
            "ai_response": "To bake a chocolate cake, preheat oven to 350 degrees Fahrenheit and mix cocoa powder with flour.",
            "reference_answer": "The French Revolution was caused by severe financial crises and feudal inequality."
        }
        res_irr = self.client.post("/api/evaluate", json=payload_irrelevant)
        self.assertEqual(res_irr.status_code, 200)
        data_irr = res_irr.json()
        rel_irr = data_irr["relevance_judge"]
        self.assertIn(rel_irr["score"], [1, 2])
        self.assertIn(rel_irr["category"], ["Barely Relevant", "Irrelevant / Off-topic"])

    def test_m2_accuracy_judge_case1_reference_answer(self):
        """Test Case 1: Accuracy Judge evaluates against Reference Answer ground truth."""
        payload = {
            "question": "What is the capital of Australia?",
            "ai_response": "The capital of Australia is Canberra.",
            "reference_answer": "The capital of Australia is Canberra."
        }
        res = self.client.post("/api/evaluate", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        acc = data["accuracy_judge"]
        self.assertEqual(acc["score"], 5)
        self.assertEqual(acc["category"], "Fully Correct")
        self.assertEqual(acc["evidence_source"], "Reference Answer")
        self.assertEqual(data["case_mode"], "Case 1: Reference Ground Truth")

    def test_m2_accuracy_judge_case2_knowledge_base_only(self):
        """Test Case 2: Accuracy Judge evaluates against Knowledge Base when Reference Answer is absent."""
        payload = {
            "question": "Can the Great Wall of China be seen from space?",
            "ai_response": "The Great Wall of China cannot be seen from space or low Earth orbit with the naked eye.",
            "reference_answer": "",
            "use_knowledge_base_only": True
        }
        res = self.client.post("/api/evaluate", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        acc = data["accuracy_judge"]
        self.assertIn(acc["score"], [4, 5])
        self.assertIn(acc["category"], ["Fully Correct", "Mostly Correct"])
        self.assertEqual(acc["evidence_source"], "Knowledge Base Retrieval")
        self.assertEqual(data["case_mode"], "Case 2: Knowledge Base Ground Truth")
        self.assertGreater(len(acc["supporting_evidence"]), 0)

    def test_m2_hallucination_claim_decomposition_and_classification(self):
        """Test Hallucination Detection decomposes claims into Supported, Unsupported, and Contradicted."""
        # 1. Contradiction test (chewing gum myth)
        payload_contra = {
            "question": "What happens if you swallow chewing gum?",
            "ai_response": "Swallowed chewing gum gets stuck in your digestive tract and remains in your stomach for seven years.",
            "reference_answer": "Swallowed chewing gum passes through the digestive tract normally and does not remain in the stomach for seven years."
        }
        res_contra = self.client.post("/api/evaluate", json=payload_contra)
        self.assertEqual(res_contra.status_code, 200)
        hal_contra = res_contra.json()["hallucination_judge"]
        self.assertGreaterEqual(hal_contra["contradicted_claims"], 1)
        contra_items = [c for c in hal_contra["claims_breakdown"] if c["status"] == "Contradicted"]
        self.assertGreaterEqual(len(contra_items), 1)
        self.assertIn(hal_contra["risk_level"], ["Medium", "High"])

        # 2. Unsupported test (fabricated crystal base on Moon)
        payload_unsup = {
            "question": "What did the Apollo 11 astronauts find on the lunar surface?",
            "ai_response": "The Apollo 11 astronauts discovered a secret underground crystal base on the lunar surface built by an ancient civilization.",
            "reference_answer": "During Apollo 11, astronauts collected 47.5 pounds of lunar rock samples and deployed scientific experiments."
        }
        res_unsup = self.client.post("/api/evaluate", json=payload_unsup)
        self.assertEqual(res_unsup.status_code, 200)
        hal_unsup = res_unsup.json()["hallucination_judge"]
        self.assertGreaterEqual(hal_unsup["unsupported_claims"], 1)
        unsup_items = [c for c in hal_unsup["claims_breakdown"] if c["status"] == "Unsupported"]
        self.assertGreaterEqual(len(unsup_items), 1)

    def test_m2_dual_mode_orchestrator_schema_compatibility(self):
        """Test API response returns both Milestone 1 metrics and Milestone 2 judge payloads."""
        payload = {
            "question": "What is the capital of Australia?",
            "ai_response": "The capital of Australia is Canberra.",
            "reference_answer": "The capital of Australia is Canberra."
        }
        res = self.client.post("/api/evaluate", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()

        # Check Milestone 1 structure
        self.assertIn("evaluation", data)
        eval_data = data["evaluation"]
        self.assertIn("relevance", eval_data)
        self.assertIn("accuracy", eval_data)
        self.assertIn("hallucination", eval_data)
        self.assertIn("completeness", eval_data)
        self.assertIn("similarity", eval_data)
        self.assertIn("overall_score", eval_data)
        self.assertIn("verdict", eval_data)

        # Check Milestone 2 structure
        self.assertIn("relevance_judge", data)
        self.assertIn("accuracy_judge", data)
        self.assertIn("hallucination_judge", data)
        self.assertIn("case_mode", data)

        # Verify claim breakdown details
        claims = data["hallucination_judge"]["claims_breakdown"]
        self.assertIsInstance(claims, list)
        self.assertGreater(len(claims), 0)
        self.assertIn(claims[0]["status"], ["Supported", "Unsupported", "Contradicted"])


if __name__ == "__main__":
    unittest.main()
