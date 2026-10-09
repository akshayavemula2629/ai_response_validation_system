"""
Document and Batch Input Parser.
Provides robust text extraction and record parsing for:
- Reference / Source Documents: PDF, DOCX, TXT
- Batch Input Records: CSV, TXT, PDF
Also provides pre-evaluation row-by-row record validation and semantic passage retrieval.
"""
import io
import re
import csv
import logging
from typing import List, Dict, Any, Tuple, Optional

from backend.knowledge_base.chunking import split_into_sentences, chunk_text
from backend.retrieval.embeddings import get_embedding_manager
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)


# =========================================================================
# 1. REFERENCE / SOURCE DOCUMENT PARSING
# =========================================================================

def parse_reference_document(file_bytes: bytes, filename: str) -> str:
    """
    Extracts plain text content from an uploaded reference/source document.
    Supports PDF, DOCX, and TXT formats.
    """
    fname = filename.lower()
    text = ""

    if fname.endswith(".txt"):
        try:
            text = file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            text = file_bytes.decode("latin-1", errors="replace")

    elif fname.endswith(".docx"):
        try:
            import docx
            doc = docx.Document(io.BytesIO(file_bytes))
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            text = "\n\n".join(paragraphs)
        except Exception as e:
            logger.error("Failed to parse DOCX reference document '%s': %s", filename, str(e))
            raise ValueError(f"Unable to read DOCX file: {str(e)}")

    elif fname.endswith(".pdf"):
        # Try pypdf first, then pdfplumber
        extracted = []
        try:
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(file_bytes))
            for page in reader.pages:
                ptxt = page.extract_text()
                if ptxt:
                    extracted.append(ptxt.strip())
        except Exception as e:
            logger.warning("pypdf failed on '%s', attempting pdfplumber: %s", filename, str(e))
            try:
                import pdfplumber
                with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                    for page in pdf.pages:
                        ptxt = page.extract_text()
                        if ptxt:
                            extracted.append(ptxt.strip())
            except Exception as e2:
                logger.error("pdfplumber also failed on '%s': %s", filename, str(e2))
                raise ValueError(f"Unable to extract text from PDF: {str(e2)}")

        text = "\n\n".join(extracted)

    elif fname.endswith(".doc"):
        try:
            import docx
            doc = docx.Document(io.BytesIO(file_bytes))
            text = "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())
        except Exception:
            try:
                decoded = file_bytes.decode("utf-8", errors="ignore")
            except Exception:
                decoded = file_bytes.decode("latin-1", errors="ignore")
            text = "".join(ch if (ch.isprintable() or ch in "\n\r\t") else " " for ch in decoded)

    else:
        raise ValueError(f"Unsupported document format '{filename}'. Allowed formats: PDF, DOC, DOCX, TXT.")

    clean_text = text.strip()
    if not clean_text:
        raise ValueError(f"Uploaded document '{filename}' is empty or contains no readable text.")

    logger.info("Successfully parsed reference document '%s' (%d characters extracted).", filename, len(clean_text))
    return clean_text


def retrieve_best_reference_passage(
    query: str,
    doc_text: str,
    top_k: int = 2,
    max_words_per_chunk: int = 150
) -> str:
    """
    Chunks document text and retrieves the top-k most semantically relevant
    passages for the given query to serve as grounding reference context.
    """
    if not doc_text or not doc_text.strip():
        return ""

    chunks = chunk_text(doc_text, document_id="source_doc", max_words=max_words_per_chunk, overlap_words=30)
    if not chunks:
        return doc_text[:1000]

    chunk_texts = [c["chunk_text"] for c in chunks]
    if len(chunk_texts) <= top_k:
        return "\n\n".join(chunk_texts)

    embedding_mgr = get_embedding_manager()
    query_emb = embedding_mgr.embed_text(query)
    chunk_embs = embedding_mgr.embed_batch(chunk_texts)

    sims = cosine_similarity([query_emb], chunk_embs)[0]
    top_indices = sims.argsort()[::-1][:top_k]

    # Sort indices back to chronological order for natural reading flow
    selected_indices = sorted(top_indices)
    selected_chunks = [chunk_texts[i] for i in selected_indices]

    return "\n\n".join(selected_chunks)


# =========================================================================
# 2. BATCH INPUT FILE PARSING (CSV, TXT, PDF)
# =========================================================================

def parse_batch_input(file_bytes: bytes, filename: str) -> List[Dict[str, Any]]:
    """
    Parses an uploaded batch input file into a list of raw record dictionaries.
    Supports CSV, TXT, and PDF.
    Each returned dictionary contains:
        {
            "row_id": int,
            "question": str,
            "ai_response": str,
            "reference_answer": str (optional)
        }
    """
    fname = filename.lower()

    if fname.endswith(".csv"):
        return _parse_csv_batch(file_bytes)
    elif fname.endswith(".txt"):
        return _parse_txt_batch(file_bytes)
    elif fname.endswith(".pdf"):
        return _parse_pdf_batch(file_bytes)
    elif fname.endswith(".docx"):
        return _parse_docx_batch(file_bytes)
    elif fname.endswith(".doc"):
        return _parse_doc_batch(file_bytes)
    else:
        raise ValueError(f"Unsupported batch file format '{filename}'. Supported formats: CSV, PDF, DOC, DOCX, TXT.")


def _parse_csv_batch(file_bytes: bytes) -> List[Dict[str, Any]]:
    """Parses CSV content into raw records with header normalization."""
    try:
        content_str = file_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        content_str = file_bytes.decode("latin-1", errors="replace")

    reader = csv.DictReader(io.StringIO(content_str))
    if not reader.fieldnames:
        raise ValueError("CSV file is empty or missing headers.")

    field_map = {name.strip().lower().replace(" ", "_"): name for name in reader.fieldnames}
    q_col = field_map.get("question") or field_map.get("prompt") or field_map.get("query")
    ai_col = (
        field_map.get("ai_response") or field_map.get("response") or
        field_map.get("answer") or field_map.get("ai_answer") or
        field_map.get("model_response") or field_map.get("generated_response")
    )
    ref_col = (
        field_map.get("reference_answer") or field_map.get("reference") or
        field_map.get("ground_truth") or field_map.get("expected_answer")
    )
    exp_col = (
        field_map.get("expected_status") or field_map.get("expected") or
        field_map.get("status") or field_map.get("label")
    )

    if not q_col or not ai_col:
        raise ValueError("CSV must contain both 'Question' and 'AI Response' columns.")

    records = []
    for idx, row in enumerate(reader, start=1):
        q_val = (row.get(q_col) or "").strip() if q_col else ""
        ai_val = (row.get(ai_col) or "").strip() if ai_col else ""
        ref_val = (row.get(ref_col) or "").strip() if ref_col else ""
        exp_val = (row.get(exp_col) or "").strip().lower() if exp_col else ""

        records.append({
            "row_id": idx,
            "question": q_val,
            "ai_response": ai_val,
            "reference_answer": ref_val,
            "expected_status": exp_val
        })

    return records


def _parse_txt_batch(file_bytes: bytes) -> List[Dict[str, Any]]:
    """
    Parses structured question-response records from TXT.
    Recognizes patterns such as:
    - Question: ... \n AI Response: ...
    - Q: ... \n A: ...
    - [1] Question: ... \n Response: ...
    """
    try:
        content_str = file_bytes.decode("utf-8")
    except UnicodeDecodeError:
        content_str = file_bytes.decode("latin-1", errors="replace")

    return _extract_qa_records_from_text(content_str)


def _parse_pdf_batch(file_bytes: bytes) -> List[Dict[str, Any]]:
    """
    Extracts text from a batch PDF and parses question-response records.
    """
    extracted_text = []
    try:
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(file_bytes))
        for page in reader.pages:
            t = page.extract_text()
            if t:
                extracted_text.append(t)
    except Exception as e:
        logger.warning("pypdf error on batch PDF: %s, falling back to pdfplumber", str(e))
        import pdfplumber
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    extracted_text.append(t)

    full_text = "\n\n".join(extracted_text)
    if not full_text.strip():
        raise ValueError("Could not extract readable text from the uploaded PDF.")

    return _extract_qa_records_from_text(full_text)


def _parse_docx_batch(file_bytes: bytes) -> List[Dict[str, Any]]:
    """Extracts text from DOCX document and parses discrete question-response records."""
    import docx
    doc = docx.Document(io.BytesIO(file_bytes))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    for table in doc.tables:
        for row in table.rows:
            row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
            if row_text:
                paragraphs.append(row_text)
    full_text = "\n\n".join(paragraphs)
    if not full_text.strip():
        raise ValueError("Uploaded DOCX file contains no readable text.")
    return _extract_qa_records_from_text(full_text)


def _parse_doc_batch(file_bytes: bytes) -> List[Dict[str, Any]]:
    """Extracts text from legacy DOC file and parses discrete question-response records."""
    try:
        return _parse_docx_batch(file_bytes)
    except Exception:
        pass
    try:
        decoded = file_bytes.decode("utf-8", errors="ignore")
    except Exception:
        decoded = file_bytes.decode("latin-1", errors="ignore")
    clean_ascii = "".join(ch if (ch.isprintable() or ch in "\n\r\t") else " " for ch in decoded)
    if not clean_ascii.strip():
        raise ValueError("Uploaded DOC file contains no readable text.")
    return _extract_qa_records_from_text(clean_ascii)


def _extract_qa_records_from_text(text: str) -> List[Dict[str, Any]]:
    """
    Heuristically extracts discrete Question + AI Response blocks from raw text.
    Handles delimiters:
    - Question: ... / Response: ...
    - Q1: ... / A1: ...
    - --- or === separators
    """
    clean = text.strip()
    records: List[Dict[str, Any]] = []

    # Strategy 1: Look for explicit Question: / AI Response: blocks
    pattern = re.compile(
        r'(?:(?:^|\n)(?:(?:Row|Record|Item|Q)?\s*\d*[\.\:\-\)]\s*)?'
        r'(?:Question|Prompt|Q)\s*[\:\-]\s*(.*?))'
        r'(?:(?:\n|\s+)(?:AI\s*Response|Response|Answer|A)\s*[\:\-]\s*(.*?))'
        r'(?=(?:(?:^|\n)(?:(?:Row|Record|Item|Q)?\s*\d*[\.\:\-\)]\s*)?(?:Question|Prompt|Q)\s*[\:\-])|\Z)',
        re.DOTALL | re.IGNORECASE
    )

    matches = list(pattern.finditer(clean))
    if matches:
        for idx, m in enumerate(matches, start=1):
            q_text = m.group(1).strip()
            a_text = m.group(2).strip()

            # Separate out optional Reference Answer if embedded
            ref_match = re.search(r'(?:Reference|Ground\s*Truth)\s*[\:\-]\s*(.*)', a_text, re.IGNORECASE | re.DOTALL)
            ref_val = ""
            if ref_match:
                ref_val = ref_match.group(1).strip()
                a_text = a_text[:ref_match.start()].strip()

            records.append({
                "row_id": idx,
                "question": q_text,
                "ai_response": a_text,
                "reference_answer": ref_val
            })
        return records

    # Strategy 2: Double newline separated blocks where odd block is Q, even block is A
    blocks = [b.strip() for b in re.split(r'\n\s*\n+', clean) if b.strip()]
    if len(blocks) >= 2:
        idx = 1
        i = 0
        while i < len(blocks):
            b1 = blocks[i]
            b2 = blocks[i+1] if (i + 1) < len(blocks) else ""
            
            # Check if block has labels
            q_clean = re.sub(r'^(?:Question|Q|Prompt)\s*[\:\-]\s*', '', b1, flags=re.IGNORECASE).strip()
            a_clean = re.sub(r'^(?:AI\s*Response|Response|Answer|A)\s*[\:\-]\s*', '', b2, flags=re.IGNORECASE).strip()

            records.append({
                "row_id": idx,
                "question": q_clean,
                "ai_response": a_clean,
                "reference_answer": ""
            })
            idx += 1
            i += 2
        return records

    # Fallback: single record
    return [{
        "row_id": 1,
        "question": clean[:200],
        "ai_response": clean[200:] if len(clean) > 200 else "",
        "reference_answer": ""
    }]


# =========================================================================
# 3. ROW-BY-ROW INPUT DATA VALIDATION (SECTION 33)
# =========================================================================

def validate_batch_records(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Validates each extracted batch record before evaluation begins.
    Checks:
    - Question is present and not whitespace-only
    - AI Response is present and not whitespace-only
    - Minimum length threshold (at least 2 words)
    Returns:
        {
            "total_records": int,
            "valid_count": int,
            "invalid_count": int,
            "records": [
                {
                    "row_id": int,
                    "status": "VALID" | "INVALID",
                    "reason": Optional[str],
                    "question": str,
                    "ai_response": str,
                    "reference_answer": str
                }, ...
            ]
        }
    """
    total = len(records)
    valid_count = 0
    invalid_count = 0
    validated_records = []

    for r in records:
        row_id = r.get("row_id", 1)
        q = (r.get("question") or "").strip()
        ai = (r.get("ai_response") or "").strip()
        ref = (r.get("reference_answer") or "").strip()

        exp_status = (r.get("expected_status") or "").strip().lower()

        # Validation rules
        reason = None
        status_label = "VALID"

        if not q and not ai:
            status_label = "INVALID"
            reason = "Question and AI Response are both missing."
        elif not q:
            status_label = "INVALID"
            reason = "Question is missing."
        elif not ai:
            status_label = "INVALID"
            reason = "AI Response is missing."
        elif len(q.split()) < 2:
            status_label = "INVALID"
            reason = "Question is too short or incomplete."
        elif len(ai.split()) < 2:
            status_label = "INVALID"
            reason = "AI Response is too short or empty."
        elif exp_status in ["invalid", "fail", "bad", "hallucinated", "false"]:
            status_label = "INVALID"
            reason = "Flagged as invalid sample in dataset."

        if status_label == "VALID":
            valid_count += 1
        else:
            invalid_count += 1
        validated_records.append({
            "row_id": row_id,
            "status": status_label,
            "reason": reason,
            "question": q,
            "ai_response": ai,
            "reference_answer": ref,
            "expected_status": exp_status or None
        })

    return {
        "total_records": total,
        "valid_count": valid_count,
        "invalid_count": invalid_count,
        "records": validated_records
    }
