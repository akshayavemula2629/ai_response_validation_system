# Agile Project Documentation

## Project
**AI Response Validation System with Hallucination Detection Assistance**

## Objective
Build a system that evaluates AI-generated answers for relevance, factual accuracy, hallucination risk, completeness, and an overall verdict. The system supports individual and CSV-based batch evaluation, dashboard summaries, visual analytics, and PDF reporting.

## Agile Approach
The project follows an iterative Agile/Scrum-inspired workflow. Work is divided into milestones, with each milestone producing reviewable functionality. At the end of each iteration, changes should be tested and integrated without regressing previously working features.

## Roles and Responsibilities
- **Product/Project Owner:** Defines requirements, priorities, and acceptance criteria.
- **Development Team:** Implements the API, evaluation agents, retrieval layer, frontend, dashboards, and reports.
- **Reviewer/Tester:** Runs acceptance tests, checks evidence-grounded scoring, and reports defects.

For a student project, these roles may be performed by the same team member(s).

## Product Backlog
1. Accept a question, AI response, required reference answer, and optional source context.
2. Evaluate relevance, accuracy, hallucination risk, and completeness.
3. Produce an explainable overall verdict with supporting details.
4. Support CSV batch evaluation with row-level results and validation.
5. Provide batch progress, counts, filters, charts, and quality-trend views where evaluation history is available.
6. Export evaluation reports to PDF.
7. Provide setup instructions, automated tests, and deployment documentation.

## Milestone Plan
| Iteration | Focus | Acceptance criteria |
|---|---|---|
| M1 | Core evaluation pipeline and hallucination-detection assistance | A valid evaluation request returns structured evaluation results and a verdict. |
| M2 | Retrieval and evidence grounding | Retrieval can supply relevant context to the evaluation pipeline; missing or weak evidence is handled explicitly. |
| M3 | Completeness judgement, verdict logic, and batch workflow | Completeness is represented in results; batch input validation and row-level outcomes are available. |
| M4 | Separate Single and Batch dashboards, visual analytics, PDF export, and end-to-end validation | Dashboard metrics reflect real evaluation data; PDF export works; tests cover single and batch flows. |

The table describes the planned scope. Completion should be claimed only after the corresponding implementation and tests have been verified.

## Definition of Done
A feature is considered done when:
- Its acceptance criteria are met.
- Existing single-evaluation behavior remains functional.
- Invalid input produces a clear, safe error rather than a crash.
- Relevant automated tests pass.
- UI metrics and charts use actual returned evaluation data, not hard-coded demo values.
- Setup or behavior changes are documented.
- The change is reviewed and committed to the main branch.

## Testing and Review
Run the test suite from the repository root after installing dependencies:
```bash
python -m pip install -r requirements.txt
python -m pytest -q
```
If a test depends on a running API, start the backend in a separate terminal according to the README and then run that test. Record any known limitations and do not describe unexecuted tests as passing.

## Risks and Mitigations
- **Model download/start-up time:** Document initial setup and allow time for model initialization.
- **Uncertain evaluation scores:** Show evidence and explain that automated scores are decision support, not a guarantee of truth.
- **Batch data variability:** Validate CSV columns and row content; report invalid rows clearly.
- **Regression risk:** Keep single-evaluation and batch-evaluation tests and run them after changes.
- **Deployment constraints:** Verify model storage, file persistence, memory limits, and frontend-to-backend configuration on the selected host.

## Change Management
Use focused commits with descriptive messages. Keep secrets and local environment files out of Git. Do not commit generated batch history, local indexes, caches, virtual environments, or private evaluation data unless intentionally required and reviewed.
