"""
Live API Integration Verification Script.
Tests:
1. Single evaluation with valid payload (Verifies CompletenessJudgeResult and VerdictJudgeResult).
2. Single evaluation with missing reference answer (Verifies HTTP 422 validation failure).
3. Batch evaluation with sample CSV containing 10 rows (1 invalid row testing fault tolerance).
"""
import urllib.request
import urllib.error
import json
import uuid
from pathlib import Path

def test_single_eval():
    url = "http://127.0.0.1:8000/api/evaluate"
    payload = {
        "question": "What is the capital of Australia?",
        "ai_response": "The capital of Australia is Canberra.",
        "reference_answer": "The capital of Australia is Canberra."
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200, f"Expected 200, got {resp.status}"
        data = json.loads(resp.read().decode())
        print("[PASS] Single evaluation succeeded with HTTP 200")
        print(f"       Overall Score: {data['evaluation']['overall_score']}")
        print(f"       Verdict Agent Final Verdict: {data['verdict_judge']['final_verdict']}")
        print(f"       Verdict Weighted Score: {data['verdict_judge']['weighted_score']}")
        print(f"       Completeness Score: {data['completeness_judge']['score']}")
        print(f"       Addressed Aspects: {data['completeness_judge']['addressed_aspects']}")
        assert data['verdict_judge']['final_verdict'] in ["PASS", "NEEDS IMPROVEMENT", "FAIL"]
        assert len(data['completeness_judge']['addressed_aspects']) > 0

def test_missing_ref():
    url = "http://127.0.0.1:8000/api/evaluate"
    payload = {
        "question": "What is the capital of Australia?",
        "ai_response": "The capital of Australia is Canberra."
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    try:
        urllib.request.urlopen(req)
        raise AssertionError("Expected HTTP 422 for missing reference answer, but succeeded!")
    except urllib.error.HTTPError as e:
        assert e.code == 422, f"Expected 422, got {e.code}"
        print(f"[PASS] Missing reference answer correctly rejected with HTTP {e.code}")

def test_batch_eval():
    url = "http://127.0.0.1:8000/api/batch/evaluate"
    csv_path = Path(__file__).resolve().parent.parent / "data" / "sample_batch_evaluation.csv"
    assert csv_path.exists(), f"CSV file not found at {csv_path}"
    
    boundary = uuid.uuid4().hex
    body = (
        f"--{boundary}\r\n"
        f"Content-Disposition: form-data; name=\"file\"; filename=\"{csv_path.name}\"\r\n"
        f"Content-Type: text/csv\r\n\r\n"
        f"{csv_path.read_text(encoding='utf-8')}\r\n"
        f"--{boundary}--\r\n"
    ).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
    )
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200, f"Expected 200, got {resp.status}"
        data = json.loads(resp.read().decode())
        summary = data["summary"]
        print("[PASS] Batch evaluation succeeded with HTTP 200")
        print(f"       Total rows: {summary['total_rows']}")
        print(f"       Valid rows: {summary['valid_rows']}")
        print(f"       Invalid rows: {summary['invalid_rows']}")
        print(f"       Average Score: {summary['average_score']}%")
        print(f"       Verdict Distribution: {summary['verdict_distribution']}")
        print(f"       High Hallucination Risk Count: {summary['high_hallucination_risk_count']}")
        assert summary["total_rows"] == 10
        assert summary["valid_rows"] == 9
        assert summary["invalid_rows"] == 1
        assert "PASS" in summary["verdict_distribution"]
        assert "FAIL" in summary["verdict_distribution"]

if __name__ == "__main__":
    print("Testing Live API Integration...")
    test_single_eval()
    test_missing_ref()
    test_batch_eval()
    print("\nALL LIVE API INTEGRATION CHECKS PASSED SUCCESSFULLY!")
