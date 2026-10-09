"""
Tests for Batch Input Data Validation (Section 33) and Document Parsing.
Verifies:
1. Row-by-row input validation on CSV (valid vs missing question vs missing AI response).
2. Validation summary counts (total, valid, invalid).
3. POST /api/batch/validate-input endpoint returns accurate JSON structures.
4. Parsing of TXT and CSV formats.
5. Reference document parsing (TXT).
"""
import io
import unittest
from fastapi.testclient import TestClient
from backend.main import app
from backend.knowledge_base.document_parser import (
    parse_batch_input,
    validate_batch_records,
    parse_reference_document,
    retrieve_best_reference_passage
)


class TestBatchValidationAndParsing(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_csv_validation_mixed_rows(self):
        """Tests Section 33 validation logic with 5 mixed rows (3 valid, 1 missing Q, 1 missing A)."""
        csv_data = (
            "Question,AI Response\n"
            "What is machine learning?,Machine learning is a subset of artificial intelligence.\n"
            "What is Python?,Python is a high-level programming language.\n"
            ",This response has no question.\n"
            "What is RAG?,RAG combines retrieval with generative LLMs.\n"
            "What is deep learning?,\n"
        ).encode("utf-8")

        records = parse_batch_input(csv_data, "test.csv")
        self.assertEqual(len(records), 5)

        summary = validate_batch_records(records)
        self.assertEqual(summary["total_records"], 5)
        self.assertEqual(summary["valid_count"], 3)
        self.assertEqual(summary["invalid_count"], 2)

        # Row 1, 2, 4 valid
        self.assertEqual(summary["records"][0]["status"], "VALID")
        self.assertEqual(summary["records"][1]["status"], "VALID")
        self.assertEqual(summary["records"][3]["status"], "VALID")

        # Row 3 invalid (missing question)
        self.assertEqual(summary["records"][2]["status"], "INVALID")
        self.assertIn("Question is missing", summary["records"][2]["reason"])

        # Row 5 invalid (missing AI response)
        self.assertEqual(summary["records"][4]["status"], "INVALID")
        self.assertIn("AI Response is missing", summary["records"][4]["reason"])

    def test_api_batch_validate_input_endpoint(self):
        """Tests POST /api/batch/validate-input returns structured validation report."""
        csv_data = (
            "Question,AI Response\n"
            "What is Docker?,Docker is an open platform for containerizing apps.\n"
            "What is Kubernetes?,\n"
        ).encode("utf-8")

        files = {"file": ("sample.csv", io.BytesIO(csv_data), "text/csv")}
        res = self.client.post("/api/batch/validate-input", files=files)
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertEqual(data["total_records"], 2)
        self.assertEqual(data["valid_count"], 1)
        self.assertEqual(data["invalid_count"], 1)
        self.assertEqual(data["records"][0]["status"], "VALID")
        self.assertEqual(data["records"][1]["status"], "INVALID")
        self.assertIn("AI Response is missing", data["records"][1]["reason"])

    def test_txt_batch_parsing(self):
        """Tests parsing structured question-response blocks from TXT file."""
        txt_data = (
            "Question: What is photosynthesis?\n"
            "AI Response: Photosynthesis converts light to chemical energy.\n\n"
            "Question: What is cellular respiration?\n"
            "AI Response: Cellular respiration releases energy from glucose.\n"
        ).encode("utf-8")

        records = parse_batch_input(txt_data, "sample.txt")
        self.assertEqual(len(records), 2)
        self.assertIn("photosynthesis", records[0]["question"].lower())
        self.assertIn("converts light", records[0]["ai_response"].lower())

    def test_reference_document_parsing_and_retrieval(self):
        """Tests parsing TXT reference document and extracting relevant passage."""
        ref_text = (
            "Australia is an island country and continent located in the Southern Hemisphere. "
            "Its federal capital city is Canberra, which is located in the Australian Capital Territory. "
            "The largest city in Australia is Sydney, followed by Melbourne."
        ).encode("utf-8")

        parsed_text = parse_reference_document(ref_text, "geography.txt")
        self.assertIn("Canberra", parsed_text)

        best_passage = retrieve_best_reference_passage("What is the capital of Australia?", parsed_text)
        self.assertIn("Canberra", best_passage)


if __name__ == "__main__":
    unittest.main()
