# Tech Stack — AI Response Validation System

This document specifies the technical components, software dependencies, and runtime environment for the **AI Response Validation System**.

---

## 1. Core Framework & Libraries

| Technology | Version | Purpose / Architectural Role |
|---|---|---|
| **Python** | `3.12.x` | Core backend programming language. |
| **FastAPI** | `0.115.x` | High-performance asynchronous REST API framework. |
| **Pydantic** | `2.8.x` | Data validation, request parsing, and schema definition. |
| **Uvicorn** | `0.30.x` | Lightning-fast ASGI web server. |
| **sentence-transformers** | `3.0.x` | Local sentence embedding generation (`all-MiniLM-L6-v2`). |
| **FAISS (faiss-cpu)** | `1.8.x` | High-efficiency local CPU vector indexing and nearest-neighbor retrieval. |
| **NumPy** | `1.26.x` | Vector mathematics, matrix operations, and L2 normalization. |
| **scikit-learn** | `1.4.x` | Fallback hashing vectorizers and cosine similarity utilities. |
| **datasets** | `2.18.x` | Ingestion of Hugging Face benchmark datasets (TruthfulQA, SQuAD). |
| **python-dotenv** | `1.0.x` | Environment variable management and `.env` loading. |
| **httpx** | `0.27.x` | Asynchronous HTTP client for API testing and remote model calls. |
| **OpenAI SDK** | `1.35.x` | Optional LLM-as-a-Judge integration when API keys are configured. |

---

## 2. Model Specifications

- **Embedding Model**: `sentence-transformers/all-MiniLM-L6-v2`
  - Output Dimension: 384
  - Max Sequence Length: 256 tokens
  - Inference Hardware: Standard CPU (AVX2/AVX512 supported)
  - Memory Footprint: ~90 MB
- **Vector Index**: FAISS `IndexFlatIP` (Inner Product on L2-normalized vectors = exact cosine similarity).

---

## 3. Environment & Compatibility

- **Operating System**: Windows 11, Linux (Ubuntu 20.04+), macOS (Apple Silicon / Intel).
- **Python Version**: Python 3.10 to 3.12.
- **Hardware Requirements**:
  - RAM: Minimum 4 GB (8 GB recommended for large batch ingestion).
  - Storage: < 500 MB for models, benchmarks, and vector indices.
  - GPU: Not required (fully optimized for standard CPU execution).
