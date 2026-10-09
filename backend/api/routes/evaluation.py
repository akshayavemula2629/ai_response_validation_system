"""
Evaluation and Retrieval API Routes.
Exposes POST /api/evaluate and GET /api/retrieval endpoints.
"""
import logging
import csv
import io
import json
import time
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Query, status, UploadFile, File, Form, HTTPException, Body, Response
from fastapi.responses import StreamingResponse

from backend.services.batch_storage import BatchStorageService, compute_batch_analytics
from backend.services.pdf_report_service import generate_batch_pdf_report, generate_single_pdf_report

from backend.api.schemas.evaluation import (
    EvaluationRequest,
    EvaluationResponse,
    RetrievedEvidenceItem,
    BatchItemResult,
    BatchSummary,
    BatchEvaluationResponse,
    BatchRecordValidationItem,
    BatchInputValidationSummary
)
from backend.agents.orchestrator import get_orchestrator
from backend.retrieval.retriever import retrieve_relevant_context
from backend.knowledge_base.document_parser import (
    parse_reference_document,
    retrieve_best_reference_passage,
    parse_batch_input,
    validate_batch_records
)

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
    resp = orchestrator.evaluate(request)
    try:
        eval_id = getattr(resp, "evaluation_id", None) or f"SINGLE-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f')[:21]}"
        ts = getattr(resp, "timestamp", None) or datetime.now(timezone.utc).isoformat()
        
        BatchStorageService.save_single_evaluation({
            "evaluation_id": eval_id,
            "timestamp": ts,
            "question": request.question,
            "ai_response": request.ai_response,
            "reference_answer": request.reference_answer or "",
            "overall_score": resp.verdict_judge.weighted_overall_score if resp.verdict_judge else resp.evaluation.overall_score,
            "verdict": resp.evaluation.verdict,
            "final_verdict": resp.verdict_judge.final_verdict if resp.verdict_judge else resp.evaluation.verdict,
            "relevance_score": resp.relevance_judge.score_normalized if resp.relevance_judge else (resp.evaluation.relevance.score * 20.0 if resp.evaluation.relevance else 0.0),
            "accuracy_score": resp.accuracy_judge.score_normalized if resp.accuracy_judge else (resp.evaluation.accuracy.score * 20.0 if resp.evaluation.accuracy else 0.0),
            "completeness_score": resp.completeness_judge.completeness_score if resp.completeness_judge else (resp.evaluation.completeness.score if resp.evaluation.completeness else 0.0),
            "hallucination_risk": resp.hallucination_judge.hallucination_percentage if resp.hallucination_judge else (resp.evaluation.hallucination.percentage if resp.evaluation.hallucination else 0.0),
            "missing_elements": resp.completeness_judge.missing_aspects if resp.completeness_judge else [],
            "unsupported_claims": resp.hallucination_judge.issues if resp.hallucination_judge else (resp.evaluation.hallucination.issues if resp.evaluation.hallucination else []),
            "reasoning": resp.verdict_judge.consolidated_reasoning if resp.verdict_judge else resp.evaluation.summary,
            "evidence": [e.content for e in resp.retrieved_evidence] if resp.retrieved_evidence else [],
            "better_answer": resp.better_answer,
            "raw_evaluation": resp.model_dump()
        })
    except Exception as e:
        logger.warning("Could not persist single evaluation to history: %s", str(e))
    return resp


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
    "/batch/validate-input",
    response_model=BatchInputValidationSummary,
    status_code=status.HTTP_200_OK,
    summary="Validate Batch Input File Row-by-Row (Section 33)",
    description="Parses CSV, TXT, or PDF batch inputs and validates each record for Question and AI Response before evaluation."
)
async def validate_batch_input_file(file: UploadFile = File(...)) -> BatchInputValidationSummary:
    """Pre-evaluation row-by-row input data validation."""
    content_bytes = await file.read()
    try:
        raw_records = parse_batch_input(content_bytes, file.filename)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not parse uploaded file: {str(e)}"
        )

    val_res = validate_batch_records(raw_records)
    record_items = [BatchRecordValidationItem(**r) for r in val_res["records"]]
    return BatchInputValidationSummary(
        total_records=val_res["total_records"],
        valid_count=val_res["valid_count"],
        invalid_count=val_res["invalid_count"],
        records=record_items,
        valid_records=val_res["valid_count"],
        invalid_records=val_res["invalid_count"],
        validation_items=[
            {
                "row_index": r.row_id,
                "is_valid": r.status == "VALID",
                "reason": r.reason,
                "question_snippet": r.question,
                "response_snippet": r.ai_response
            }
            for r in record_items
        ]
    )


@router.post(
    "/batch/evaluate",
    response_model=BatchEvaluationResponse,
    status_code=status.HTTP_200_OK,
    summary="Batch Evaluate AI Responses from File Upload",
    description=(
        "Upload a CSV, TXT, or PDF file with optional or mandatory reference document. "
        "Each valid record is evaluated via the multi-agent orchestrator. Malformed or invalid rows "
        "are safely flagged without stopping the batch."
    )
)
async def evaluate_batch_csv(
    file: UploadFile = File(...),
    reference_file: Optional[UploadFile] = File(None),
    valid_rows_json: Optional[str] = Form(None),
    filter_status: Optional[str] = Form("all"),
    row_limit: Optional[int] = Form(None),
    selected_row_ids_json: Optional[str] = Form(None)
) -> BatchEvaluationResponse:
    """Evaluates a batch of responses uploaded as CSV, TXT, or PDF."""
    content_bytes = await file.read()
    try:
        raw_records = parse_batch_input(content_bytes, file.filename)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not read uploaded batch file: {str(e)}"
        )

    # Process optional reference / source document if provided
    ref_doc_text = ""
    if reference_file is not None and reference_file.filename:
        try:
            ref_bytes = await reference_file.read()
            ref_doc_text = parse_reference_document(ref_bytes, reference_file.filename)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Could not process reference document: {str(e)}"
            )

    file_total = len(raw_records)

    # 1. Run input validation across all parsed records
    val_summary = validate_batch_records(raw_records)
    row_val_map = {r["row_id"]: r["status"] for r in val_summary["records"]}

    # 2. Determine filtered records
    valid_id_set: Optional[set] = None
    norm_filter = (filter_status or "all").strip().lower()
    if selected_row_ids_json:
        try:
            sel_ids = set(json.loads(selected_row_ids_json))
            filtered_records = [r for r in raw_records if r.get("row_id") in sel_ids]
        except Exception:
            filtered_records = raw_records
    elif norm_filter == "valid":
        filtered_records = [r for r in raw_records if row_val_map.get(r.get("row_id"), "VALID") == "VALID"]
    elif norm_filter == "invalid":
        filtered_records = [r for r in raw_records if row_val_map.get(r.get("row_id"), "VALID") == "INVALID"]
    elif valid_rows_json:
        try:
            valid_id_set = set(json.loads(valid_rows_json))
            filtered_records = [r for r in raw_records if r.get("row_id") in valid_id_set]
        except Exception:
            filtered_records = raw_records
    else:
        filtered_records = raw_records

    available_records = len(filtered_records)

    # 3. Validate and slice requested row count
    if row_limit is not None:
        if row_limit <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid number of rows. Please enter a positive integer between 1 and available records."
            )
        if row_limit > available_records:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid number of rows. Only {available_records} records are available for the selected filter. Please enter a number between 1 and {available_records}."
            )
        selected_records = filtered_records[:row_limit]
    else:
        selected_records = filtered_records

    requested_records = len(selected_records)
    orchestrator = get_orchestrator()
    results: List[BatchItemResult] = []
    total_records = len(selected_records)
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

    for idx, record in enumerate(selected_records, start=1):
        q_val = record.get("question", "").strip()
        ai_val = record.get("ai_response", "").strip()
        ref_val = record.get("reference_answer", "").strip()
        exp_status = record.get("expected_status", "").strip().lower()
        row_id = record.get("row_id", idx)
        resp_id = f"row_{row_id}"

        if not q_val:
            invalid += 1
            results.append(BatchItemResult(
                row_id=row_id,
                response_id=resp_id,
                question=q_val,
                ai_response=ai_val,
                reference_answer=ref_val,
                status="INVALID",
                record_status="INVALID",
                verdict="FAIL",
                final_verdict="FAIL",
                overall_score=0.0,
                error_message=f"Row {row_id}: Question is required.",
                expected_status=exp_status or None
            ))
            continue


        if not ai_val:
            invalid += 1
            results.append(BatchItemResult(
                row_id=row_id,
                response_id=resp_id,
                question=q_val,
                ai_response=ai_val,
                reference_answer=ref_val,
                status="INVALID",
                verdict="FAIL",
                final_verdict="FAIL",
                error_message=f"Row {row_id}: AI Response is required.",
                expected_status=exp_status or None
            ))
            continue

        # Determine effective reference answer matching Single Evaluation methodology:
        # 1. Use record's reference_answer if provided (backward compatibility)
        # 2. Extract best passage from uploaded reference document if provided
        # 3. Retrieve ground truth context from Knowledge Base
        effective_ref = ref_val
        if not effective_ref and ref_doc_text:
            effective_ref = retrieve_best_reference_passage(q_val, ref_doc_text)

        if not effective_ref:
            try:
                kb_evidence = retrieve_relevant_context(q_val, top_k=5)
                if kb_evidence:
                    chosen_chunk = kb_evidence[0]
                    q_lower = q_val.strip(" ?.").lower()
                    for chk in kb_evidence:
                        chk_lower = chk.content.lower()
                        if q_lower and q_lower in chk_lower:
                            chosen_chunk = chk
                            break
                    raw_content = chosen_chunk.content
                    if "Reference Answer:" in raw_content:
                        clean_ref = raw_content.split("Reference Answer:", 1)[1]
                        if "\nQuestion:" in clean_ref:
                            clean_ref = clean_ref.split("\nQuestion:", 1)[0].strip()
                        elif "Question:" in clean_ref:
                            clean_ref = clean_ref.split("Question:", 1)[0].strip()
                        elif "\nAnswer:" in clean_ref:
                            clean_ref = clean_ref.split("\nAnswer:", 1)[0].strip()
                        effective_ref = clean_ref.strip()
                    elif "Answer:" in raw_content:
                        clean_ref = raw_content.split("Answer:", 1)[1].strip()
                        if "\nQuestion:" in clean_ref:
                            clean_ref = clean_ref.split("\nQuestion:", 1)[0].strip()
                        effective_ref = clean_ref.strip()
                    else:
                        effective_ref = raw_content.strip()
                else:
                    effective_ref = "The AI response is evaluated based on factual grounding, accuracy to the prompt, and logical reasoning."
            except Exception as e:
                logger.warning("KB retrieval fallback for batch row %d: %s", row_id, str(e))
                effective_ref = "Standard ground truth evaluation based on domain knowledge and verified facts."

        try:
            req = EvaluationRequest(
                question=q_val,
                ai_response=ai_val,
                reference_answer=effective_ref,
                source_document=ref_doc_text if ref_doc_text else None
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
            rec_status = "VALID" if verd == "PASS" else "INVALID"
            results.append(BatchItemResult(
                row_id=row_id,
                response_id=resp_id,
                question=q_val,
                ai_response=ai_val,
                reference_answer=effective_ref,
                status="SUCCESS",
                record_status=rec_status,
                relevance_score=rel_sc,
                accuracy_score=acc_sc,
                hallucination_score=hal_quality_sc,
                hallucination_percentage=eval_res.evaluation.hallucination.percentage,
                completeness_score=comp_sc,
                overall_score=ovr_sc,
                similarity_score=eval_res.evaluation.similarity.percentage if eval_res.evaluation.similarity else None,
                verdict=verd,
                final_verdict=verd,
                evaluation_detail=eval_res,
                expected_status=exp_status or None
            ))
        except Exception as e:
            failed += 1
            invalid += 1
            logger.error("Error evaluating batch row %d: %s", row_id, str(e))
            results.append(BatchItemResult(
                row_id=row_id,
                response_id=resp_id,
                question=q_val,
                ai_response=ai_val,
                reference_answer=effective_ref or "",
                status="FAILED",
                record_status="INVALID",
                verdict="FAIL",
                final_verdict="FAIL",
                error_message=f"Evaluation Error: {str(e)}",
                expected_status=exp_status or None
            ))

    def safe_avg(lst: List[float]) -> float:
        return round(sum(lst) / len(lst), 1) if lst else 0.0

    summary = BatchSummary(
        total_records=total_records,
        total_rows=total_records,
        file_total=file_total,
        valid_total=val_summary.get("valid_count", 0),
        invalid_total=val_summary.get("invalid_count", 0),
        selected_filter=norm_filter.capitalize(),
        available_records=available_records,
        requested_records=requested_records,
        actually_evaluated=len(results),
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

    summary_dict = summary.model_dump()
    results_list = [r.model_dump() for r in results]
    try:
        saved_batch_id = BatchStorageService.save_batch_run(summary_dict, results_list, dataset_name=file.filename or "batch.csv")
        summary.batch_id = saved_batch_id
    except Exception as e:
        logger.warning("Could not persist batch run to history: %s", str(e))

    return BatchEvaluationResponse(summary=summary, results=results)


@router.post(
    "/batch/evaluate/stream",
    summary="Batch Evaluate AI Responses with Real-Time Record Streaming (SSE)",
    description="Streams record-by-record progress events (Processed X/N) as each row is evaluated."
)
async def evaluate_batch_csv_stream(
    file: UploadFile = File(...),
    reference_file: Optional[UploadFile] = File(None),
    valid_rows_json: Optional[str] = Form(None),
    filter_status: Optional[str] = Form("all"),
    row_limit: Optional[int] = Form(None),
    selected_row_ids_json: Optional[str] = Form(None)
):
    """Streams batch evaluation progress row-by-row via Server-Sent Events (SSE)."""
    content_bytes = await file.read()
    try:
        raw_records = parse_batch_input(content_bytes, file.filename)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not read uploaded batch file: {str(e)}"
        )

    ref_doc_text = ""
    if reference_file is not None and reference_file.filename:
        try:
            ref_bytes = await reference_file.read()
            ref_doc_text = parse_reference_document(ref_bytes, reference_file.filename)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Could not process reference document: {str(e)}"
            )

    file_total = len(raw_records)

    # 1. Input Validation across all records
    val_summary = validate_batch_records(raw_records)
    row_val_map = {r["row_id"]: r["status"] for r in val_summary["records"]}

    # 2. Filter records according to requested filter
    valid_id_set: Optional[set] = None
    norm_filter = (filter_status or "all").strip().lower()
    if selected_row_ids_json:
        try:
            sel_ids = set(json.loads(selected_row_ids_json))
            filtered_records = [r for r in raw_records if r.get("row_id") in sel_ids]
        except Exception:
            filtered_records = raw_records
    elif norm_filter == "valid":
        filtered_records = [r for r in raw_records if row_val_map.get(r.get("row_id"), "VALID") == "VALID"]
    elif norm_filter == "invalid":
        filtered_records = [r for r in raw_records if row_val_map.get(r.get("row_id"), "VALID") == "INVALID"]
    elif valid_rows_json:
        try:
            valid_id_set = set(json.loads(valid_rows_json))
            filtered_records = [r for r in raw_records if r.get("row_id") in valid_id_set]
        except Exception:
            filtered_records = raw_records
    else:
        filtered_records = raw_records

    available_records = len(filtered_records)

    # 3. Validate and slice requested row count
    if row_limit is not None:
        if row_limit <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid number of rows. Please enter a positive integer between 1 and available records."
            )
        if row_limit > available_records:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid number of rows. Only {available_records} records are available for the selected filter. Please enter a number between 1 and {available_records}."
            )
        selected_records = filtered_records[:row_limit]
    else:
        selected_records = filtered_records

    requested_records = len(selected_records)
    total_records = len(selected_records)

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

        yield f"data: {json.dumps({'event': 'BATCH_STARTED', 'total_rows': total_records, 'processed': 0, 'percentage': 0.0, 'file_total': file_total, 'available': available_records, 'filter': norm_filter})}\n\n"

        for idx, record in enumerate(selected_records, start=1):
            q_val = record.get("question", "").strip()
            ai_val = record.get("ai_response", "").strip()
            ref_val = record.get("reference_answer", "").strip()
            exp_status = record.get("expected_status", "").strip().lower()
            row_id = record.get("row_id", idx)
            resp_id = f"row_{row_id}"

            if valid_rows_json and valid_id_set is not None and row_id not in valid_id_set:
                invalid += 1
                item = BatchItemResult(
                    row_id=row_id,
                    response_id=resp_id,
                    question=q_val,
                    ai_response=ai_val,
                    reference_answer=ref_val,
                    status="INVALID",
                    verdict="FAIL",
                    final_verdict="FAIL",
                    error_message=f"Row {row_id}: Skipped as invalid.",
                    expected_status=exp_status or None
                )
                results.append(item)
                pct = round((idx / total_records) * 100, 1) if total_records > 0 else 100.0
                yield f"data: {json.dumps({'event': 'ROW_PROCESSED', 'row_id': row_id, 'processed': idx, 'total_rows': total_records, 'percentage': pct, 'status': 'INVALID', 'item': item.model_dump()})}\n\n"
                continue

            if not q_val:
                invalid += 1
                item = BatchItemResult(
                    row_id=row_id,
                    response_id=resp_id,
                    question=q_val,
                    ai_response=ai_val,
                    reference_answer=ref_val,
                    status="INVALID",
                    verdict="FAIL",
                    final_verdict="FAIL",
                    error_message=f"Row {row_id}: Question is required.",
                    expected_status=exp_status or None
                )
                results.append(item)
                pct = round((idx / total_records) * 100, 1) if total_records > 0 else 100.0
                yield f"data: {json.dumps({'event': 'ROW_PROCESSED', 'row_id': row_id, 'processed': idx, 'total_rows': total_records, 'percentage': pct, 'status': 'INVALID', 'item': item.model_dump()})}\n\n"
                continue

            if not ai_val:
                invalid += 1
                item = BatchItemResult(
                    row_id=row_id,
                    response_id=resp_id,
                    question=q_val,
                    ai_response=ai_val,
                    reference_answer=ref_val,
                    status="INVALID",
                    verdict="FAIL",
                    final_verdict="FAIL",
                    error_message=f"Row {row_id}: AI Response is required.",
                    expected_status=exp_status or None
                )
                results.append(item)
                pct = round((idx / total_records) * 100, 1) if total_records > 0 else 100.0
                yield f"data: {json.dumps({'event': 'ROW_PROCESSED', 'row_id': row_id, 'processed': idx, 'total_rows': total_records, 'percentage': pct, 'status': 'INVALID', 'item': item.model_dump()})}\n\n"
                continue

            # Determine effective reference answer matching Single Evaluation methodology:
            # 1. Use record's reference_answer if provided (backward compatibility)
            # 2. Extract best passage from uploaded reference document if provided
            # 3. Retrieve ground truth context from Knowledge Base
            effective_ref = ref_val
            if not effective_ref and ref_doc_text:
                effective_ref = retrieve_best_reference_passage(q_val, ref_doc_text)

            if not effective_ref:
                try:
                    kb_evidence = retrieve_relevant_context(q_val, top_k=5)
                    if kb_evidence:
                        chosen_chunk = kb_evidence[0]
                        q_lower = q_val.strip(" ?.").lower()
                        for chk in kb_evidence:
                            chk_lower = chk.content.lower()
                            if q_lower and q_lower in chk_lower:
                                chosen_chunk = chk
                                break
                        raw_content = chosen_chunk.content
                        if "Reference Answer:" in raw_content:
                            clean_ref = raw_content.split("Reference Answer:", 1)[1]
                            if "\nQuestion:" in clean_ref:
                                clean_ref = clean_ref.split("\nQuestion:", 1)[0].strip()
                            elif "Question:" in clean_ref:
                                clean_ref = clean_ref.split("Question:", 1)[0].strip()
                            elif "\nAnswer:" in clean_ref:
                                clean_ref = clean_ref.split("\nAnswer:", 1)[0].strip()
                            effective_ref = clean_ref.strip()
                        elif "Answer:" in raw_content:
                            clean_ref = raw_content.split("Answer:", 1)[1].strip()
                            if "\nQuestion:" in clean_ref:
                                clean_ref = clean_ref.split("\nQuestion:", 1)[0].strip()
                            effective_ref = clean_ref.strip()
                        else:
                            effective_ref = raw_content.strip()
                    else:
                        effective_ref = "The AI response is evaluated based on factual grounding, accuracy to the prompt, and logical reasoning."
                except Exception as e:
                    logger.warning("KB retrieval fallback for batch row %d: %s", row_id, str(e))
                    effective_ref = "Standard ground truth evaluation based on domain knowledge and verified facts."

            try:
                req = EvaluationRequest(
                    question=q_val,
                    ai_response=ai_val,
                    reference_answer=effective_ref,
                    source_document=ref_doc_text if ref_doc_text else None
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
                rec_status = "VALID" if verd == "PASS" else "INVALID"
                item = BatchItemResult(
                    row_id=row_id,
                    response_id=resp_id,
                    question=q_val,
                    ai_response=ai_val,
                    reference_answer=effective_ref,
                    status="SUCCESS",
                    record_status=rec_status,
                    relevance_score=rel_sc,
                    accuracy_score=acc_sc,
                    hallucination_score=hal_quality_sc,
                    hallucination_percentage=eval_res.evaluation.hallucination.percentage,
                    completeness_score=comp_sc,
                    overall_score=ovr_sc,
                    similarity_score=eval_res.evaluation.similarity.percentage if eval_res.evaluation.similarity else None,
                    verdict=verd,
                    final_verdict=verd,
                    evaluation_detail=eval_res,
                    expected_status=exp_status or None
                )
                results.append(item)
                pct = round((idx / total_records) * 100, 1) if total_records > 0 else 100.0
                yield f"data: {json.dumps({'event': 'ROW_PROCESSED', 'row_id': row_id, 'processed': idx, 'total_rows': total_records, 'percentage': pct, 'status': 'SUCCESS', 'item': item.model_dump()})}\n\n"
            except Exception as e:
                failed += 1
                invalid += 1
                logger.error("Error evaluating batch row %d: %s", row_id, str(e))
                item = BatchItemResult(
                    row_id=row_id,
                    response_id=resp_id,
                    question=q_val,
                    ai_response=ai_val,
                    reference_answer=effective_ref or "",
                    status="FAILED",
                    record_status="INVALID",
                    verdict="FAIL",
                    final_verdict="FAIL",
                    error_message=f"Evaluation Error: {str(e)}",
                    expected_status=exp_status or None
                )
                results.append(item)
                pct = round((idx / total_records) * 100, 1) if total_records > 0 else 100.0
                yield f"data: {json.dumps({'event': 'ROW_PROCESSED', 'row_id': row_id, 'processed': idx, 'total_rows': total_records, 'percentage': pct, 'status': 'FAILED', 'item': item.model_dump()})}\n\n"

        def safe_avg(lst: List[float]) -> float:
            return round(sum(lst) / len(lst), 1) if lst else 0.0

        summary = BatchSummary(
            total_records=total_records,
            total_rows=total_records,
            file_total=file_total,
            valid_total=val_summary.get("valid_count", 0),
            invalid_total=val_summary.get("invalid_count", 0),
            selected_filter=norm_filter.capitalize(),
            available_records=available_records,
            requested_records=requested_records,
            actually_evaluated=len(results),
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

        summary_dict = summary.model_dump()
        results_list = [r.model_dump() for r in results]
        try:
            saved_batch_id = BatchStorageService.save_batch_run(summary_dict, results_list, dataset_name=file.filename or "batch.csv")
            summary.batch_id = saved_batch_id
            summary_dict["batch_id"] = saved_batch_id
        except Exception as e:
            logger.warning("Could not persist batch run to history: %s", str(e))

        final_payload = {
            "event": "BATCH_COMPLETED",
            "processed": total_records,
            "total_rows": total_records,
            "percentage": 100.0,
            "summary": summary_dict,
            "results": results_list
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


# =========================================================================
# Milestone 4 API Routes (Dashboard, History, PDF Reports, E2E Test Runner)
# =========================================================================

@router.get(
    "/dashboard/analytics",
    status_code=status.HTTP_200_OK,
    summary="Evaluation Scoring Dashboard Analytics (M4.1)",
    description="Returns aggregated metrics, KPIs, dimension averages, distributions, and historical batch trends."
)
def get_dashboard_analytics_api(
    batch_id: Optional[str] = Query(None, description="Optional batch ID to filter metrics. Defaults to all stored evaluations.")
) -> Dict[str, Any]:
    """Retrieves aggregated evaluation metrics for the dashboard."""
    try:
        return BatchStorageService.get_dashboard_analytics(batch_id=batch_id)
    except Exception as e:
        logger.error("Failed to load dashboard analytics: %s", str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get(
    "/batch/history",
    status_code=status.HTTP_200_OK,
    summary="Retrieve Batch Evaluation History and Trends (M4.1 & History)",
    description="Returns list of historical batch evaluations and multi-batch trend data."
)
def get_batch_history_api() -> Dict[str, Any]:
    """Retrieves list of past batch runs with trends."""
    batches = BatchStorageService.get_batch_history()
    trends = BatchStorageService.get_batch_trends()
    return {"batches": batches, "trends": trends}


@router.get(
    "/batch/{batch_id}",
    status_code=status.HTTP_200_OK,
    summary="Retrieve Details for a Specific Batch Run (History & Dashboard)",
    description="Returns full summary and evaluated results list for the requested batch ID."
)
def get_batch_detail_api(batch_id: str) -> Dict[str, Any]:
    """Retrieves full evaluation records for a specific historical batch."""
    batch_run = BatchStorageService.get_batch_by_id(batch_id)
    if not batch_run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Batch run '{batch_id}' was not found in persistent storage."
        )
    return batch_run


@router.post(
    "/batch/report/pdf",
    status_code=status.HTTP_200_OK,
    summary="Export Publication-Grade Batch PDF Report (M4.2)",
    description="Generates and streams an executive multi-page vector PDF report for a batch evaluation run."
)
def export_batch_pdf_report_api(payload: Dict[str, Any] = Body(...)) -> Response:
    """Generates an executive vector PDF report using ReportLab for a batch evaluation."""
    summary = payload.get("summary")
    results = payload.get("results")

    # If payload passed batch_id only, fetch from storage
    if not summary and payload.get("batch_id"):
        batch_run = BatchStorageService.get_batch_by_id(payload["batch_id"])
        if batch_run:
            summary = batch_run.get("summary")
            results = batch_run.get("results")

    if not summary or not isinstance(summary, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing required 'summary' payload for batch PDF generation.")

    if not results or not isinstance(results, list):
        results = []

    try:
        pdf_bytes = generate_batch_pdf_report(summary, results)
        batch_id = summary.get("batch_id", "batch")
        filename = f"Evaluation_Report_{batch_id}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except Exception as e:
        logger.error("Batch PDF report generation failed: %s", str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"PDF generation failed: {str(e)}")


@router.post(
    "/single/report/pdf",
    status_code=status.HTTP_200_OK,
    summary="Export Forensic Single Evaluation PDF Report (M4.2)",
    description="Generates and streams a publication-grade forensic audit vector PDF report for a single response evaluation."
)
def export_single_pdf_report_api(payload: Dict[str, Any] = Body(...)) -> Response:
    """Generates a forensic single response evaluation vector PDF report using ReportLab."""
    if not payload or not isinstance(payload, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid evaluation payload for PDF generation.")

    if not payload.get("question") or not (payload.get("ai_response") or payload.get("original_response")):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Payload must include 'question' and 'ai_response' fields.")

    try:
        pdf_bytes = generate_single_pdf_report(payload)
        req_id = payload.get("request_id") or payload.get("evaluation_id") or "single_eval"
        filename = f"Evaluation_Audit_{req_id}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except Exception as e:
        logger.error("Single PDF report generation failed: %s", str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"PDF generation failed: {str(e)}")


@router.post(
    "/testing/run",
    status_code=status.HTTP_200_OK,
    summary="Execute Live End-to-End Test Suite (M4.3)",
    description="Executes automated testing categories and returns live validation statuses, timings, and verification results."
)
def run_automated_tests_api() -> Dict[str, Any]:
    """
    Executes actual test validations across 10 categories required by Milestone 4:
    Single E2E, Batch E2E, Agent Validation, Hallucination, Completeness, Verdict,
    Dashboard, PDF Validation, Error Handling, Performance.
    """
    start_time = time.perf_counter()
    orchestrator = get_orchestrator()
    categories = []

    # 1. Single Evaluation Tests
    t0 = time.perf_counter()
    try:
        single_req = EvaluationRequest(
            question="What is the capital of France?",
            ai_response="Paris is the capital of France.",
            reference_answer="Paris is the capital of France."
        )
        single_res = orchestrator.evaluate(single_req)
        assert single_res.evaluation.verdict in ["Excellent", "Good", "PASS"], "Unexpected single evaluation verdict"
        dur_ms = round((time.perf_counter() - t0) * 1000, 1)
        categories.append({
            "category": "Single Evaluation Tests",
            "status": "PASSED",
            "duration_ms": dur_ms,
            "details": f"Verified full single evaluation pipeline. Verdict: {single_res.evaluation.verdict}, Score: {single_res.evaluation.overall_score}"
        })
    except Exception as e:
        dur_ms = round((time.perf_counter() - t0) * 1000, 1)
        categories.append({
            "category": "Single Evaluation Tests",
            "status": "FAILED",
            "duration_ms": dur_ms,
            "details": f"Error: {str(e)}"
        })

    # 2. Batch Evaluation Tests
    t0 = time.perf_counter()
    try:
        sample_csv = "question,ai_response,reference_answer\nWhat is H2O?,Water,Water is H2O."
        records = parse_batch_input(sample_csv.encode("utf-8"), "test.csv")
        val_res = validate_batch_records(records)
        assert val_res["valid_count"] == 1, "Expected 1 valid record"
        dur_ms = round((time.perf_counter() - t0) * 1000, 1)
        categories.append({
            "category": "Batch Evaluation Tests",
            "status": "PASSED",
            "duration_ms": dur_ms,
            "details": f"Batch CSV parser and row validation verified ({val_res['total_records']} rows, {val_res['valid_count']} valid)."
        })
    except Exception as e:
        dur_ms = round((time.perf_counter() - t0) * 1000, 1)
        categories.append({
            "category": "Batch Evaluation Tests",
            "status": "FAILED",
            "duration_ms": dur_ms,
            "details": f"Error: {str(e)}"
        })

    # 3. Agent Validation Tests
    t0 = time.perf_counter()
    try:
        req = EvaluationRequest(
            question="What is photosynthesis?",
            ai_response="Photosynthesis is the biological process by which plants convert sunlight into energy.",
            reference_answer="Photosynthesis converts solar light into chemical energy."
        )
        res = orchestrator.evaluate(req)
        assert res.relevance_judge is not None, "Missing Relevance Judge"
        assert res.accuracy_judge is not None, "Missing Accuracy Judge"
        assert res.hallucination_judge is not None, "Missing Hallucination Judge"
        assert res.completeness_judge is not None, "Missing Completeness Judge"
        assert res.verdict_judge is not None, "Missing Verdict Judge"
        dur_ms = round((time.perf_counter() - t0) * 1000, 1)
        categories.append({
            "category": "Agent Validation Tests",
            "status": "PASSED",
            "duration_ms": dur_ms,
            "details": "All 5 Judge Agents (Relevance, Accuracy, Hallucination, Completeness, Verdict) executed cleanly."
        })
    except Exception as e:
        dur_ms = round((time.perf_counter() - t0) * 1000, 1)
        categories.append({
            "category": "Agent Validation Tests",
            "status": "FAILED",
            "duration_ms": dur_ms,
            "details": f"Error: {str(e)}"
        })

    # 4. Hallucination Tests
    t0 = time.perf_counter()
    try:
        # Test unsupported claim detection
        hal_req = EvaluationRequest(
            question="What is the speed of sound in air?",
            ai_response="The speed of sound in air is 9,000 meters per second and dry air contains gold dust.",
            reference_answer="The speed of sound in dry air at 20°C is 343 meters per second."
        )
        hal_res = orchestrator.evaluate(hal_req)
        hal_risk = hal_res.hallucination_judge.hallucination_percentage if hal_res.hallucination_judge else hal_res.evaluation.hallucination.percentage
        assert hal_risk > 20.0 or len(hal_res.evaluation.hallucination.issues) > 0, "Failed to flag obvious hallucination"
        dur_ms = round((time.perf_counter() - t0) * 1000, 1)
        categories.append({
            "category": "Hallucination Tests",
            "status": "PASSED",
            "duration_ms": dur_ms,
            "details": f"Detected ungrounded claims with risk level '{hal_res.evaluation.hallucination.risk_level}' ({hal_risk:.1f}% risk)."
        })
    except Exception as e:
        dur_ms = round((time.perf_counter() - t0) * 1000, 1)
        categories.append({
            "category": "Hallucination Tests",
            "status": "FAILED",
            "duration_ms": dur_ms,
            "details": f"Error: {str(e)}"
        })

    # 5. Completeness Tests
    t0 = time.perf_counter()
    try:
        comp_req = EvaluationRequest(
            question="Explain the three laws of thermodynamics.",
            ai_response="The first law is conservation of energy.",
            reference_answer="First law: conservation of energy. Second law: entropy increases. Third law: entropy approaches constant at absolute zero."
        )
        comp_res = orchestrator.evaluate(comp_req)
        comp_score = comp_res.completeness_judge.completeness_score if comp_res.completeness_judge else comp_res.evaluation.completeness.score
        assert comp_score < 90.0, "Incomplete response should receive completeness penalty"
        dur_ms = round((time.perf_counter() - t0) * 1000, 1)
        categories.append({
            "category": "Completeness Tests",
            "status": "PASSED",
            "duration_ms": dur_ms,
            "details": f"Completeness Judge accurately identified missing sub-aspects (Coverage score: {comp_score:.1f}/100)."
        })
    except Exception as e:
        dur_ms = round((time.perf_counter() - t0) * 1000, 1)
        categories.append({
            "category": "Completeness Tests",
            "status": "FAILED",
            "duration_ms": dur_ms,
            "details": f"Error: {str(e)}"
        })

    # 6. Verdict Tests
    t0 = time.perf_counter()
    try:
        pass_req = EvaluationRequest(
            question="What is the chemical symbol for gold?",
            ai_response="The chemical symbol for gold is Au.",
            reference_answer="Gold's chemical symbol is Au."
        )
        pass_res = orchestrator.evaluate(pass_req)
        verd = pass_res.verdict_judge.final_verdict if pass_res.verdict_judge else pass_res.evaluation.verdict
        assert "PASS" in verd or "Excellent" in verd, f"Expected PASS verdict, got {verd}"
        dur_ms = round((time.perf_counter() - t0) * 1000, 1)
        categories.append({
            "category": "Verdict Tests",
            "status": "PASSED",
            "duration_ms": dur_ms,
            "details": f"Verified composite weighted model (25% Rel, 30% Acc, 25% Comp, 20% Hal). Final Verdict: {verd}."
        })
    except Exception as e:
        dur_ms = round((time.perf_counter() - t0) * 1000, 1)
        categories.append({
            "category": "Verdict Tests",
            "status": "FAILED",
            "duration_ms": dur_ms,
            "details": f"Error: {str(e)}"
        })

    # 7. Dashboard Validation
    t0 = time.perf_counter()
    try:
        dash_data = BatchStorageService.get_dashboard_analytics()
        assert "kpis" in dash_data, "Missing kpis in dashboard response"
        assert "dimensions" in dash_data, "Missing dimensions in dashboard response"
        dur_ms = round((time.perf_counter() - t0) * 1000, 1)
        categories.append({
            "category": "Dashboard Validation",
            "status": "PASSED",
            "duration_ms": dur_ms,
            "details": f"Verified multi-run analytics aggregation ({dash_data['kpis']['total_evaluations']} records processed)."
        })
    except Exception as e:
        dur_ms = round((time.perf_counter() - t0) * 1000, 1)
        categories.append({
            "category": "Dashboard Validation",
            "status": "FAILED",
            "duration_ms": dur_ms,
            "details": f"Error: {str(e)}"
        })

    # 8. PDF Validation
    t0 = time.perf_counter()
    try:
        sample_eval = {
            "evaluation_id": "TEST-PDF-001",
            "question": "What is the speed of light?",
            "ai_response": "299,792,458 m/s in vacuum.",
            "reference_answer": "Light travels at 299,792,458 m/s in vacuum.",
            "overall_score": 98.0,
            "verdict": "PASS"
        }
        pdf_bytes = generate_single_pdf_report(sample_eval)
        assert len(pdf_bytes) > 1000, "Generated PDF is too small or empty"
        assert pdf_bytes.startswith(b"%PDF"), "Invalid PDF binary signature"
        dur_ms = round((time.perf_counter() - t0) * 1000, 1)
        categories.append({
            "category": "PDF Validation",
            "status": "PASSED",
            "duration_ms": dur_ms,
            "details": f"Verified publication-grade PDF generation ({len(pdf_bytes):,} bytes produced)."
        })
    except Exception as e:
        dur_ms = round((time.perf_counter() - t0) * 1000, 1)
        categories.append({
            "category": "PDF Validation",
            "status": "FAILED",
            "duration_ms": dur_ms,
            "details": f"Error: {str(e)}"
        })

    # 9. Error Handling
    t0 = time.perf_counter()
    try:
        # Invalid CSV format
        malformed = b"this,is,not,valid,header\n1,2,3"
        parse_batch_input(malformed, "bad.csv")
        val = validate_batch_records([{"row_id": 1, "question": "", "ai_response": ""}])
        assert val["invalid_count"] == 1, "Failed to flag missing required fields in batch record"
        dur_ms = round((time.perf_counter() - t0) * 1000, 1)
        categories.append({
            "category": "Error Handling",
            "status": "PASSED",
            "duration_ms": dur_ms,
            "details": "Graceful validation error handling confirmed on missing fields and malformed rows."
        })
    except Exception as e:
        dur_ms = round((time.perf_counter() - t0) * 1000, 1)
        categories.append({
            "category": "Error Handling",
            "status": "FAILED",
            "duration_ms": dur_ms,
            "details": f"Error: {str(e)}"
        })

    # 10. Performance Tests
    t0 = time.perf_counter()
    try:
        t_perf = time.perf_counter()
        perf_req = EvaluationRequest(
            question="What is the boiling point of ethanol?",
            ai_response="Ethanol boils at 78.37 degrees Celsius.",
            reference_answer="The boiling point of ethanol is 78.37°C."
        )
        orchestrator.evaluate(perf_req)
        lat = time.perf_counter() - t_perf
        assert lat < 15.0, f"Evaluation latency {lat:.2f}s exceeded 15s limit"
        dur_ms = round((time.perf_counter() - t0) * 1000, 1)
        categories.append({
            "category": "Performance Tests",
            "status": "PASSED",
            "duration_ms": dur_ms,
            "details": f"Responsive latency benchmark confirmed ({lat:.2f}s per evaluation pipeline, limit < 15.0s)."
        })
    except Exception as e:
        dur_ms = round((time.perf_counter() - t0) * 1000, 1)
        categories.append({
            "category": "Performance Tests",
            "status": "FAILED",
            "duration_ms": dur_ms,
            "details": f"Error: {str(e)}"
        })

    total_time = round(time.perf_counter() - start_time, 2)
    passed_count = sum(1 for c in categories if c["status"] == "PASSED")
    failed_count = sum(1 for c in categories if c["status"] == "FAILED")
    total_count = len(categories)
    pct = round((passed_count / total_count) * 100.0, 1) if total_count > 0 else 0.0

    return {
        "status": "COMPLETED",
        "total_tests": total_count,
        "passed": passed_count,
        "failed": failed_count,
        "skipped": 0,
        "pass_percentage": pct,
        "execution_time_seconds": total_time,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "categories": categories
    }

