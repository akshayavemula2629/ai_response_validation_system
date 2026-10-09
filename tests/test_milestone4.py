"""
Milestone 4 Comprehensive Automated Test Suite.
Verifies:
1. Single Evaluation E2E pipeline and Diagnostic PDF Report generation.
2. Batch Evaluation E2E pipeline, M4 KPI metrics, batch storage, and Executive PDF Report generation.
3. Batch History and Multi-Batch Trend retrieval.
4. Multi-agent evaluation consistency and arbitration thresholds.
5. Strict scoring boundaries [0.0, 100.0] and weighted formula adherence.
6. Semantic retrieval from knowledge base.
7. Dashboard analytics aggregation API.
8. Live End-to-End Automated Testing Runner API (/api/testing/run).
9. Latency benchmarks.
"""
import io
import time
import unittest
from fastapi.testclient import TestClient
from backend.main import app
from backend.services.batch_storage import BatchStorageService, compute_batch_analytics
from backend.services.pdf_report_service import generate_single_pdf_report, generate_batch_pdf_report
from backend.agents.orchestrator import get_orchestrator
from backend.api.schemas.evaluation import EvaluationRequest


class TestMilestone4Comprehensive(unittest.TestCase):
    """Milestone 4 End-to-End and System Validation Suite."""

    def setUp(self):
        self.client = TestClient(app)
        self.orchestrator = get_orchestrator()

    # =========================================================================
    # 1. SINGLE EVALUATION E2E & PDF EXPORT TESTS
    # =========================================================================

    def test_single_evaluation_e2e(self):
        """Verifies end-to-end single response evaluation across all agents."""
        payload = {
            "question": "What is the capital of France?",
            "ai_response": "Paris is the capital of France.",
            "reference_answer": "Paris is the capital and most populous city of France."
        }
        res = self.client.post("/api/evaluate", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()

        # Core structure checks
        self.assertIn("evaluation", data)
        self.assertIn("overall_score", data["evaluation"])
        self.assertIn("verdict", data["evaluation"])
        self.assertIn("relevance", data["evaluation"])
        self.assertIn("accuracy", data["evaluation"])
        self.assertIn("completeness", data["evaluation"])
        self.assertIn("hallucination", data["evaluation"])

        # Milestone 3/4 Agent results
        self.assertIn("verdict_judge", data)
        self.assertIn("completeness_judge", data)
        self.assertEqual(data["verdict_judge"]["final_verdict"], "PASS")
        self.assertGreaterEqual(data["evaluation"]["overall_score"], 80.0)

    def test_single_pdf_report_export(self):
        """Verifies publication-grade Single Evaluation PDF Report generation via API."""
        eval_payload = {
            "request_id": "REQ-M4-TEST-SINGLE",
            "timestamp": "2026-10-05T12:00:00Z",
            "question": "What is photosynthesis?",
            "ai_response": "Photosynthesis is the process by which green plants use sunlight to synthesize nutrients from carbon dioxide and water.",
            "reference_ground_truth": "Photosynthesis is the biological process converting light energy into chemical energy in plants.",
            "overall_score": 94.0,
            "relevance_result": {
                "score": 96.0,
                "semantic_similarity": 0.95,
                "reasoning": "Direct and comprehensive response to the question."
            },
            "accuracy_result": {
                "score": 95.0,
                "factual_correctness": 0.95,
                "reasoning": "Fully accurate scientific explanation."
            },
            "hallucination_result": {
                "hallucination_score": 0.0,
                "is_hallucination": False,
                "risk_level": "LOW",
                "unsupported_claims": []
            },
            "completeness_result": {
                "score": 92.0,
                "completeness_ratio": 0.92,
                "missing_elements": []
            },
            "verdict_result": {
                "final_verdict": "PASS",
                "verdict_confidence": 0.98,
                "reasoning": "Exceptional quality across all dimensions."
            },
            "retrieved_evidence": [
                {
                    "title": "Plant Biology Benchmark",
                    "snippet": "Photosynthesis converts solar light into stored chemical sugars.",
                    "similarity": 0.91
                }
            ],
            "better_answer": "Photosynthesis is the process by which autotrophs convert light energy into chemical sugars.",
            "better_answer_reason": "Ground truth baseline alignment."
        }
        res = self.client.post("/api/single/report/pdf", json=eval_payload)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers.get("content-type"), "application/pdf")
        self.assertTrue(res.content.startswith(b"%PDF"))
        self.assertGreater(len(res.content), 2000)

    def test_single_pdf_report_validation_errors(self):
        """Verifies that invalid payloads are rejected by the PDF export route."""
        res = self.client.post("/api/single/report/pdf", json={})
        self.assertEqual(res.status_code, 400)

    # =========================================================================
    # 2. BATCH EVALUATION E2E & BATCH PDF EXPORT TESTS
    # =========================================================================

    def test_batch_evaluation_e2e_and_storage(self):
        """Verifies end-to-end batch processing, selective limits, and persistent storage."""
        csv_content = (
            "question,ai_response,reference_answer\n"
            "What is the capital of Germany?,Berlin is the capital of Germany.,Berlin is the capital of Germany.\n"
            "What is the chemical formula for water?,Water is H2O.,Water is H2O.\n"
            "Who walked on the Moon first?,Neil Armstrong was the first person to walk on the Moon.,Neil Armstrong in 1969.\n"
        )
        file_obj = io.BytesIO(csv_content.encode("utf-8"))

        res = self.client.post(
            "/api/batch/evaluate",
            files={"file": ("test_batch_m4.csv", file_obj, "text/csv")},
            data={"filter_status": "all", "row_limit": "3"}
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()

        # Check Summary
        summary = data.get("summary", {})
        self.assertEqual(summary.get("total_records"), 3)
        self.assertEqual(summary.get("actually_evaluated"), 3)
        self.assertIn("batch_id", summary)
        self.assertIn("pass_rate", summary)
        self.assertIn("fail_rate", summary)
        self.assertIn("needs_improvement_rate", summary)
        self.assertIn("dimension_averages", summary)
        self.assertIn("score_distributions", summary)
        self.assertIn("hallucination_stats", summary)
        self.assertIn("completeness_stats", summary)

        # Check Results list
        results = data.get("results", [])
        self.assertEqual(len(results), 3)
        for r in results:
            self.assertIn("overall_score", r)
            self.assertIn("final_verdict", r)
            self.assertGreaterEqual(r["overall_score"], 0.0)
            self.assertLessEqual(r["overall_score"], 100.0)

    def test_batch_history_and_details_api(self):
        """Verifies retrieving past batch runs and multi-batch trend data."""
        res = self.client.get("/api/batch/history")
        self.assertEqual(res.status_code, 200)
        history_data = res.json()
        self.assertIn("batches", history_data)
        self.assertIn("trends", history_data)

        batches = history_data["batches"]
        if batches:
            latest_batch_id = batches[0]["batch_id"]
            detail_res = self.client.get(f"/api/batch/{latest_batch_id}")
            self.assertEqual(detail_res.status_code, 200)
            detail_data = detail_res.json()
            self.assertIn("summary", detail_data)
            self.assertIn("results", detail_data)

    def test_batch_details_not_found(self):
        """Verifies HTTP 404 on requesting a non-existent batch run ID."""
        res = self.client.get("/api/batch/NON_EXISTENT_BATCH_ID_99999")
        self.assertEqual(res.status_code, 404)

    def test_batch_pdf_report_export(self):
        """Verifies publication-grade Batch Evaluation Executive PDF Report generation."""
        sample_results = [
            {
                "row_id": 1,
                "response_id": "RESP-1",
                "question": "What is the speed of light?",
                "ai_response": "The speed of light in vacuum is approximately 299,792,458 meters per second.",
                "reference_answer": "Light travels at 299,792,458 m/s in vacuum.",
                "overall_score": 96.0,
                "verdict": "PASS",
                "final_verdict": "PASS",
                "relevance_score": 95.0,
                "accuracy_score": 98.0,
                "completeness_score": 94.0,
                "hallucination_score": 100.0,
                "hallucination_risk": 0.0
            },
            {
                "row_id": 2,
                "response_id": "RESP-2",
                "question": "What is the boiling point of water?",
                "ai_response": "Water boils at 50 degrees Celsius.",
                "reference_answer": "Water boils at 100 degrees Celsius at sea level.",
                "overall_score": 38.0,
                "verdict": "FAIL",
                "final_verdict": "FAIL",
                "relevance_score": 80.0,
                "accuracy_score": 20.0,
                "completeness_score": 40.0,
                "hallucination_score": 20.0,
                "hallucination_risk": 80.0
            }
        ]
        sample_summary = {
            "batch_id": "BATCH-TEST-PDF-001",
            "dataset_name": "test_batch.csv",
            "evaluation_time": "2026-10-05 12:00:00 UTC",
            "total_records": 2,
            "actually_evaluated": 2,
            "average_overall": 67.0,
            "average_score": 67.0,
            "average_relevance": 87.5,
            "average_accuracy": 59.0,
            "average_completeness": 67.0,
            "average_hallucination": 60.0,
            "pass_rate": 50.0,
            "needs_improvement_rate": 0.0,
            "fail_rate": 50.0,
            "hallucination_frequency": 50.0,
            "verdict_counts": {"PASS": 1, "FAIL": 1, "NEEDS IMPROVEMENT": 0},
            "recurring_issues": [
                {
                    "issue": "Low Factual Accuracy to Evidence",
                    "category": "Factual Grounding",
                    "count": 1,
                    "percentage": 50.0,
                    "severity": "High"
                }
            ]
        }
        res = self.client.post("/api/batch/report/pdf", json={"summary": sample_summary, "results": sample_results})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers.get("content-type"), "application/pdf")
        self.assertTrue(res.content.startswith(b"%PDF"))
        self.assertGreater(len(res.content), 2000)

    # =========================================================================
    # 3. MULTI-AGENT ARBITRATION & INVARIANTS TESTS
    # =========================================================================

    def test_multi_agent_arbitration_consistency(self):
        """Verifies that an AI response with clear hallucinations receives severe penalty or FAIL."""
        req = EvaluationRequest(
            question="What is the speed of sound in air?",
            ai_response="The speed of sound in air is 9,000 meters per second and dry air contains gold dust.",
            reference_answer="The speed of sound in dry air at 20 degrees Celsius is approximately 343 meters per second."
        )
        resp = self.orchestrator.evaluate(req)

        self.assertIn(resp.evaluation.verdict, ["Needs Improvement", "Poor", "FAIL"])
        self.assertLess(resp.evaluation.overall_score, 75.0)
        if resp.verdict_judge:
            self.assertIn(resp.verdict_judge.final_verdict, ["NEEDS IMPROVEMENT", "FAIL"])

    def test_scoring_boundaries_and_formula_weights(self):
        """Verifies that scores strictly satisfy boundaries [0.0, 100.0] and weighted formula."""
        req = EvaluationRequest(
            question="What is the boiling point of water at sea level?",
            ai_response="Water boils at 100 degrees Celsius under standard atmospheric pressure.",
            reference_answer="At standard atmospheric pressure, water boils at 100°C (212°F)."
        )
        resp = self.orchestrator.evaluate(req)

        # 1. Boundary invariants
        self.assertGreaterEqual(resp.evaluation.overall_score, 0.0)
        self.assertLessEqual(resp.evaluation.overall_score, 100.0)
        self.assertGreaterEqual(resp.evaluation.relevance.score, 0.0)
        self.assertLessEqual(resp.evaluation.relevance.score, 100.0)
        self.assertGreaterEqual(resp.evaluation.accuracy.score, 0.0)
        self.assertLessEqual(resp.evaluation.accuracy.score, 100.0)
        self.assertGreaterEqual(resp.evaluation.completeness.score, 0.0)
        self.assertLessEqual(resp.evaluation.completeness.score, 100.0)
        self.assertGreaterEqual(resp.evaluation.hallucination.score, 0.0)
        self.assertLessEqual(resp.evaluation.hallucination.score, 100.0)

        # 2. Formula verification if verdict_judge present
        if resp.verdict_judge:
            vj = resp.verdict_judge
            expected_weighted = round(
                (vj.relevance_score * 0.25) +
                (vj.accuracy_score * 0.30) +
                (vj.completeness_score * 0.25) +
                (vj.hallucination_score * 0.20),
                1
            )
            self.assertAlmostEqual(vj.weighted_overall_score, expected_weighted, delta=0.5)

    # =========================================================================
    # 4. KNOWLEDGE BASE SEMANTIC RETRIEVAL
    # =========================================================================

    def test_semantic_retrieval_endpoint(self):
        """Verifies independent semantic retrieval from indexed knowledge base."""
        res = self.client.get("/api/retrieval", params={"question": "What is the capital of Australia?", "top_k": 3})
        self.assertEqual(res.status_code, 200)
        chunks = res.json()
        self.assertIsInstance(chunks, list)
        self.assertGreater(len(chunks), 0)
        first_chunk = chunks[0]
        self.assertIn("content", first_chunk)
        self.assertIn("similarity_score", first_chunk)

    # =========================================================================
    # 5. DASHBOARD ANALYTICS API TESTS
    # =========================================================================

    def test_dashboard_analytics_api(self):
        """Verifies GET /api/dashboard/analytics returns structured multi-run aggregation."""
        res = self.client.get("/api/dashboard/analytics")
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertIn("kpis", data)
        self.assertIn("dimensions", data)
        self.assertIn("score_distributions", data)
        self.assertIn("verdict_distribution", data)
        self.assertIn("hallucination_stats", data)
        self.assertIn("completeness_stats", data)
        self.assertIn("batch_summaries", data)
        self.assertIn("records", data)
        self.assertIn("total_evaluations", data["kpis"])
        self.assertIn("pass_rate", data["kpis"])
        self.assertIn("average_score", data["kpis"])

    # =========================================================================
    # 6. LIVE AUTOMATED TEST RUNNER API (M4.3)
    # =========================================================================

    def test_automated_test_runner_api(self):
        """Verifies POST /api/testing/run executes real test suites across 10 categories."""
        res = self.client.post("/api/testing/run")
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertEqual(data.get("status"), "COMPLETED")
        self.assertGreaterEqual(data.get("total_tests", 0), 10)
        self.assertGreaterEqual(data.get("passed", 0), 8)
        self.assertIn("pass_percentage", data)
        self.assertIn("categories", data)
        self.assertEqual(len(data["categories"]), 10)

        # Check required categories are present
        category_names = [c["category"] for c in data["categories"]]
        self.assertIn("Single Evaluation Tests", category_names)
        self.assertIn("Batch Evaluation Tests", category_names)
        self.assertIn("Agent Validation Tests", category_names)
        self.assertIn("Hallucination Tests", category_names)
        self.assertIn("Completeness Tests", category_names)
        self.assertIn("Verdict Tests", category_names)
        self.assertIn("Dashboard Validation", category_names)
        self.assertIn("PDF Validation", category_names)
        self.assertIn("Error Handling", category_names)
        self.assertIn("Performance Tests", category_names)

    # =========================================================================
    # 7. LATENCY BENCHMARK
    # =========================================================================

    def test_evaluation_latency_benchmark(self):
        """Verifies that evaluation executes within acceptable responsive latency (< 15 seconds)."""
        start = time.perf_counter()
        req = EvaluationRequest(
            question="What is the speed of sound in air?",
            ai_response="The speed of sound in dry air at 20 degrees Celsius is approximately 343 meters per second.",
            reference_answer="About 343 m/s at 20°C."
        )
        resp = self.orchestrator.evaluate(req)
        duration = time.perf_counter() - start

        self.assertIsNotNone(resp.evaluation.verdict)
        self.assertLess(duration, 15.0, f"Evaluation took {duration:.2f}s, exceeding 15.0s benchmark")


if __name__ == "__main__":
    unittest.main()
