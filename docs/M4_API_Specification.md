# M4 API Specification

## Endpoints Summary

### 1. Evaluation Endpoints
- **POST `/api/evaluate`**: Synchronous single response evaluation.
- **POST `/api/evaluate/stream`**: SSE streaming single response evaluation.

### 2. Batch Evaluation Endpoints
- **POST `/api/batch/validate-input`**: Pre-evaluation validation of uploaded CSV/TXT/PDF records.
- **POST `/api/batch/evaluate`**: Batch evaluation execution with selective row limits and filters.
- **POST `/api/batch/evaluate/stream`**: SSE streaming batch evaluation row-by-row.
- **GET `/api/batch/history`**: Chronological list of saved batch runs with trend arrays.
- **GET `/api/batch/{batch_id}`**: Complete evaluation records and summary for a specific batch.

### 3. Dashboard Endpoints
- **GET `/api/dashboard/analytics`**: Multi-run aggregated KPIs, dimension averages, score distributions, and recurring issues. Supports optional `?batch_id=` parameter.

### 4. PDF Export Endpoints
- **POST `/api/batch/report/pdf`**: Generates and downloads multi-page Executive PDF report for a batch.
- **POST `/api/single/report/pdf`**: Generates and downloads forensic Single Evaluation PDF report.

### 5. Automated Testing Endpoints
- **POST `/api/testing/run`**: Executes automated verification suite across 10 categories and returns live results.

### 6. Retrieval Endpoints
- **GET `/api/retrieval`**: Independent semantic search against indexed knowledge base.
