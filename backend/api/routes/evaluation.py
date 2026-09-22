"""
Evaluation and Retrieval API Routes.
Exposes POST /api/evaluate and GET /api/retrieval endpoints.
"""
import logging
import csv
import io
import json
from typing import List, Optional
from fastapi import APIRouter, Query, status, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse

from backend.api.schemas.evaluation import (
    EvaluationRequest,
    EvaluationResponse,
    RetrievedEvidenceItem,
    BatchItemResult,
    BatchSummary,
    BatchEvaluationResponse
)
from backend.agents.orchestrator import get_orchestrator
from backend.retrieval.retriever import retrieve_relevant_context

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Evaluation"])


@router.post(
    "/evaluate",
    response_model=EvaluationResponse,
    status_code=status.HTTP_200_OK,
    summary="Evaluate an AI Response against Question and Reference Ground Truth",
    description=(
        "Performs comprehensive evaluation across Relevance, Accuracy, Hallucination Risk, "
        "and Completeness. Retrieves relevant Knowledge Base evidence, computes semantic similarity, "
        "detects factual contradictions, generates a grounded Better Answer when needed, "
        "and delivers an overall verdict score with comparison metrics."
    )
)
def evaluate_response(request: EvaluationRequest) -> EvaluationResponse:
    """Evaluates the submitted AI response."""
    orchestrator = get_orchestrator()
    return orchestrator.evaluate(request)


@router.post(
    "/evaluate/stream",
    summary="Evaluate an AI Response with Truthful Real-Time Stage Streaming (SSE)",
    description="Streams genuine evaluation stage progression events (Relevance, Accuracy, Hallucination, Completeness, Verdict)."
)
def evaluate_response_stream(request: EvaluationRequest):
    """Streams evaluation stage progress events via Server-Sent Events (SSE)."""
    orchestrator = get_orchestrator()

    def event_generator():
        try:
            for event in orchestrator.evaluate_stream(request):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            logger.error("Streaming evaluation error: %s", str(e))
            err_payload = {"event": "ERROR", "error": str(e)}
            yield f"data: {json.dumps(err_payload)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post(
    "/batch/evaluate",
    response_model=BatchEvaluationResponse,
    status_code=status.HTTP_200_OK,
    summary="Batch Evaluate AI Responses from CSV Upload",
    description=(
        "Upload a CSV file containing 'question', 'ai_response', and mandatory 'reference_answer'. "
        "Each record is evaluated via the multi-agent orchestrator. Malformed or invalid rows "
        "are safely flagged without stopping the batch."
    )
)
async def evaluate_batch_csv(file: UploadFile = File(...)) -> BatchEvaluationResponse:
    """Evaluates a batch of responses uploaded as a CSV file."""
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file format: Please upload a valid CSV file (.csv)."
        )

    try:
        content_bytes = await file.read()
        content_str = content_bytes.decode("utf-8-sig", errors="replace")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not read uploaded CSV: {str(e)}"
        )

    reader = csv.DictReader(io.StringIO(content_str))
    if not reader.fieldnames:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSV file is empty or missing headers."
        )

    # Normalize headers
    field_map = {name.strip().lower().replace(" ", "_"): name for name in reader.fieldnames}
    q_col = field_map.get("question")
    ai_col = field_map.get("ai_response") or field_map.get("response") or field_map.get("answer")
    ref_col = field_map.get("reference_answer") or field_map.get("reference") or field_map.get("ground_truth")
    resp_id_col = field_map.get("response_id") or field_map.get("id")

    missing_cols = []
    if not q_col:
        missing_cols.append("question")
    if not ai_col:
        missing_cols.append("ai_response")
    if not ref_col:
        missing_cols.append("reference_answer")

    if missing_cols:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"CSV missing mandatory columns: {', '.join(missing_cols)}. Reference Answer is mandatory."
        )

    orchestrator = get_orchestrator()
    results: List[BatchItemResult] = []
    total_records = 0
    successful = 0
    invalid = 0
    failed = 0

    relevance_scores: List[float] = []
    accuracy_scores: List[float] = []
    hallucination_scores: List[float] = []
    completeness_scores: List[float] = []
    overall_scores: List[float] = []
    verdict_counts: dict = {"PASS": 0, "NEEDS IMPROVEMENT": 0, "FAIL": 0}
    high_hallucination_count = 0

    for idx, row in enumerate(reader, start=1):
        total_records += 1
        q_val = (row.get(q_col) or "").strip()
        ai_val = (row.get(ai_col) or "").strip()
        ref_val = (row.get(ref_col) or "").strip()
        resp_id = row.get(resp_id_col, f"row_{idx}")

        # Check required fields
        if not q_val:
            invalid += 1
            results.append(BatchItemResult(
                row_id=idx,
                response_id=resp_id,
                question=q_val,
                ai_response=ai_val,
                reference_answer=ref_val,
                status="INVALID",
                error_message=f"Row {idx}: Question is required."
            ))
            continue

        if not ai_val:
            invalid += 1
            results.append(BatchItemResult(
                row_id=idx,
                response_id=resp_id,
                question=q_val,
                ai_response=ai_val,
                reference_answer=ref_val,
                status="INVALID",
                error_message=f"Row {idx}: AI Response is required."
            ))
            continue

        if not ref_val:
            invalid += 1
            results.append(BatchItemResult(
                row_id=idx,
                response_id=resp_id,
                question=q_val,
                ai_response=ai_val,
                reference_answer=ref_val,
                status="INVALID",
                error_message=f"Row {idx}: Reference Answer is required."
            ))
            continue

        # Execute through orchestrator
        try:
            req = EvaluationRequest(
                question=q_val,
                ai_response=ai_val,
                reference_answer=ref_val
            )
            eval_res = orchestrator.evaluate(req)

            rel_sc = eval_res.evaluation.relevance.score
            acc_sc = eval_res.evaluation.accuracy.score
            hal_quality_sc = eval_res.evaluation.hallucination.score
            comp_sc = eval_res.evaluation.completeness.score
            ovr_sc = eval_res.evaluation.overall_score
            verd = eval_res.verdict_judge.final_verdict if eval_res.verdict_judge else eval_res.evaluation.verdict

            relevance_scores.append(rel_sc)
            accuracy_scores.append(acc_sc)
            hallucination_scores.append(hal_quality_sc)
            completeness_scores.append(comp_sc)
            overall_scores.append(ovr_sc)

            if verd in verdict_counts:
                verdict_counts[verd] += 1
            else:
                verdict_counts[verd] = 1

            if eval_res.evaluation.hallucination.percentage > 20.0:
                high_hallucination_count += 1

            successful += 1
            results.append(BatchItemResult(
                row_id=idx,
                response_id=resp_id,
                question=q_val,
                ai_response=ai_val,
                reference_answer=ref_val,
                status="SUCCESS",
                relevance_score=rel_sc,
                accuracy_score=acc_sc,
                hallucination_score=hal_quality_sc,
                completeness_score=comp_sc,
                overall_score=ovr_sc,
                verdict=verd,
                evaluation_detail=eval_res
            ))
        except Exception as e:
            failed += 1
            logger.error("Error evaluating batch row %d: %s", idx, str(e))
            results.append(BatchItemResult(
                row_id=idx,
                response_id=resp_id,
                question=q_val,
                ai_response=ai_val,
                reference_answer=ref_val,
                status="FAILED",
                error_message=f"Row {idx} execution failed: {str(e)}"
            ))

    def safe_avg(lst: List[float]) -> float:
        return round(sum(lst) / len(lst), 1) if lst else 0.0

    summary = BatchSummary(
        total_records=total_records,
        successful=successful,
        invalid=invalid,
        failed=failed,
        average_relevance=safe_avg(relevance_scores),
        average_accuracy=safe_avg(accuracy_scores),
        average_hallucination=safe_avg(hallucination_scores),
        average_completeness=safe_avg(completeness_scores),
        average_overall=safe_avg(overall_scores),
        verdict_counts=verdict_counts,
        hallucination_frequency=round((high_hallucination_count / successful * 100.0), 1) if successful > 0 else 0.0
    )

    return BatchEvaluationResponse(summary=summary, results=results)


@router.post(
    "/batch/evaluate/stream",
    summary="Batch Evaluate AI Responses with Real-Time Record Streaming (SSE)",
    description="Streams record-by-record progress events (Processed X/N) as each CSV row is evaluated."
)
async def evaluate_batch_csv_stream(file: UploadFile = File(...)):
    """Streams batch evaluation progress row-by-row via Server-Sent Events (SSE)."""
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file format: Please upload a valid CSV file (.csv)."
        )

    try:
        content_bytes = await file.read()
        content_str = content_bytes.decode("utf-8-sig", errors="replace")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not read uploaded CSV: {str(e)}"
        )

    reader = csv.DictReader(io.StringIO(content_str))
    if not reader.fieldnames:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSV file is empty or missing headers."
        )

    field_map = {name.strip().lower().replace(" ", "_"): name for name in reader.fieldnames}
    q_col = field_map.get("question")
    ai_col = field_map.get("ai_response") or field_map.get("response") or field_map.get("answer")
    ref_col = field_map.get("reference_answer") or field_map.get("reference") or field_map.get("ground_truth")
    resp_id_col = field_map.get("response_id") or field_map.get("id")

    missing_cols = []
    if not q_col:
        missing_cols.append("question")
    if not ai_col:
        missing_cols.append("ai_response")
    if not ref_col:
        missing_cols.append("reference_answer")

    if missing_cols:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"CSV missing mandatory columns: {', '.join(missing_cols)}. Reference Answer is mandatory."
        )

    rows = list(reader)
    total_records = len(rows)

    def batch_stream_generator():
        orchestrator = get_orchestrator()
        results = []
        successful = 0
        invalid = 0
        failed = 0
        relevance_scores = []
        accuracy_scores = []
        hallucination_scores = []
        completeness_scores = []
        overall_scores = []
        verdict_counts = {}
        high_hallucination_count = 0

        yield f"data: {json.dumps({'event': 'BATCH_STARTED', 'total_rows': total_records, 'processed': 0, 'percentage': 0.0})}\n\n"

        for idx, row in enumerate(rows, start=1):
            q_val = (row.get(q_col) or "").strip()
            ai_val = (row.get(ai_col) or "").strip()
            ref_val = (row.get(ref_col) or "").strip()
            resp_id = row.get(resp_id_col, f"row_{idx}")

            if not q_val:
                invalid += 1
                item = BatchItemResult(
                    row_id=idx,
                    response_id=resp_id,
                    question=q_val,
                    ai_response=ai_val,
                    reference_answer=ref_val,
                    status="INVALID",
                    error_message=f"Row {idx}: Question is required."
                )
                results.append(item)
                pct = round((idx / total_records) * 100, 1) if total_records > 0 else 100.0
                yield f"data: {json.dumps({'event': 'ROW_PROCESSED', 'row_id': idx, 'processed': idx, 'total_rows': total_records, 'percentage': pct, 'status': 'INVALID', 'item': item.model_dump()})}\n\n"
                continue

            if not ai_val:
                invalid += 1
                item = BatchItemResult(
                    row_id=idx,
                    response_id=resp_id,
                    question=q_val,
                    ai_response=ai_val,
                    reference_answer=ref_val,
                    status="INVALID",
                    error_message=f"Row {idx}: AI Response is required."
                )
                results.append(item)
                pct = round((idx / total_records) * 100, 1) if total_records > 0 else 100.0
                yield f"data: {json.dumps({'event': 'ROW_PROCESSED', 'row_id': idx, 'processed': idx, 'total_rows': total_records, 'percentage': pct, 'status': 'INVALID', 'item': item.model_dump()})}\n\n"
                continue

            if not ref_val:
                invalid += 1
                item = BatchItemResult(
                    row_id=idx,
                    response_id=resp_id,
                    question=q_val,
                    ai_response=ai_val,
                    reference_answer=ref_val,
                    status="INVALID",
                    error_message=f"Row {idx}: Reference Answer is required."
                )
                results.append(item)
                pct = round((idx / total_records) * 100, 1) if total_records > 0 else 100.0
                yield f"data: {json.dumps({'event': 'ROW_PROCESSED', 'row_id': idx, 'processed': idx, 'total_rows': total_records, 'percentage': pct, 'status': 'INVALID', 'item': item.model_dump()})}\n\n"
                continue

            try:
                req = EvaluationRequest(
                    question=q_val,
                    ai_response=ai_val,
                    reference_answer=ref_val
                )
                eval_res = orchestrator.evaluate(req)

                rel_sc = eval_res.evaluation.relevance.score
                acc_sc = eval_res.evaluation.accuracy.score
                hal_quality_sc = eval_res.evaluation.hallucination.score
                comp_sc = eval_res.evaluation.completeness.score
                ovr_sc = eval_res.evaluation.overall_score
                verd = eval_res.verdict_judge.final_verdict if eval_res.verdict_judge else eval_res.evaluation.verdict

                relevance_scores.append(rel_sc)
                accuracy_scores.append(acc_sc)
                hallucination_scores.append(hal_quality_sc)
                completeness_scores.append(comp_sc)
                overall_scores.append(ovr_sc)

                verdict_counts[verd] = verdict_counts.get(verd, 0) + 1
                if eval_res.evaluation.hallucination.percentage > 20.0:
                    high_hallucination_count += 1

                successful += 1
                item = BatchItemResult(
                    row_id=idx,
                    response_id=resp_id,
                    question=q_val,
                    ai_response=ai_val,
                    reference_answer=ref_val,
                    status="SUCCESS",
                    relevance_score=rel_sc,
                    accuracy_score=acc_sc,
                    hallucination_score=hal_quality_sc,
                    completeness_score=comp_sc,
                    overall_score=ovr_sc,
                    verdict=verd,
                    evaluation_detail=eval_res
                )
                results.append(item)
                pct = round((idx / total_records) * 100, 1) if total_records > 0 else 100.0
                yield f"data: {json.dumps({'event': 'ROW_PROCESSED', 'row_id': idx, 'processed': idx, 'total_rows': total_records, 'percentage': pct, 'status': 'SUCCESS', 'item': item.model_dump()})}\n\n"
            except Exception as e:
                failed += 1
                logger.error("Error evaluating batch row %d: %s", idx, str(e))
                item = BatchItemResult(
                    row_id=idx,
                    response_id=resp_id,
                    question=q_val,
                    ai_response=ai_val,
                    reference_answer=ref_val,
                    status="FAILED",
                    error_message=f"Row {idx} execution failed: {str(e)}"
                )
                results.append(item)
                pct = round((idx / total_records) * 100, 1) if total_records > 0 else 100.0
                yield f"data: {json.dumps({'event': 'ROW_PROCESSED', 'row_id': idx, 'processed': idx, 'total_rows': total_records, 'percentage': pct, 'status': 'FAILED', 'item': item.model_dump()})}\n\n"

        def safe_avg(lst: List[float]) -> float:
            return round(sum(lst) / len(lst), 1) if lst else 0.0

        summary = BatchSummary(
            total_records=total_records,
            successful=successful,
            invalid=invalid,
            failed=failed,
            average_relevance=safe_avg(relevance_scores),
            average_accuracy=safe_avg(accuracy_scores),
            average_hallucination=safe_avg(hallucination_scores),
            average_completeness=safe_avg(completeness_scores),
            average_overall=safe_avg(overall_scores),
            verdict_counts=verdict_counts,
            hallucination_frequency=round((high_hallucination_count / successful * 100.0), 1) if successful > 0 else 0.0
        )

        final_payload = {
            "event": "BATCH_COMPLETED",
            "processed": total_records,
            "total_rows": total_records,
            "percentage": 100.0,
            "summary": summary.model_dump(),
            "results": [r.model_dump() for r in results]
        }
        yield f"data: {json.dumps(final_payload)}\n\n"

    return StreamingResponse(batch_stream_generator(), media_type="text/event-stream")


@router.get(
    "/retrieval",
    response_model=List[RetrievedEvidenceItem],
    status_code=status.HTTP_200_OK,
    summary="Independent Semantic Retrieval from Knowledge Base",
    description="Query the indexed TruthfulQA and SQuAD knowledge base for top-k relevant evidence chunks."
)
def search_knowledge_base(
    question: str = Query(..., description="Query string to search in the knowledge base"),
    top_k: int = Query(3, ge=1, le=10, description="Number of evidence chunks to retrieve"),
    threshold: float = Query(0.1, ge=0.0, le=1.0, description="Minimum cosine similarity threshold")
) -> List[RetrievedEvidenceItem]:
    """Retrieves relevant context chunks independently."""
    return retrieve_relevant_context(question, top_k=top_k, threshold=threshold)

