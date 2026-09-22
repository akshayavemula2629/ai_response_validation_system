"""
Knowledge Base Ingestion Pipeline.
Loads benchmark datasets (TruthfulQA and SQuAD), cleans and standardizes them,
generates sentence-aware chunks, creates vector embeddings, and builds the FAISS index.
"""
import logging
import argparse
from typing import List, Dict, Any

from backend.config import settings
from backend.knowledge_base.preprocessing import (
    KBRecord,
    standardize_truthfulqa_record,
    standardize_squad_record
)
from backend.knowledge_base.chunking import chunk_text
from backend.knowledge_base.seed_data import SEED_TRUTHFUL_QA, SEED_SQUAD
from backend.retrieval.embeddings import get_embedding_manager
from backend.retrieval.vector_store import get_vector_store

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("ingestion")


def load_raw_datasets(max_samples_per_dataset: int = 50, use_huggingface: bool = True) -> List[KBRecord]:
    """
    Loads records from Hugging Face datasets if enabled/available,
    and merges with seed benchmark datasets.
    """
    records: List[KBRecord] = []

    # 1. Load TruthfulQA Seeds
    logger.info("Loading TruthfulQA seed benchmarks...")
    for idx, item in enumerate(SEED_TRUTHFUL_QA):
        record = standardize_truthfulqa_record(item, idx)
        records.append(record)

    # 2. Load SQuAD Seeds
    logger.info("Loading SQuAD seed benchmarks...")
    for idx, item in enumerate(SEED_SQUAD):
        record = standardize_squad_record(item, idx)
        records.append(record)

    # 3. Attempt Hugging Face datasets ingestion if requested
    if use_huggingface:
        try:
            logger.info("Attempting to load TruthfulQA from Hugging Face datasets...")
            from datasets import load_dataset
            tqa_ds = load_dataset("truthful_qa", "generation", split=f"validation[:{max_samples_per_dataset}]", trust_remote_code=True)
            for idx, item in enumerate(tqa_ds):
                rec = standardize_truthfulqa_record(item, 1000 + idx)
                records.append(rec)
            logger.info("Successfully fetched %d records from Hugging Face TruthfulQA", len(tqa_ds))
        except Exception as e:
            logger.info("Hugging Face TruthfulQA remote load skipped or unavailable (%s). Seed dataset preserved.", str(e))

        try:
            logger.info("Attempting to load SQuAD from Hugging Face datasets...")
            from datasets import load_dataset
            squad_ds = load_dataset("squad", split=f"train[:{max_samples_per_dataset}]", trust_remote_code=True)
            for idx, item in enumerate(squad_ds):
                rec = standardize_squad_record(item, 2000 + idx)
                records.append(rec)
            logger.info("Successfully fetched %d records from Hugging Face SQuAD", len(squad_ds))
        except Exception as e:
            logger.info("Hugging Face SQuAD remote load skipped or unavailable (%s). Seed dataset preserved.", str(e))

    logger.info("Total standardized records collected: %d", len(records))
    return records


def process_and_chunk_records(records: List[KBRecord]) -> List[Dict[str, Any]]:
    """Chunks documents and creates standardized chunk metadata payloads."""
    all_chunks: List[Dict[str, Any]] = []

    for rec in records:
        content_to_chunk = f"Context: {rec.context}\nQuestion: {rec.question}\nAnswer: {rec.answer}"
        chunks = chunk_text(content_to_chunk, document_id=rec.document_id, max_words=120, overlap_words=25)

        if not chunks:
            chunks = [{
                "chunk_id": f"{rec.document_id}_chunk_0",
                "chunk_index": 0,
                "chunk_text": content_to_chunk
            }]

        for ch in chunks:
            chunk_metadata = {
                "chunk_id": ch["chunk_id"],
                "document_id": rec.document_id,
                "dataset": rec.dataset,
                "question": rec.question,
                "answer": rec.answer,
                "source": rec.source,
                "chunk_text": ch["chunk_text"]
            }
            all_chunks.append(chunk_metadata)

    logger.info("Generated %d chunks across %d documents.", len(all_chunks), len(records))
    return all_chunks


def run_ingestion_pipeline(max_samples: int = 50, use_huggingface: bool = True):
    """
    Executes end-to-end ingestion pipeline:
    Extraction -> Cleaning -> Chunking -> Embedding -> FAISS Indexing -> Persistence.
    """
    logger.info("Starting Knowledge Base Ingestion Pipeline...")
    records = load_raw_datasets(max_samples_per_dataset=max_samples, use_huggingface=use_huggingface)
    chunks = process_and_chunk_records(records)

    chunk_texts = [ch["chunk_text"] for ch in chunks]
    embedding_mgr = get_embedding_manager()

    logger.info("Generating embeddings for %d chunks using %s...", len(chunk_texts), settings.EMBEDDING_MODEL_NAME)
    embeddings = embedding_mgr.embed_batch(chunk_texts, batch_size=32)

    logger.info("Building FAISS vector index...")
    vector_store = get_vector_store()
    vector_store.add_documents(chunks, embeddings)

    logger.info("Persisting vector index and metadata...")
    vector_store.save()
    logger.info("Knowledge Base Ingestion completed successfully! Total indexed chunks: %d", vector_store.count())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest Knowledge Base benchmark datasets.")
    parser.add_argument("--max-samples", type=int, default=30, help="Max samples per remote dataset")
    parser.add_argument("--skip-hf", action="store_true", help="Skip remote Hugging Face download and use seed datasets only")
    args = parser.parse_args()

    run_ingestion_pipeline(max_samples=args.max_samples, use_huggingface=not args.skip_hf)
