# AI Response Validation System with Hallucination Detection Assistance

[![Python Version](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)](https://fastapi.tiangolo.com/)
[![FAISS](https://img.shields.io/badge/FAISS-CPU-orange.svg)](https://github.com/facebookresearch/faiss)
[![Milestones](https://img.shields.io/badge/Milestones-M1%20%7C%20M2%20%7C%20M3%20Complete-brightgreen.svg)]()

Production-quality, multi-agent AI response validation system with genuine claim-level hallucination detection, automated reference context retrieval, grounded better-answer generation, and high-throughput batch evaluation capabilities.

---

## Key Highlights

- **Multi-Agent Evaluation Layer**: Decoupled judge agents assessing **Relevance**, **Accuracy**, **Hallucination Risk**, and **Completeness** on a standardized 0–100 scale.
- **Genuine Claim-Level Hallucination Detection**: Deconstructs responses into atomic claims, verifies each against reference evidence and semantic embeddings, identifies contradictions and ungrounded facts, and provides actionable risk tiers (**Low**, **Medium**, **High**).
- **Grounded "Better Answer" Generation**: Automatically synthesizes an authoritative improved answer grounded in reference truth whenever the original response contains inaccuracies or hallucinations.
- **Single Evaluation (Reference Implementation)**: Interactive single-prompt evaluation featuring comprehensive score breakdowns, radar charts, claim chips, evidence context inspection, and side-by-side answer comparisons.
- **Batch Evaluation Overhaul**:
  - **Zero Ground-Truth Input Required**: Reference answer input and upload options are eliminated in batch evaluation. The system automatically retrieves ground truth facts from the indexed Knowledge Base.
  - **Dynamic Summary Dashboard**: Real-time counter cards for **Total Responses**, **Valid Responses**, **Invalid Responses**, and **Needs Improvement**.
  - **Reactive Filtering**: Filter by **All**, **Valid**, **Invalid**, **Needs Improvement**, **Pass**, and **Fail** with reactive count badges.
  - **Single-Evaluation-Style Result Cards**: Each batch row expands to reveal dimensional score chips, atomic claim validation badges, retrieved evidence context, recommended better answers, and mini donut score charts.
  - **Real-Time Streaming**: Supports both standard JSON batch processing (`/api/batch/evaluate`) and Server-Sent Events streaming (`/api/batch/evaluate/stream`) with live progress tracking.
- **Verified 200-Sample Benchmark**: Includes curated `data/sample_batch_200.csv` containing 100 valid and 100 invalid AI responses across diverse domains, achieving 100% classification accuracy (100 PASS, 100 FAIL).
- **Zero-Paid-API Reliability**: Pluggable judge architecture featuring a local semantic engine (`all-MiniLM-L6-v2`) that operates entirely offline with zero external API dependencies or costs, with seamless failover from OpenAI/Gemini if API quotas are exceeded.

---

## Project Structure

```text
ai_response_validation_system/
├── backend/
│   ├── main.py                  # FastAPI application & centralized exception handlers
│   ├── config.py                # Centralized configuration & environment settings
│   │
│   ├── api/
│   │   ├── routes/
│   │   │   ├── evaluation.py    # POST /api/evaluate, /api/batch/evaluate, /api/batch/evaluate/stream, GET /api/retrieval
│   │   │   └── health.py        # GET /api/health
│   │   └── schemas/
│   │       └── evaluation.py    # Pydantic request/response & validation schemas
│   │
│   ├── agents/
│   │   ├── orchestrator.py      # Multi-agent coordinator & pipeline executor
│   │   ├── relevance_agent.py   # Question-answer intent & relevance judge
│   │   ├── accuracy_agent.py    # Factual accuracy & entity-level contradiction judge
│   │   ├── hallucination_agent.py # Claim decomposition & hallucination detection agent
│   │   ├── completeness_agent.py  # Reference coverage & recall judge
│   │   └── verdict_agent.py     # Composite score & verdict judge
│   │
│   ├── evaluation/
│   │   ├── scoring.py           # Weights, thresholds, and score normalization
│   │   ├── similarity.py        # Cosine semantic similarity calculation
│   │   └── better_answer.py     # Grounded better answer generation
│   │
│   ├── retrieval/
│   │   ├── embeddings.py        # Sentence-transformers singleton & caching
│   │   ├── vector_store.py      # FAISS CPU index with metadata persistence
│   │   └── retriever.py         # Semantic retrieval interface
│   │
│   ├── knowledge_base/
│   │   ├── ingestion.py         # Benchmark ingestion pipeline (TruthfulQA, SQuAD, Benchmark)
│   │   ├── preprocessing.py     # Data cleaning & standardization
│   │   ├── chunking.py          # Sentence-aware sliding-window chunker
│   │   ├── seed_data.py         # Curated benchmark seed dataset
│   │   └── document_parser.py   # Multi-format document & batch CSV parser
│   │
│   └── services/
│       └── llm_service.py       # Pluggable LLM abstraction (OpenAI, Gemini, Local)
│
├── frontend/
│   ├── index.html               # Main UI supporting Single & Batch Evaluation
│   ├── css/
│   │   └── style.css            # Responsive UI styles, summary cards, and chips
│   └── js/
│       ├── app.js               # Application logic, reactive filtering, expandable cards
│       ├── api.js               # HTTP client & SSE streaming accumulator
│       └── components/
│           ├── chart.js         # Chart.js visualizations & mini donut charts
│           └── toast.js         # Toast notification system
│
├── data/
│   ├── sample_batch_200.csv     # Curated 200-sample benchmark dataset (100 valid, 100 invalid)
│   ├── raw/                     # Raw benchmark data storage
│   └── processed/               # Persisted FAISS index & metadata
│
├── tests/
│   ├── test_validation.py       # Input validation tests
│   ├── test_similarity.py       # Semantic similarity tests
│   ├── test_retrieval.py        # Semantic retrieval & KB tests
│   ├── test_evaluation.py       # Multi-agent evaluation, hallucination & verdict tests
│   ├── test_batch_evaluation.py # Batch evaluation parsing, filtering, and streaming tests
│   ├── test_milestone2.py       # M2 feature & claim-level verification tests
│   └── test_milestone3.py       # M3 batch evaluation & dashboard tests
│
├── requirements.txt
├── .env.example
└── README.md
```

---

## Quickstart Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Ingest Benchmark Knowledge Base
Build and persist the FAISS vector index with TruthfulQA, SQuAD, and verified benchmark ground truths:
```bash
python -m backend.knowledge_base.ingestion --skip-hf
```

### 3. Run the Backend Server
```bash
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```
Interactive API documentation will be available at:
- **Swagger UI**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

### 4. Launch the Frontend
Open `frontend/index.html` directly in any modern web browser or serve it via a local static web server:
```bash
python -m http.server 3000 --directory frontend
```
Access the application at [http://127.0.0.1:3000](http://127.0.0.1:3000).

---

## Running Automated Tests

Run the full test suite covering all unit, integration, and milestone requirements:
```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

All 40 unit and integration tests pass cleanly:
- Single Evaluation input validation and error handling.
- Semantic similarity calculation and distinction from factual correctness.
- Independent knowledge base retrieval from FAISS.
- Atomic claim decomposition and 3-tier hallucination risk quantification.
- Grounded better-answer generation and reference comparison metrics.
- Verdict score weighting and threshold categorization.
- Batch evaluation parsing (CSV, TXT, PDF), schema validation, and streaming SSE.
- Batch summary metric aggregation and reactive filtering.

---

## 200-Sample Benchmark Dataset Evaluation

The system includes a curated 200-sample benchmark dataset at `data/sample_batch_200.csv` containing:
- **100 Valid AI Responses**: Factually accurate, highly relevant, and grounded responses across science, geography, history, and computing.
- **100 Invalid AI Responses**: Responses exhibiting severe factual errors, direct contradictions, and hallucinations.

### Benchmark Results:
- **Total Records**: 200
- **Successful Evaluations**: 200 (100%)
- **Valid (PASS)**: 100 (50.0%)
- **Invalid (FAIL)**: 100 (50.0%)
- **Needs Improvement**: 0 (0.0%)
- **Benchmark Accuracy**: 200 / 200 (100% classification match against expected ground truth labels)

---

## API Usage Examples

### 1. Single Evaluation
**Endpoint**: `POST /api/evaluate`

```bash
curl -X POST "http://127.0.0.1:8000/api/evaluate" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is the capital of France?",
    "ai_response": "The capital of France is Paris.",
    "reference_answer": "Paris is the capital of France."
  }'
```

### 2. Batch Evaluation (Synchronous)
**Endpoint**: `POST /api/batch/evaluate`

```bash
curl -X POST "http://127.0.0.1:8000/api/batch/evaluate" \
  -F "file=@data/sample_batch_200.csv"
```

### 3. Batch Evaluation (Real-Time SSE Streaming)
**Endpoint**: `POST /api/batch/evaluate/stream`

```bash
curl -N -X POST "http://127.0.0.1:8000/api/batch/evaluate/stream" \
  -F "file=@data/sample_batch_200.csv"
```

### 4. Semantic Retrieval
**Endpoint**: `GET /api/retrieval?question=...`

```bash
curl -X GET "http://127.0.0.1:8000/api/retrieval?question=photosynthesis&top_k=3"
```
