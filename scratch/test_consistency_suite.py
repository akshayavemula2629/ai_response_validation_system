import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

from backend.agents.orchestrator import EvaluationOrchestrator
from backend.api.schemas.evaluation import EvaluationRequest

orchestrator = EvaluationOrchestrator()

def run_tests():
    print("=" * 60)
    print("RUNNING CONSISTENCY TEST SUITE (TEST A, TEST B, TEST C)")
    print("=" * 60)

    # TEST A: Correct Answer
    print("\n--- TEST A: Correct Answer ---")
    req_a = EvaluationRequest(
        question="What is the capital of Australia?",
        ai_response="The capital city of Australia is Canberra.",
        reference_answer="The capital of Australia is Canberra."
    )
    res_a = orchestrator.evaluate(req_a)
    print(f"Accuracy Score: {res_a.evaluation.accuracy.score}")
    print(f"Accuracy Category: {res_a.accuracy_judge.category}")
    print(f"Hallucination Risk %: {res_a.evaluation.hallucination.percentage}%")
    print(f"Hallucination-Free Score: {res_a.evaluation.hallucination.score}")
    print(f"Hallucination Risk Level: {res_a.evaluation.hallucination.risk_level}")
    print(f"Claims: Total={res_a.hallucination_judge.total_claims}, Sup={res_a.hallucination_judge.supported_claims}, Contra={res_a.hallucination_judge.contradicted_claims}, Unsup={res_a.hallucination_judge.unsupported_claims}")
    print(f"Final Verdict: {res_a.verdict_judge.final_verdict}")
    print(f"Weighted Score: {res_a.verdict_judge.weighted_score}")

    assert res_a.evaluation.accuracy.score >= 85.0, "TEST A: Accuracy should be high"
    assert res_a.evaluation.hallucination.percentage == 0.0, "TEST A: Hallucination risk should be 0.0%"
    assert res_a.evaluation.hallucination.score == 100.0, "TEST A: Hallucination-free score should be 100.0"
    assert res_a.hallucination_judge.contradicted_claims == 0, "TEST A: Contradicted claims should be 0"
    assert res_a.hallucination_judge.supported_claims == res_a.hallucination_judge.total_claims, "TEST A: All claims supported"
    assert res_a.verdict_judge.final_verdict == "PASS", "TEST A: Verdict should be PASS"
    print(">>> TEST A PASSED! Grounded response has 0.0% hallucination risk.")

    # TEST B: Incorrect Factual Answer (Date Discrepancy)
    print("\n--- TEST B: Factual Date Discrepancy ---")
    req_b = EvaluationRequest(
        question="Who was the first person to walk on the Moon and when?",
        ai_response="Neil Armstrong walked on the Moon during the Apollo 11 spaceflight, landing there in 1975.",
        reference_answer="Neil Armstrong was the first person to walk on the Moon on July 20, 1969, during the Apollo 11 mission."
    )
    res_b = orchestrator.evaluate(req_b)
    print(f"Accuracy Score: {res_b.evaluation.accuracy.score}")
    print(f"Accuracy Issues: {res_b.accuracy_judge.issues}")
    print(f"Hallucination Risk %: {res_b.evaluation.hallucination.percentage}%")
    print(f"Hallucination-Free Score: {res_b.evaluation.hallucination.score}")
    print(f"Hallucination Risk Level: {res_b.evaluation.hallucination.risk_level}")
    print(f"Claims: Total={res_b.hallucination_judge.total_claims}, Sup={res_b.hallucination_judge.supported_claims}, Contra={res_b.hallucination_judge.contradicted_claims}, Unsup={res_b.hallucination_judge.unsupported_claims}")
    print(f"Final Verdict: {res_b.verdict_judge.final_verdict}")
    print(f"Weighted Score: {res_b.verdict_judge.weighted_score}")

    assert res_b.evaluation.accuracy.score < 60.0, "TEST B: Accuracy should detect factual issue"
    assert res_b.evaluation.hallucination.percentage > 50.0, "TEST B: Hallucination risk should reflect contradiction"
    assert res_b.hallucination_judge.contradicted_claims > 0, "TEST B: Contradicted claim count should be > 0"
    assert res_b.verdict_judge.final_verdict in ["FAIL", "NEEDS IMPROVEMENT"], "TEST B: Verdict should not be PASS"
    print(">>> TEST B PASSED! Contradicted claim correctly identified and reflected across Accuracy & Hallucination.")

    # TEST C: Unsupported Fabricated Statement
    print("\n--- TEST C: Unsupported Fabricated Statement ---")
    req_c = EvaluationRequest(
        question="What did the Apollo 11 astronauts find on the lunar surface?",
        ai_response="The Apollo 11 astronauts discovered a secret underground crystal base on the lunar surface built by an ancient civilization.",
        reference_answer="During Apollo 11, astronauts collected 47.5 pounds of lunar rock samples and deployed scientific experiments."
    )
    res_c = orchestrator.evaluate(req_c)
    print(f"Accuracy Score: {res_c.evaluation.accuracy.score}")
    print(f"Hallucination Risk %: {res_c.evaluation.hallucination.percentage}%")
    print(f"Hallucination-Free Score: {res_c.evaluation.hallucination.score}")
    print(f"Hallucination Risk Level: {res_c.evaluation.hallucination.risk_level}")
    print(f"Claims: Total={res_c.hallucination_judge.total_claims}, Sup={res_c.hallucination_judge.supported_claims}, Contra={res_c.hallucination_judge.contradicted_claims}, Unsup={res_c.hallucination_judge.unsupported_claims}")
    print(f"Final Verdict: {res_c.verdict_judge.final_verdict}")
    print(f"Weighted Score: {res_c.verdict_judge.weighted_score}")

    assert res_c.evaluation.hallucination.percentage >= 60.0, "TEST C: Hallucination risk should be elevated"
    assert res_c.hallucination_judge.unsupported_claims > 0, "TEST C: Unsupported claims should be detected"
    print(">>> TEST C PASSED! Fabricated claim detected as unsupported with elevated hallucination risk.")

    print("\n" + "=" * 60)
    print("ALL CONSISTENCY TESTS (A, B, C) PASSED SUCCESSFULLY!")
    print("=" * 60)

if __name__ == "__main__":
    run_tests()
