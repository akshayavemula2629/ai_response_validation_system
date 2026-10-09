# Implementation Strategy & Technical Rationale

This document details the engineering principles, architectural trade-offs, and technical rationale underlying the design of the **AI Response Validation System** (Milestone 1).

---

## 1. Technology Selection & Architectural Decisions

### 1.1 Backend Framework: FastAPI
- **Choice**: FastAPI with Python 3.12 and Pydantic v2.
- **Rationale**:
  - Native asynchronous I/O support for high-throughput evaluation requests.
  - Automatic OpenAPI / Swagger UI generation at `/docs` for effortless testing without building complex frontends prematurely.
  - Pydantic v2 provides compile-speed schema validation, enforcing strict input constraints with clear JSON error responses.

### 1.2 Vector Database: FAISS (CPU)
- **Choice**: FAISS (`IndexFlatIP` with L2-normalized embeddings).
- **Rationale**:
  - Runs natively on CPU without requiring heavy cloud vector services (e.g., Pinecone, Milvus) or background daemon processes.
  - Exact nearest-neighbor cosine similarity calculation with sub-millisecond retrieval latency.
  - Portable disk serialization (`vector_index.faiss` + `metadata.json`) allowing easy persistence and versioning.

### 1.3 Embedding Model: `sentence-transformers/all-MiniLM-L6-v2`
- **Choice**: 384-dimensional MiniLM model.
- **Rationale**:
  - Superb trade-off between inference speed (10–20ms per sentence on standard CPU) and semantic representation quality.
  - Pre-trained on over 1 billion sentence pairs for clustering and semantic search.
  - Embedded as a singleton manager (`EmbeddingManager`) with model caching to eliminate reloading overhead across requests.

### 1.4 Pluggable Judge Architecture & Zero-Paid-API Out-Of-The-Box Reliability
- **Choice**: `BaseLLMClient` with `OpenAILLMClient`, `GeminiLLMClient`, and `HybridSemanticJudge`.
- **Rationale**:
  - Systems that hard-depend on external paid APIs break when API keys expire, billing limits hit (e.g. 429 quota exhaustion), or internet connections fluctuate.
  - Our system automatically falls back to an algorithmic, local semantic judge when external keys are absent or exhausted.
  - The local judge executes genuine NLP claim extraction, sentence entailment, entity checking, and negation analysis rather than fake random values.

---

## 2. Hallucination Detection Pipeline

Hallucination detection is not computed as a naive `100 - similarity` formula. The pipeline follows a multi-stage claim verification workflow:

1. **Claim Extraction**: The response is segmented into individual semantic claims using sentence boundary tokenization.
2. **Evidence Pool Assembly**: Sentences from the reference ground truth, user-supplied documents, and top-k retrieved KB chunks form the evidence pool.
3. **Semantic Grounding**: Each claim vector is compared against all evidence sentence vectors to locate the strongest supporting context.
4. **Contradiction & Negation Detection**:
   - Polarity inversion checks (detecting if reference refutes what the AI response affirms, such as misconceptions).
   - Entity conflicts (identifying mismatched named entities).
   - Date and numeric factual checks (identifying unsupported dates/years).
5. **Risk Aggregation**: Unsupported claims and contradictions are weighted to compute the exact hallucination risk percentage (0–100%) and hallucination-free score.

---

## 3. Knowledge Base Benchmark Foundation

- **Benchmarks**: **TruthfulQA** (for hallucination and misconception testing) and **SQuAD** (for reading comprehension and factual recall).
- **Ingestion**: Standardizes disparate formats into uniform `KBRecord` models, applies sentence-aware sliding window chunking (120 words with 25-word overlap), generates embeddings in batches, and indexes them into FAISS.
- **Offline Reliability**: Includes curated seed benchmark entries to allow instantaneous setup and testing without requiring remote network requests to Hugging Face.

---

## 4. Future Milestone Extensibility

The system architecture provides clean extension points for subsequent milestones:

- **RAGAS Integration**: Clean hooks exist in `backend/evaluation/` to incorporate RAGAS metrics (`faithfulness`, `answer_relevancy`, `context_precision`) alongside custom agents.
- **TruLens Integration**: Orchestrator structure allows instrumenting TruLens feedback functions (`QS_relevance`, `groundedness`) without altering API contracts.
- **Batch Evaluation & Reporting**: The Orchestrator's `evaluate` method can be invoked in concurrent task pools for batch processing of test sets.
- **Database Persistence**: SQLite/PostgreSQL connectors can be connected to the API layer to store historical evaluation runs.
