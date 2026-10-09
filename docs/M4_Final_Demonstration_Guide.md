# M4 Final Demonstration Guide

## Step-by-Step Evaluator Demonstration Manual

### 1. Launching the System
1. Open terminal and start backend:
   ```powershell
   .venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
   ```
2. Open second terminal and start frontend:
   ```powershell
   python run_frontend.py
   ```
   Navigate to `http://127.0.0.1:3000`.

### 2. Sidebar Navigation
- Observe the clean left-side navigation sidebar displaying all 8 sections:
  1. Single Evaluation
  2. Batch Evaluation
  3. Dashboard
  4. Evaluation (Report Export)
  5. End-to-End Testing
  6. Doc & Final Reports
  7. Architecture
  8. History

### 3. Evaluating AI System 1 (High Performing)
1. Click **Batch Evaluation** in the sidebar.
2. Upload `data/demo/ai_system_1_gpt4_responses.csv`.
3. Verify pre-evaluation row validation counter (10 valid records).
4. Set row limit to `10` and click **EVALUATE RESPONSES**.
5. Watch progress and inspect results:
   - High Pass Rate ($\ge 90\%$)
   - Average Score $> 90.0/100$
   - Low Hallucination Risk ($< 10\%$)
6. Expand any row to inspect complete forensic evaluation and individual question pie chart.

### 4. Evaluating AI System 2 (Underperforming / Hallucination-Prone)
1. Click **Batch Evaluation** -> **Replace / Upload Another File**.
2. Upload `data/demo/ai_system_2_generic_responses.csv`.
3. Set row limit to `10` and click **EVALUATE RESPONSES**.
4. Observe results:
   - Low Pass Rate ($\le 30\%$)
   - Multiple `FAIL` and `NEEDS IMPROVEMENT` verdicts
   - High Hallucination Frequency ($> 50\%$)

### 5. Inspecting the Dashboard
1. Click **Dashboard** in the sidebar.
2. View aggregated KPIs: Total Responses, Pass Rate, Needs Improvement Rate, Fail Rate, Average Overall Score, Hallucinated Responses.
3. Observe Dimension Scores, Verdict Donut, Dimension Bar, and Score Distribution Histogram.
4. Test interactive filters: toggle Verdict pills (Pass / Fail), change score tier, or search prompt text.
5. Inspect the drill-down table and click **View Details** to open the forensic evaluation modal.

### 6. Exporting PDF Reports
1. Click **Evaluation** in the sidebar (or click "Export Evaluation Report" on the Dashboard).
2. Click **Generate PDF Report** / **Download PDF**.
3. View the generated multi-page vector PDF report in your PDF reader.

### 7. Running End-to-End Testing Live
1. Click **End-to-End Testing** in the sidebar.
2. Click **Run All Automated Tests**.
3. Observe live testing across all 10 categories, passing statuses, and execution timings.

### 8. Inspecting History & Architecture
1. Click **History** to see past batch runs with scores, dates, and actions.
2. Click **Architecture** to view the interactive diagram of the complete multi-agent pipeline.
