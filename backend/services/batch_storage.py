"""
Persistent Storage and Analytics Service for Evaluation Runs.
Provides thread-safe storage and aggregated metrics across Single and Batch evaluations.
"""
import os
import json
import logging
import threading
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

STORAGE_LOCK = threading.Lock()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BASE_DIR, "data", "processed")
BATCHES_DIR = os.path.join(DATA_DIR, "batches")
BATCH_HISTORY_FILE = os.path.join(DATA_DIR, "batch_history.json")
SINGLE_EVALS_FILE = os.path.join(DATA_DIR, "single_evaluations.json")


def ensure_storage_dirs():
    """Ensure data/processed and data/processed/batches directories exist."""
    os.makedirs(BATCHES_DIR, exist_ok=True)
    if not os.path.exists(BATCH_HISTORY_FILE):
        with open(BATCH_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump([], f)
    if not os.path.exists(SINGLE_EVALS_FILE):
        with open(SINGLE_EVALS_FILE, "w", encoding="utf-8") as f:
            json.dump([], f)


def compute_batch_analytics(results: List[Dict[str, Any]], summary: Dict[str, Any]) -> Dict[str, Any]:
    """
    Computes analytics across a list of evaluation records.
    Calculates dimension averages, score distributions, hallucination risk tiers,
    completeness distributions, and ranked recurring issues.
    """
    total_evaluated = len(results)
    if total_evaluated == 0:
        return {
            "verdict_distribution": {
                "PASS": {"count": 0, "percentage": 0.0},
                "NEEDS IMPROVEMENT": {"count": 0, "percentage": 0.0},
                "FAIL": {"count": 0, "percentage": 0.0}
            },
            "dimension_averages": {
                "relevance": 0.0,
                "accuracy": 0.0,
                "hallucination_safety": 0.0,
                "completeness": 0.0,
                "similarity": 0.0,
                "overall_score": 0.0
            },
            "score_distributions": {"0-40": 0, "41-70": 0, "71-85": 0, "86-100": 0},
            "hallucination_stats": {
                "hallucinated_responses_count": 0,
                "hallucination_free_count": 0,
                "hallucination_frequency_pct": 0.0,
                "total_unsupported_claims": 0,
                "total_claims_evaluated": 0,
                "unsupported_claim_frequency_pct": 0.0,
                "risk_distribution": {"low": 0, "medium": 0, "high": 0}
            },
            "completeness_stats": {
                "complete_count": 0,
                "partial_count": 0,
                "incomplete_count": 0,
                "missing_info_frequency_pct": 0.0,
                "commonly_omitted_aspects": []
            },
            "recurring_issues": []
        }

    # Verdict Distribution
    verdict_counts = {"PASS": 0, "NEEDS IMPROVEMENT": 0, "FAIL": 0}
    for r in results:
        v = (r.get("final_verdict") or r.get("verdict") or "FAIL").upper()
        if "PASS" in v and "NEEDS" not in v:
            verdict_counts["PASS"] += 1
        elif "NEEDS" in v or "IMPROVEMENT" in v:
            verdict_counts["NEEDS IMPROVEMENT"] += 1
        else:
            verdict_counts["FAIL"] += 1

    verdict_dist = {
        k: {
            "count": count,
            "percentage": round((count / total_evaluated) * 100.0, 1)
        }
        for k, count in verdict_counts.items()
    }

    # Dimension Scores & Distributions
    rel_scores, acc_scores, hal_safeties, comp_scores, sim_scores, ovr_scores = [], [], [], [], [], []
    score_dist = {"0-40": 0, "41-70": 0, "71-85": 0, "86-100": 0}

    # Hallucination & Completeness deep inspection
    hallucinated_resp = 0
    hal_free_resp = 0
    total_unsupported_claims = 0
    total_claims = 0
    risk_dist = {"low": 0, "medium": 0, "high": 0}

    complete_cnt = 0
    partial_cnt = 0
    incomplete_cnt = 0
    omitted_aspects_map: Dict[str, int] = {}

    # Common issue tracking
    low_rel_cnt = 0
    low_acc_cnt = 0
    hallucination_detected_cnt = 0
    incomplete_coverage_cnt = 0

    for r in results:
        # Relevance
        rel = float(r.get("relevance_score") or 0.0)
        rel_scores.append(rel)
        if rel < 60.0:
            low_rel_cnt += 1

        # Accuracy
        acc = float(r.get("accuracy_score") or 0.0)
        acc_scores.append(acc)
        if acc < 60.0:
            low_acc_cnt += 1

        # Hallucination
        hal_risk = float(r.get("hallucination_percentage") or r.get("hallucination_risk") or 0.0)
        hal_safety = max(0.0, 100.0 - hal_risk)
        hal_safeties.append(hal_safety)

        if hal_risk > 20.0:
            hallucinated_resp += 1
            hallucination_detected_cnt += 1
        else:
            hal_free_resp += 1

        if hal_risk <= 10.0:
            risk_dist["low"] += 1
        elif hal_risk <= 30.0:
            risk_dist["medium"] += 1
        else:
            risk_dist["high"] += 1

        # Completeness
        comp = float(r.get("completeness_score") or 0.0)
        comp_scores.append(comp)
        if comp >= 90.0:
            complete_cnt += 1
        elif comp >= 60.0:
            partial_cnt += 1
            incomplete_coverage_cnt += 1
        else:
            incomplete_cnt += 1
            incomplete_coverage_cnt += 1

        # Similarity
        sim = float(r.get("similarity_score") or 0.0)
        if sim > 0:
            sim_scores.append(sim)

        # Overall
        ovr = float(r.get("overall_score") or 0.0)
        ovr_scores.append(ovr)
        if ovr <= 40.0:
            score_dist["0-40"] += 1
        elif ovr <= 70.0:
            score_dist["41-70"] += 1
        elif ovr <= 85.0:
            score_dist["71-85"] += 1
        else:
            score_dist["86-100"] += 1

        # Detailed evaluation breakdown
        eval_detail = r.get("evaluation_detail") or r.get("evaluation_response") or {}
        if isinstance(eval_detail, dict):
            h_judge = eval_detail.get("hallucination_judge") or {}
            if isinstance(h_judge, dict):
                total_unsupported_claims += int(h_judge.get("unsupported_claims", 0))
                total_claims += int(h_judge.get("total_claims", 1))

            c_judge = eval_detail.get("completeness_judge") or {}
            if isinstance(c_judge, dict):
                for missing in c_judge.get("missing_aspects", []):
                    m_str = str(missing).strip()
                    if m_str:
                        omitted_aspects_map[m_str] = omitted_aspects_map.get(m_str, 0) + 1

        # Fallback missing elements from row
        missing = r.get("missing_elements") or []
        if isinstance(missing, list):
            for m in missing:
                m_str = str(m).strip()
                if m_str:
                    omitted_aspects_map[m_str] = omitted_aspects_map.get(m_str, 0) + 1

    def safe_mean(lst: List[float]) -> float:
        return round(sum(lst) / len(lst), 1) if lst else 0.0

    dim_averages = {
        "relevance": safe_mean(rel_scores),
        "accuracy": safe_mean(acc_scores),
        "hallucination_safety": safe_mean(hal_safeties),
        "completeness": safe_mean(comp_scores),
        "similarity": safe_mean(sim_scores),
        "overall_score": safe_mean(ovr_scores)
    }

    # Commonly omitted aspects sorted by frequency
    sorted_omitted = [
        {"aspect": k, "count": v, "percentage": round((v / total_evaluated) * 100.0, 1)}
        for k, v in sorted(omitted_aspects_map.items(), key=lambda x: x[1], reverse=True)[:5]
    ]

    # Rank recurring issues
    recurring_issues = []
    if hallucination_detected_cnt > 0:
        recurring_issues.append({
            "issue": "Hallucinated / Contradicted Claims",
            "category": "Hallucination Risk",
            "count": hallucination_detected_cnt,
            "percentage": round((hallucination_detected_cnt / total_evaluated) * 100.0, 1),
            "severity": "High" if (hallucination_detected_cnt / total_evaluated) > 0.25 else "Medium"
        })
    if low_acc_cnt > 0:
        recurring_issues.append({
            "issue": "Low Factual Accuracy to Evidence",
            "category": "Factual Grounding",
            "count": low_acc_cnt,
            "percentage": round((low_acc_cnt / total_evaluated) * 100.0, 1),
            "severity": "High" if (low_acc_cnt / total_evaluated) > 0.25 else "Medium"
        })
    if incomplete_coverage_cnt > 0:
        recurring_issues.append({
            "issue": "Incomplete Coverage of Core Requirements",
            "category": "Completeness",
            "count": incomplete_coverage_cnt,
            "percentage": round((incomplete_coverage_cnt / total_evaluated) * 100.0, 1),
            "severity": "Medium"
        })
    if low_rel_cnt > 0:
        recurring_issues.append({
            "issue": "Partial Query Relevance / Semantic Deviation",
            "category": "Relevance",
            "count": low_rel_cnt,
            "percentage": round((low_rel_cnt / total_evaluated) * 100.0, 1),
            "severity": "Low"
        })

    recurring_issues.sort(key=lambda x: x["count"], reverse=True)

    return {
        "verdict_distribution": verdict_dist,
        "dimension_averages": dim_averages,
        "score_distributions": score_dist,
        "hallucination_stats": {
            "hallucinated_responses_count": hallucinated_resp,
            "hallucination_free_count": hal_free_resp,
            "hallucination_frequency_pct": round((hallucinated_resp / total_evaluated) * 100.0, 1),
            "total_unsupported_claims": total_unsupported_claims,
            "total_claims_evaluated": total_claims,
            "unsupported_claim_frequency_pct": round((total_unsupported_claims / total_claims) * 100.0, 1) if total_claims > 0 else 0.0,
            "risk_distribution": risk_dist
        },
        "completeness_stats": {
            "complete_count": complete_cnt,
            "partial_count": partial_cnt,
            "incomplete_count": incomplete_cnt,
            "missing_info_frequency_pct": round(((partial_cnt + incomplete_cnt) / total_evaluated) * 100.0, 1),
            "commonly_omitted_aspects": sorted_omitted
        },
        "recurring_issues": recurring_issues
    }


class BatchStorageService:
    """Manages persistent batch runs and trend tracking across evaluations."""

    @staticmethod
    def save_batch_run(summary: Dict[str, Any], results: List[Dict[str, Any]], dataset_name: str = "batch.csv") -> str:
        """
        Saves a batch evaluation run into persistent storage.
        Returns the generated or existing batch_id.
        """
        ensure_storage_dirs()

        batch_id = summary.get("batch_id")
        if not batch_id:
            batch_id = f"BATCH-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
            summary["batch_id"] = batch_id

        eval_time = summary.get("evaluation_time") or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        summary["evaluation_time"] = eval_time
        summary["dataset_name"] = dataset_name

        # Compute and attach analytics
        analytics = compute_batch_analytics(results, summary)
        summary["dimension_averages"] = analytics["dimension_averages"]
        summary["hallucination_stats"] = analytics["hallucination_stats"]
        summary["completeness_stats"] = analytics["completeness_stats"]
        summary["recurring_issues"] = analytics["recurring_issues"]
        summary["score_distributions"] = analytics["score_distributions"]
        summary["verdict_distribution"] = analytics["verdict_distribution"]

        total_eval = summary.get("actually_evaluated") or len(results)
        v_counts = summary.get("verdict_counts") or {}
        if total_eval > 0:
            summary["pass_rate"] = round((v_counts.get("PASS", 0) / total_eval) * 100.0, 1)
            summary["needs_improvement_rate"] = round((v_counts.get("NEEDS IMPROVEMENT", 0) / total_eval) * 100.0, 1)
            summary["fail_rate"] = round((v_counts.get("FAIL", 0) / total_eval) * 100.0, 1)

        batch_data = {
            "batch_id": batch_id,
            "dataset_name": dataset_name,
            "evaluation_time": eval_time,
            "summary": summary,
            "analytics": analytics,
            "results": results
        }

        with STORAGE_LOCK:
            # 1. Save individual full batch run
            batch_filepath = os.path.join(BATCHES_DIR, f"{batch_id}.json")
            with open(batch_filepath, "w", encoding="utf-8") as f:
                json.dump(batch_data, f, indent=2)

            # 2. Append/Update in index history
            history = []
            if os.path.exists(BATCH_HISTORY_FILE):
                try:
                    with open(BATCH_HISTORY_FILE, "r", encoding="utf-8") as f:
                        history = json.load(f)
                except Exception as e:
                    logger.warning("Error reading batch history file: %s", str(e))
                    history = []

            # Check if entry already exists
            entry_idx = next((i for i, b in enumerate(history) if b.get("batch_id") == batch_id), -1)
            history_entry = {
                "batch_id": batch_id,
                "dataset_name": dataset_name,
                "evaluation_time": eval_time,
                "total_records": summary.get("total_records", len(results)),
                "actually_evaluated": total_eval,
                "average_score": summary.get("average_overall", 0.0),
                "pass_rate": summary.get("pass_rate", 0.0),
                "needs_improvement_rate": summary.get("needs_improvement_rate", 0.0),
                "fail_rate": summary.get("fail_rate", 0.0),
                "hallucination_frequency": summary.get("hallucination_frequency", 0.0),
                "dimension_averages": analytics["dimension_averages"]
            }

            if entry_idx >= 0:
                history[entry_idx] = history_entry
            else:
                history.append(history_entry)

            with open(BATCH_HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(history, f, indent=2)

        logger.info("Successfully persisted batch run %s with %d records.", batch_id, len(results))
        return batch_id

    @staticmethod
    def get_batch_history() -> List[Dict[str, Any]]:
        """Retrieves list of all saved batch runs in chronological order."""
        ensure_storage_dirs()
        with STORAGE_LOCK:
            if not os.path.exists(BATCH_HISTORY_FILE):
                return []
            try:
                with open(BATCH_HISTORY_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error("Failed to read batch history: %s", str(e))
                return []

    @staticmethod
    def get_batch_by_id(batch_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves complete records and summary for a specific batch run."""
        ensure_storage_dirs()
        batch_filepath = os.path.join(BATCHES_DIR, f"{batch_id}.json")
        if not os.path.exists(batch_filepath):
            return None
        with STORAGE_LOCK:
            try:
                with open(batch_filepath, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error("Failed to load batch file %s: %s", batch_id, str(e))
                return None

    @staticmethod
    def save_single_evaluation(eval_record: Dict[str, Any]) -> str:
        """
        Persists a single response evaluation to single_evaluations.json.
        Returns the evaluation_id.
        """
        ensure_storage_dirs()
        eval_id = eval_record.get("evaluation_id")
        if not eval_id:
            eval_id = f"SINGLE-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f')[:21]}"
            eval_record["evaluation_id"] = eval_id

        if "timestamp" not in eval_record:
            eval_record["timestamp"] = datetime.now(timezone.utc).isoformat()

        with STORAGE_LOCK:
            evals = []
            if os.path.exists(SINGLE_EVALS_FILE):
                try:
                    with open(SINGLE_EVALS_FILE, "r", encoding="utf-8") as f:
                        evals = json.load(f)
                except Exception:
                    evals = []

            # Add to top (most recent first)
            evals.insert(0, eval_record)
            # Cap at 500 records
            evals = evals[:500]

            with open(SINGLE_EVALS_FILE, "w", encoding="utf-8") as f:
                json.dump(evals, f, indent=2)

        return eval_id

    @staticmethod
    def get_single_evaluations(limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieves recent single evaluation runs."""
        ensure_storage_dirs()
        with STORAGE_LOCK:
            if not os.path.exists(SINGLE_EVALS_FILE):
                return []
            try:
                with open(SINGLE_EVALS_FILE, "r", encoding="utf-8") as f:
                    records = json.load(f)
                    return records[:limit]
            except Exception as e:
                logger.error("Failed to read single evaluations: %s", str(e))
                return []

    @staticmethod
    def get_batch_trends() -> Dict[str, Any]:
        """Calculates trend trajectories across chronological evaluation runs."""
        history = BatchStorageService.get_batch_history()
        if not history:
            single_evals = BatchStorageService.get_single_evaluations(limit=10)
            if not single_evals:
                return {
                    "runs": [],
                    "score_trend": [],
                    "pass_rate_trend": [],
                    "hallucination_trend": [],
                    "run_items": []
                }
            runs = []
            score_trend = []
            pass_rate_trend = []
            hallucination_trend = []
            run_items = []
            for i, s in enumerate(reversed(single_evals)):
                eval_data = s.get("evaluation") or s
                scores = eval_data.get("scores") or {}
                avg_score = round(float(scores.get("overall_score") or s.get("overall_score") or 0.0), 1)
                verdict = (eval_data.get("verdict") or {}).get("verdict") or s.get("verdict") or "PASS"
                pass_rt = 100.0 if str(verdict).upper() == "PASS" else 0.0
                hal_risk = round(float(scores.get("hallucination_risk") or 0.0), 1)
                runs.append(f"Run {i + 1}")
                score_trend.append(avg_score)
                pass_rate_trend.append(pass_rt)
                hallucination_trend.append(hal_risk)
                run_items.append({
                    "batch_id": s.get("evaluation_id", f"Run {i + 1}"),
                    "run_label": f"Run {i + 1}",
                    "dataset_name": "Single Evaluation",
                    "average_score": avg_score,
                    "pass_rate": pass_rt,
                    "hallucination_frequency": hal_risk,
                    "evaluation_time": s.get("timestamp") or "",
                    "timestamp": s.get("timestamp") or ""
                })
            return {
                "runs": runs,
                "score_trend": score_trend,
                "pass_rate_trend": pass_rate_trend,
                "hallucination_trend": hallucination_trend,
                "run_items": run_items
            }

        runs = []
        score_trend = []
        pass_rate_trend = []
        hallucination_trend = []
        run_items = []

        for i, b in enumerate(history[-10:]):
            label = b.get("dataset_name") or b.get("batch_id", "")
            if len(label) > 15:
                label = label[:12] + "..."
            runs.append(label)
            avg_score = round(float(b.get("average_score") or 0.0), 1)
            pass_rt = round(float(b.get("pass_rate") or 0.0), 1)
            hal_freq = round(float(b.get("hallucination_frequency") or 0.0), 1)
            score_trend.append(avg_score)
            pass_rate_trend.append(pass_rt)
            hallucination_trend.append(hal_freq)
            run_items.append({
                "batch_id": b.get("batch_id", ""),
                "run_label": f"Run {i + 1}",
                "dataset_name": b.get("dataset_name") or b.get("batch_id", ""),
                "average_score": avg_score,
                "pass_rate": pass_rt,
                "hallucination_frequency": hal_freq,
                "evaluation_time": b.get("evaluation_time") or b.get("timestamp") or "",
                "timestamp": b.get("evaluation_time") or b.get("timestamp") or ""
            })

        return {
            "runs": runs,
            "score_trend": score_trend,
            "pass_rate_trend": pass_rate_trend,
            "hallucination_trend": hallucination_trend,
            "run_items": run_items
        }

    @staticmethod
    def get_dashboard_analytics(batch_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Aggregates stored evaluations across Single and Batch runs for Dashboard consumption.
        """
        history = BatchStorageService.get_batch_history()
        single_evals = BatchStorageService.get_single_evaluations()
        trends = BatchStorageService.get_batch_trends()

        # If a specific batch ID is requested and not 'ALL'
        if batch_id and batch_id != "ALL":
            batch_run = BatchStorageService.get_batch_by_id(batch_id)
            if batch_run:
                results = batch_run.get("results", [])
                summary = batch_run.get("summary", {})
                analytics = compute_batch_analytics(results, summary)
                for r in results:
                    r["batch_id"] = batch_id
                    r["mode"] = "BATCH"

                v_dist = analytics.get("verdict_distribution", {})
                kpis = {
                    "total_evaluations": len(results),
                    "pass_count": v_dist.get("PASS", {}).get("count", 0),
                    "pass_rate": v_dist.get("PASS", {}).get("percentage", 0.0),
                    "needs_improvement_count": v_dist.get("NEEDS IMPROVEMENT", {}).get("count", 0),
                    "needs_improvement_rate": v_dist.get("NEEDS IMPROVEMENT", {}).get("percentage", 0.0),
                    "fail_count": v_dist.get("FAIL", {}).get("count", 0),
                    "fail_rate": v_dist.get("FAIL", {}).get("percentage", 0.0),
                    "average_score": analytics.get("dimension_averages", {}).get("overall_score", 0.0),
                    "hallucination_frequency": analytics.get("hallucination_stats", {}).get("hallucination_frequency_pct", 0.0)
                }

                return {
                    "batches": history,
                    "batch_summaries": history,
                    "selected_batch_id": batch_id,
                    "dataset_name": batch_run.get("dataset_name", "batch.csv"),
                    "total_records": len(results),
                    "records": results,
                    "summary": summary,
                    "analytics": analytics,
                    "kpis": kpis,
                    "dimensions": analytics.get("dimension_averages", {}),
                    "dimension_averages": analytics.get("dimension_averages", {}),
                    "score_distributions": analytics.get("score_distributions", {}),
                    "verdict_distribution": v_dist,
                    "hallucination_stats": analytics.get("hallucination_stats", {}),
                    "completeness_stats": analytics.get("completeness_stats", {}),
                    "recurring_issues": analytics.get("recurring_issues", []),
                    "trends": trends,
                    "last_updated": batch_run.get("evaluation_time") or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
                }

        # Otherwise aggregate across historical batches and single evaluations
        all_records: List[Dict[str, Any]] = []

        # Load records from up to 10 latest batches
        for b in reversed(history[-10:]):
            b_id = b.get("batch_id")
            if b_id:
                b_run = BatchStorageService.get_batch_by_id(b_id)
                if b_run and "results" in b_run:
                    for r in b_run["results"]:
                        r_copy = dict(r)
                        r_copy["batch_id"] = b_id
                        r_copy["mode"] = "BATCH"
                        all_records.append(r_copy)

        # Include stored single evaluations
        for s in single_evals:
            all_records.append({
                "row_id": len(all_records) + 1,
                "response_id": s.get("evaluation_id"),
                "batch_id": "SINGLE",
                "mode": "SINGLE",
                "question": s.get("question", ""),
                "ai_response": s.get("ai_response", ""),
                "reference_answer": s.get("reference_answer", ""),
                "overall_score": s.get("overall_score", 0.0),
                "verdict": s.get("verdict", "PASS"),
                "final_verdict": s.get("final_verdict", "PASS"),
                "record_status": "VALID",
                "relevance_score": s.get("relevance_score", 0.0),
                "accuracy_score": s.get("accuracy_score", 0.0),
                "completeness_score": s.get("completeness_score", 0.0),
                "hallucination_risk": s.get("hallucination_risk", 0.0),
                "missing_elements": s.get("missing_elements", []),
                "unsupported_claims": s.get("unsupported_claims", []),
                "reasoning": s.get("reasoning", ""),
                "evidence": s.get("evidence", []),
                "better_answer": s.get("better_answer"),
                "raw_evaluation": s.get("raw_evaluation")
            })

        summary_base: Dict[str, Any] = {
            "total_records": len(all_records),
            "batch_id": "ALL",
            "dataset_name": "Stored Evaluation Repository"
        }
        analytics = compute_batch_analytics(all_records, summary_base)
        v_dist = analytics.get("verdict_distribution", {})
        kpis = {
            "total_evaluations": len(all_records),
            "pass_count": v_dist.get("PASS", {}).get("count", 0),
            "pass_rate": v_dist.get("PASS", {}).get("percentage", 0.0),
            "needs_improvement_count": v_dist.get("NEEDS IMPROVEMENT", {}).get("count", 0),
            "needs_improvement_rate": v_dist.get("NEEDS IMPROVEMENT", {}).get("percentage", 0.0),
            "fail_count": v_dist.get("FAIL", {}).get("count", 0),
            "fail_rate": v_dist.get("FAIL", {}).get("percentage", 0.0),
            "average_score": analytics.get("dimension_averages", {}).get("overall_score", 0.0),
            "hallucination_frequency": analytics.get("hallucination_stats", {}).get("hallucination_frequency_pct", 0.0)
        }

        return {
            "batches": history,
            "batch_summaries": history,
            "selected_batch_id": "ALL",
            "dataset_name": "All Batches & Stored Evaluations",
            "total_records": len(all_records),
            "records": all_records,
            "summary": summary_base,
            "analytics": analytics,
            "kpis": kpis,
            "dimensions": analytics.get("dimension_averages", {}),
            "dimension_averages": analytics.get("dimension_averages", {}),
            "score_distributions": analytics.get("score_distributions", {}),
            "verdict_distribution": v_dist,
            "hallucination_stats": analytics.get("hallucination_stats", {}),
            "completeness_stats": analytics.get("completeness_stats", {}),
            "recurring_issues": analytics.get("recurring_issues", []),
            "trends": trends,
            "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        }
