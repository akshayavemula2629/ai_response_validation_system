# M4 Architecture and Data Flow

## 1. System Architecture Overview

```text
                               +-------------------------------------+
                               |         WEB USER INTERFACE          |
                               | (Sidebar Navigation / 8 Page Views) |
                               +------------------+------------------+
                                                  | HTTP / SSE
                                                  v
                               +-------------------------------------+
                               |         FASTAPI ROUTER LAYER        |
                               |  /api/evaluate, /api/batch, etc.    |
                               +------------------+------------------+
                                                  |
                         +------------------------+------------------------+
                         |                                                 |
                         v                                                 v
         +-------------------------------+                 +-------------------------------+
         |    EVALUATION ORCHESTRATOR    |                 |   BATCH STORAGE & ANALYTICS   |
         |    Coordinates Judge Agents   |                 |   JSON Persistence / History  |
         +---------------+---------------+                 +---------------+---------------+
                         |                                                 |
         +---------------+---------------+                 +---------------+---------------+
         |   RAG / RETRIEVAL ENGINE      |                 |    REPORTLAB PDF SERVICE      |
         |   FAISS + MiniLM Embeddings   |                 |    Executive Vector PDF Gen   |
         +---------------+---------------+                 +-------------------------------+
                         |
      +------------------+------------------+
      |                  |                  |
      v                  v                  v
[Relevance Judge] [Accuracy Judge] [Hallucination Judge]
      |                  |                  |
      +------------------+------------------+
                         |
                         v
                [Completeness Judge]
                         |
                         v
                  [Verdict Agent]
                         |
                         v
             Structured Evaluation Result
```

## 2. Component Directory
- **Single Evaluation**: Direct prompt submission with real-time SSE progress or synchronous evaluation.
- **Batch Evaluation**: File upload parser, row validation, selective limits, and expandable row details with individual charts.
- **Dashboard**: Dynamic calculation of KPIs, dimension averages, score histograms, and issue rankings from real storage.
- **Evaluation (Report Export)**: Executive multi-page PDF generation via ReportLab.
- **End-to-End Testing**: Interactive automated test runner executing live tests across 10 categories.
- **Doc & Final Reports**: Comprehensive documentation browser.
- **Architecture**: Interactive visual component flow.
- **History**: Historical evaluation runs index and inspection.
