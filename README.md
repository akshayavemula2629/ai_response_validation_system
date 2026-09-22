# AI Response Validation System with Hallucination Detection Assistance

[![Python Version](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)](https://fastapi.tiangolo.com/)
[![FAISS](https://img.shields.io/badge/FAISS-CPU-orange.svg)](https://github.com/facebookresearch/faiss)
[![License](https://img.shields.io/badge/License-Academic%20Milestone%201-lightgrey.svg)]()

Production-quality, modular backend built from scratch for automated AI response evaluation, factual grounding verification, hallucination risk quantification, and reference-grounded improved answer generation.

---

## Key Highlights

- **Multi-Agent Evaluation Layer**: Decoupled judge agents assessing **Relevance**, **Accuracy**, **Hallucination Risk**, and **Completeness** on a standardized 0–100 scale.
- **Genuine Hallucination Detection**: Deconstructs responses into atomic claims, verifies each against reference evidence and semantic embeddings, identifies contradictions and ungrounded facts, and provides actionable risk tiers (**Low**, **Medium**, **High**).
- **Grounded "Better Answer" Generation**: Automatically synthesizes an authoritative improved answer grounded in reference truth whenever the original response contains inaccuracies or hallucinations.
- **Frontend-Ready Comparison Data**: Delivers structured numerical comparison metrics (`reference_answer_score`, `better_answer_score`, `similarity_percentage`) for graph and chart visualization.
- **RAG & Knowledge Base Ingestion**: Indexed benchmark foundation (**TruthfulQA** and **SQuAD**) using **FAISS CPU** and **sentence-transformers** (`all-MiniLM-L6-v2`).
- **Zero-Paid-API Out-Of-The-Box Reliability**: Pluggable judge architecture featuring a fully functional local semantic engine that works out of the box with zero external API dependencies or costs, while supporting seamless upgrade to OpenAI/Gemini if API keys are set in `.env`.

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
│   │   │   ├── evaluation.py    # POST /api/evaluate & GET /api/retrieval
│   │   │   └── health.py        # GET /api/health
│   │   └── schemas/
│   │       └── evaluation.py    # Pydantic request/response & validation schemas
│   │
│   ├── agents/
│   │   ├── orchestrator.py      # Multi-agent coordinator
│   │   ├── relevance_agent.py   # Question-answer intent & relevance judge
│   │   ├── accuracy_agent.py    # Factual accuracy & contradiction judge
│   │   ├── hallucination_agent.py # Claim-level hallucination detection agent
│   │   ├── completeness_agent.py  # Reference coverage & recall judge
│   │   └── verdict_agent.py     # Composite score & verdict synthesis
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
│   │   ├── ingestion.py         # TruthfulQA & SQuAD benchmark ingestion pipeline
│   │   ├── preprocessing.py     # Data cleaning & standardization
│   │   ├── chunking.py          # Sentence-aware sliding-window chunker
│   │   └── seed_data.py         # Curated benchmark seed dataset
│   │
│   └── services/
│       └── llm_service.py       # Pluggable LLM abstraction (OpenAI, Gemini, Local)
│
├── data/
│   ├── raw/                     # Raw benchmark data storage
│   └── processed/               # Persisted FAISS index & metadata
│
├── tests/
│   ├── test_validation.py       # Validation error tests (missing Q, ref, AI)
│   ├── test_similarity.py       # Semantic similarity tests
│   ├── test_retrieval.py        # Semantic retrieval & KB tests
│   └── test_evaluation.py       # Full pipeline, hallucination & verdict tests
│
├── docs/
│   ├── System_Architecture.md   # Architectural overview & component mapping
│   ├── Evaluation_Metrics.md    # Metric formulas, weights, and thresholds
│   ├── Implementation_Strategy.md # Technical rationale & future extensions
│   └── Tech_Stack.md            # Dependency breakdown & hardware requirements
│
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---

## Quickstart Setup

### 1. Clone & Set Active Directory
```bash
cd C:\Users\aakan\.gemini\antigravity\scratch\ai_response_validation_system
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Ingest Knowledge Base Benchmark Datasets
Build and persist the FAISS vector index with TruthfulQA and SQuAD benchmarks:
```bash
# Ingest with offline seed benchmarks
python -m backend.knowledge_base.ingestion --skip-hf

# Or ingest with remote Hugging Face benchmarks
python -m backend.knowledge_base.ingestion --max-samples 50
```

### 4. Run the FastAPI Development Server
```bash
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```
The interactive Swagger API documentation will be available at:
- **Interactive API Docs**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Alternative ReDoc**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

---

## Running Automated Tests

Run the full test suite covering all 11 milestone requirements:
```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

All 18 unit and integration tests will execute:
- Input validation (missing question, missing reference answer, missing AI response, whitespace-only).
- Semantic similarity calculation and distinction from factual correctness.
- Independent knowledge base retrieval from FAISS.
- Hallucination detection on contradictory and ungrounded statements.
- Partially correct and incomplete response evaluations.
- Grounded better-answer generation and reference comparison metrics.
- Verdict score weighting and threshold categorization.

---

## API Usage Examples

### 1. Evaluate an AI Response
**Endpoint**: `POST /api/evaluate`

**Request**:
```bash
curl -X POST "http://127.0.0.1:8000/api/evaluate" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What happens if you swallow chewing gum?",
    "ai_response": "Swallowed chewing gum gets stuck in your stomach for seven years and requires medical surgery.",
    "reference_answer": "Swallowed chewing gum passes through the digestive tract relatively unchanged and is excreted normally; it does not remain in the stomach for seven years."
  }'
```

**Response (Sample Output)**:
```json
{
  "question": "What happens if you swallow chewing gum?",
  "original_response": "Swallowed chewing gum gets stuck in your stomach for seven years and requires medical surgery.",
  "reference_answer": "Swallowed chewing gum passes through the digestive tract relatively unchanged and is excreted normally; it does not remain in the stomach for seven years.",
  "better_answer": "Swallowed chewing gum passes through the digestive tract relatively unchanged and is excreted normally; it does not remain in the stomach for seven years.",
  "better_answer_reason": "The generated better answer is preferred because it removes unsupported or contradictory claims, and corrects factual discrepancies with ground truth evidence, ensuring complete factual alignment with verified reference material.",
  "evaluation": {
    "relevance": {
      "score": 92.5,
      "explanation": "The response directly and clearly addresses the core intent and specific subject of the question."
    },
    "accuracy": {
      "score": 30.0,
      "explanation": "Factual discrepancies identified: Direct contradiction detected: AI response affirms that it remains in stomach / digestive tract, which the reference explicitly refutes.. The response deviates from or directly contradicts established reference facts."
    },
    "hallucination": {
      "score": 0.0,
      "percentage": 100.0,
      "risk_level": "High",
      "explanation": "High hallucination risk (100.0%). The response contains significant unsupported or contradictory information (2 issue(s) detected).",
      "issues": [
        "Contradictory claim: 'Swallowed chewing gum gets stuck in your stomach for seven years and requires medical surgery.' contradicts reference stating gum does not stay in the stomach."
      ]
    },
    "completeness": {
      "score": 62.1,
      "explanation": "The response covers primary points but omits notable details (1 aspects unaddressed)."
    },
    "similarity": {
      "percentage": 78.4,
      "explanation": "The AI response exhibits moderate semantic similarity (78.4%) with the reference material. Note: Semantic similarity measures structural and lexical alignment and is distinct from factual correctness or truthfulness."
    },
    "overall_score": 42.9,
    "verdict": "Poor",
    "summary": "The response achieved an overall verdict score of 42.9/100, classified as 'Poor'. Key metrics: Relevance: 92.5/100, Accuracy: 30.0/100, Hallucination Risk: 100.0% (High risk), Completeness: 62.1/100, and Semantic Similarity: 78.4%. The response contains severe factual inaccuracies, hallucinations, or irrelevance. Do NOT rely on the original response; substitute with the grounded 'Better Answer'."
  },
  "retrieved_evidence": [
    {
      "chunk_id": "truthfulqa_0_chunk_0",
      "content": "Context: Question: What happens if you swallow chewing gum? Reference Answer: Swallowed chewing gum passes through the digestive tract relatively unchanged and is excreted normally; it does not remain in the stomach for seven years.",
      "source": "TruthfulQA - Misconceptions",
      "similarity_score": 0.8241
    }
  ],
  "comparison": {
    "reference_answer_score": 100.0,
    "better_answer_score": 98.5,
    "similarity_percentage": 100.0
  }
}
```

### 2. Independent Semantic Retrieval
**Endpoint**: `GET /api/retrieval?question=...`

```bash
curl -X GET "http://127.0.0.1:8000/api/retrieval?question=Who%20walked%20on%20the%20Moon&top_k=2"
```

### 3. System Health Check
**Endpoint**: `GET /api/health`

```bash
curl -X GET "http://127.0.0.1:8000/api/health"
```
