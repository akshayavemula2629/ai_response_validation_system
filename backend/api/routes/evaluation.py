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

