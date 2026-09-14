"""
Automated tests for input validation (Tests 2, 3, 4, empty inputs, whitespace, malformed payloads).
"""
import unittest
from fastapi.testclient import TestClient
from backend.main import app


class TestInputValidation(unittest.TestCase):
    """Verifies that evaluation requests validate required fields according to specifications."""

    def setUp(self):
        self.client = TestClient(app)

    def test_missing_question(self):
        """Test 2: Question missing returns validation error saying 'Please enter the question.'"""
        payload = {
            "ai_response": "The capital is Canberra.",
            "reference_answer": "Canberra is the capital of Australia."
        }
        res = self.client.post("/api/evaluate", json=payload)
        self.assertEqual(res.status_code, 422)
        data = res.json()
        self.assertIn("error", data)
        self.assertIn("message", data)
        self.assertEqual(data["error"], "Question is required")
        self.assertIn("Please enter the question", data["message"])

    def test_empty_question_string(self):
        """Test question provided as empty string or whitespace."""
        payload = {
            "question": "   ",
            "ai_response": "Some response",
            "reference_answer": "Some reference"
        }
        res = self.client.post("/api/evaluate", json=payload)
        self.assertEqual(res.status_code, 422)
        data = res.json()
        self.assertIn("Please enter the question", data["message"])

    def test_missing_reference_answer(self):
        """Test 3: Reference answer missing returns validation error saying 'Please enter the reference answer.'"""
        payload = {
            "question": "What is the capital of Australia?",
            "ai_response": "The capital is Canberra."
        }
        res = self.client.post("/api/evaluate", json=payload)
        self.assertEqual(res.status_code, 422)
        data = res.json()
        self.assertIn("error", data)
        self.assertIn("message", data)
        self.assertEqual(data["error"], "Reference answer is required")
        self.assertIn("Please enter the reference answer", data["message"])

    def test_empty_reference_answer_string(self):
        """Test reference answer provided as whitespace."""
        payload = {
            "question": "What is the capital of Australia?",
            "ai_response": "The capital is Canberra.",
            "reference_answer": "\n  \t "
        }
        res = self.client.post("/api/evaluate", json=payload)
        self.assertEqual(res.status_code, 422)
        data = res.json()
        self.assertIn("Please enter the reference answer", data["message"])

    def test_missing_ai_response(self):
        """Test 4: AI response missing returns validation error."""
        payload = {
            "question": "What is the capital of Australia?",
            "reference_answer": "Canberra is the capital of Australia."
        }
        res = self.client.post("/api/evaluate", json=payload)
        self.assertEqual(res.status_code, 422)
        data = res.json()
        self.assertIn("error", data)
        self.assertIn("message", data)
        self.assertEqual(data["error"], "AI response is required")
        self.assertIn("Please enter the AI response", data["message"])

    def test_empty_ai_response_string(self):
        """Test AI response provided as empty string."""
        payload = {
            "question": "What is the capital of Australia?",
            "ai_response": "",
            "reference_answer": "Canberra is the capital of Australia."
        }
        res = self.client.post("/api/evaluate", json=payload)
        self.assertEqual(res.status_code, 422)
        data = res.json()
        self.assertIn("Please enter the AI response", data["message"])


if __name__ == "__main__":
    unittest.main()
