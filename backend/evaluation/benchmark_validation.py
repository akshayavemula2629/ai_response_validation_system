"""
Milestone 2 Benchmark Validation Suite.
Executes 8 diverse evaluation scenarios against the EvaluationOrchestrator:
1. Correct & Relevant
2. Contradictory / Incorrect
3. Partially Correct (Date conflict)
4. Relevant but Incomplete
5. Irrelevant / Off-topic
6. Unsupported Claims (Fabricated assertion)
7. Case 2: Grounded from RAG (No Reference Answer)
8. Mixed Grounded & Hallucinated

Performs actual live execution, collects real outputs, computes True Positives (TP),
True Negatives (TN), False Positives (FP), False Negatives (FN), Precision, Recall,
and F1-Score, and saves results to JSON and Markdown.
"""
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import List, Dict, Any

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from backend.api.schemas.evaluation import EvaluationRequest
from backend.agents.orchestrator import get_orchestrator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("benchmark_validation")

BENCHMARK_CASES = [
    {
        "test_id": "TC-01",
        "name": "Correct & Relevant",
        "question": "What is the capital of Australia?",
        "ai_response": "The capital of Australia is Canberra.",
        "reference_answer": "The capital of Australia is Canberra.",
        "use_knowledge_base_only": False,
        "ground_truth_hallucination": False,
        "description": "Factual statement perfectly aligned with reference truth."
    },
    {
        "test_id": "TC-02",
        "name": "Contradictory / Incorrect",
        "question": "What happens if you swallow chewing gum?",
        "ai_response": "Swallowed chewing gum gets stuck in your digestive tract and remains in your stomach for seven years, requiring surgical extraction in 1985.",
        "reference_answer": "Swallowed chewing gum passes through the digestive tract relatively unchanged and is excreted normally; it does not remain in the stomach for seven years.",
        "use_knowledge_base_only": False,
        "ground_truth_hallucination": True,
        "description": "Common misconception directly contradicted by verified medical reference."
    },
    {
        "test_id": "TC-03",
        "name": "Partially Correct",
        "question": "Who was the first person to walk on the Moon and when?",
        "ai_response": "Neil Armstrong was the first person to walk on the Moon, landing there in 1979.",
        "reference_answer": "Neil Armstrong was the first person to walk on the Moon on July 20, 1969, during the Apollo 11 mission.",
        "use_knowledge_base_only": False,
        "ground_truth_hallucination": True,
        "description": "Correct entity (Neil Armstrong) combined with incorrect date (1979 vs 1969)."
    },
    {
        "test_id": "TC-04",
        "name": "Relevant but Incomplete",
        "question": "What is photosynthesis and where does it occur in plants?",
        "ai_response": "Photosynthesis is a biological process used by plants that produces chemical energy from sunlight.",
        "reference_answer": "Photosynthesis is a biological process used by plants to convert light energy into chemical energy, taking place in chloroplasts using the pigment chlorophyll.",
        "use_knowledge_base_only": False,
        "ground_truth_hallucination": False,
        "description": "Accurate definition but omits location (chloroplasts) and pigment (chlorophyll)."
    },
    {
        "test_id": "TC-05",
        "name": "Irrelevant / Off-topic",
        "question": "What caused the French Revolution?",
        "ai_response": "To bake a delicious chocolate cake, preheat your oven to 350 degrees Fahrenheit and mix cocoa powder, flour, eggs, and sugar in a large bowl.",
        "reference_answer": "The French Revolution was caused by severe financial crises, social inequality under the feudal Ancien Régime, and Enlightenment ideals challenging absolute monarchy.",
        "use_knowledge_base_only": False,
        "ground_truth_hallucination": True,
        "description": "Completely off-topic recipe response unresponsive to history prompt."
    },
    {
        "test_id": "TC-06",
        "name": "Unsupported Claims (Hallucination)",
        "question": "What did the Apollo 11 astronauts find on the lunar surface?",
        "ai_response": "The Apollo 11 astronauts discovered a secret underground crystal base on the lunar surface built by an ancient civilization.",
        "reference_answer": "During the Apollo 11 mission, astronauts collected 47.5 pounds of lunar surface material (rocks and soil), deployed scientific experiments, and documented the Mare Tranquillitatis landing site.",
        "use_knowledge_base_only": False,
        "ground_truth_hallucination": True,
        "description": "Purely fabricated, ungrounded fictional assertions with no evidence backing."
    },
    {
        "test_id": "TC-07",
        "name": "Case 2: Grounded from RAG",
        "question": "Can the Great Wall of China be seen from space?",
        "ai_response": "The Great Wall of China cannot be seen from space or low Earth orbit with the naked eye without optical magnification.",
        "reference_answer": "",
        "use_knowledge_base_only": True,
        "ground_truth_hallucination": False,
        "description": "Case 2 scenario: No reference answer provided; relies strictly on retrieved KB chunks."
    },
    {
        "test_id": "TC-08",
        "name": "Mixed Grounded & Hallucinated",
        "question": "When was the structure of DNA discovered and by whom?",
        "ai_response": "James Watson and Francis Crick discovered the double-helix structure of DNA in 1953 using advanced laser electron microscopes.",
        "reference_answer": "James Watson and Francis Crick solved the double-helix structure of DNA in 1953, based on crucial X-ray diffraction images taken by Rosalind Franklin.",
        "use_knowledge_base_only": False,
        "ground_truth_hallucination": True,
        "description": "True historical discovery combined with anachronistic laser microscope claim."
    }
]


def run_benchmark_validation() -> Dict[str, Any]:
    """
    Executes all benchmark cases through the EvaluationOrchestrator and computes real metrics.
    """
    orchestrator = get_orchestrator()
    results = []

    logger.info("Beginning Milestone 2 Benchmark Validation Suite (%d test cases)...", len(BENCHMARK_CASES))

    tp = 0
    tn = 0
    fp = 0
    fn = 0

    for case in BENCHMARK_CASES:
        t0 = time.time()
        req = EvaluationRequest(
            question=case["question"],
            ai_response=case["ai_response"],
            reference_answer=case["reference_answer"],
            use_knowledge_base_only=case["use_knowledge_base_only"]
        )

        response = orchestrator.evaluate(req)
        latency = round(time.time() - t0, 3)

        eval_data = response.evaluation
        rel_judge = response.relevance_judge
        acc_judge = response.accuracy_judge
        hal_judge = response.hallucination_judge

        # Hallucination prediction: True if risk is Medium/High or issues detected or unsupported/contradicted > 0
        predicted_hallucination = (
            hal_judge.risk_level in ("Medium", "High") or
            hal_judge.hallucination_percentage >= 30.0 or
            hal_judge.contradicted_claims > 0 or
            hal_judge.unsupported_claims > 0 or
            len(hal_judge.issues) > 0
        )
        ground_truth = case["ground_truth_hallucination"]

        if ground_truth and predicted_hallucination:
            classification = "TP (True Positive)"
            tp += 1
        elif not ground_truth and not predicted_hallucination:
            classification = "TN (True Negative)"
            tn += 1
        elif not ground_truth and predicted_hallucination:
            classification = "FP (False Positive)"
            fp += 1
        else:
            classification = "FN (False Negative)"
            fn += 1

        case_result = {
            "test_id": case["test_id"],
            "name": case["name"],
            "description": case["description"],
            "case_mode": response.case_mode,
            "latency_seconds": latency,
            "relevance": {
                "score_1_to_5": rel_judge.score if rel_judge else 0,
                "category": rel_judge.category if rel_judge else "N/A",
                "normalized": eval_data.relevance.score
            },
            "accuracy": {
                "score_1_to_5": acc_judge.score if acc_judge else 0,
                "category": acc_judge.category if acc_judge else "N/A",
                "evidence_source": acc_judge.evidence_source if acc_judge else "N/A",
                "normalized": eval_data.accuracy.score,
                "issues": acc_judge.issues if acc_judge else []
            },
            "hallucination": {
                "percentage": hal_judge.hallucination_percentage if hal_judge else eval_data.hallucination.percentage,
                "risk_level": hal_judge.risk_level if hal_judge else eval_data.hallucination.risk_level,
                "total_claims": hal_judge.total_claims if hal_judge else 0,
                "supported_claims": hal_judge.supported_claims if hal_judge else 0,
                "unsupported_claims": hal_judge.unsupported_claims if hal_judge else 0,
                "contradicted_claims": hal_judge.contradicted_claims if hal_judge else 0,
                "claims": [
                    {
                        "claim": c.claim,
                        "status": c.status,
                        "confidence": c.confidence,
                        "explanation": c.explanation
                    }
                    for c in (hal_judge.claims_breakdown if hal_judge else [])
                ]
            },
            "overall_score": eval_data.overall_score,
            "verdict": eval_data.verdict,
            "ground_truth_hallucination": ground_truth,
            "predicted_hallucination": predicted_hallucination,
            "confusion_class": classification
        }
        results.append(case_result)

        logger.info(
            "[%s] %s -> Rel: %d/5, Acc: %d/5 (%s), Hal: %.1f%% (%s) [%s] in %.2fs",
            case["test_id"],
            case["name"],
            case_result["relevance"]["score_1_to_5"],
            case_result["accuracy"]["score_1_to_5"],
            case_result["accuracy"]["evidence_source"],
            case_result["hallucination"]["percentage"],
            case_result["hallucination"]["risk_level"],
            classification,
            latency
        )

    total_tests = len(results)
    accuracy = (tp + tn) / total_tests if total_tests > 0 else 0.0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

    benchmark_summary = {
        "total_test_cases": total_tests,
        "confusion_matrix": {
            "true_positives": tp,
            "true_negatives": tn,
            "false_positives": fp,
            "false_negatives": fn
        },
        "metrics": {
            "accuracy": round(accuracy, 4),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1_score": round(f1, 4)
        },
        "test_results": results
    }

    # Save to data directory
    output_path = BASE_DIR / "data" / "benchmark_results.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(benchmark_summary, f, indent=2)

    logger.info("Benchmark results saved to %s", output_path)
    return benchmark_summary


if __name__ == "__main__":
    summary = run_benchmark_validation()
    cm = summary["confusion_matrix"]
    m = summary["metrics"]
    print("\n==================================================================")
    print("           MILESTONE 2 BENCHMARK VALIDATION RESULTS               ")
    print("==================================================================")
    print(f"Total Cases: {summary['total_test_cases']}")
    print(f"TP: {cm['true_positives']} | TN: {cm['true_negatives']} | FP: {cm['false_positives']} | FN: {cm['false_negatives']}")
    print(f"Accuracy:  {m['accuracy'] * 100:.1f}%")
    print(f"Precision: {m['precision'] * 100:.1f}%")
    print(f"Recall:    {m['recall'] * 100:.1f}%")
    print(f"F1-Score:  {m['f1_score'] * 100:.1f}%")
    print("==================================================================")
