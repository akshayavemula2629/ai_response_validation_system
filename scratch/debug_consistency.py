import sys
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

from backend.agents.orchestrator import EvaluationOrchestrator
from backend.api.schemas.evaluation import EvaluationRequest

orchestrator = EvaluationOrchestrator()

# Test Case B from User:
req = EvaluationRequest(
    question="When did Neil Armstrong first walk on the Moon?",
    ai_response="Neil Armstrong first walked on the Moon in 1975.",
    reference_answer="Neil Armstrong first walked on the Moon on July 20, 1969."
)

result = orchestrator.evaluate(req)

print("--- EVALUATION RESULT ---")
print("Accuracy Score:", result.evaluation.accuracy.score)
print("Accuracy Category:", result.accuracy_judge.category if result.accuracy_judge else None)
print("Accuracy Issues:", result.accuracy_judge.issues if result.accuracy_judge else None)
print("\nHallucination Percentage:", result.evaluation.hallucination.percentage)
print("Hallucination Risk Level:", result.evaluation.hallucination.risk_level)
print("Hallucination Score (Hallucination-Free):", result.evaluation.hallucination.score)
print("Hallucination Issues:", result.evaluation.hallucination.issues)
if result.hallucination_judge:
    print("Total Claims:", result.hallucination_judge.total_claims)
    print("Supported Claims:", result.hallucination_judge.supported_claims)
    print("Unsupported Claims:", result.hallucination_judge.unsupported_claims)
    print("Contradicted Claims:", result.hallucination_judge.contradicted_claims)
    for c in result.hallucination_judge.claims_breakdown:
        print(f"  Claim: '{c.claim}' | Status: {c.status} | Exp: {c.explanation}")

print("\nVerdict Agent Final Verdict:", result.verdict_judge.final_verdict if result.verdict_judge else None)
print("Verdict Weighted Score:", result.verdict_judge.weighted_score if result.verdict_judge else None)
print("Severe Hallucination Override:", result.verdict_judge.severe_hallucination_override if result.verdict_judge else None)
