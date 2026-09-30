# Evaluation Metrics and Scoring Methodology

This document details the evaluation dimensions, mathematical formulations, risk thresholds, and scoring scales utilized by the **AI Response Validation System**.

---

## 1. Core Scoring Philosophy

- **Unified Scale**: All evaluation dimensions are mapped to a standardized **0–100 scale**, where:
  - `100.0` represents optimal performance / complete alignment.
  - `0.0` represents failure / complete misalignment.
- **Independence of Dimensions**: Semantic similarity, factual accuracy, and hallucination are calculated as distinct orthogonal dimensions. A response may share high semantic overlap with a reference while asserting completely incorrect facts.

---

## 2. Evaluation Dimensions

### 2.1 Relevance (Weight: 25%)
- **Definition**: Measures how directly, purposefully, and completely the response answers the specific question asked.
- **Evaluation Mechanism**:
  - Semantic vector alignment between question embedding and response embedding.
  - Interrogative intent matching (checking whether questions asking *When*, *Who*, *Where*, *Why* receive corresponding temporal, entity, or causal explanations).
  - Keyword and key concept overlap.
- **Scale**:
  - `85.0 - 100.0`: Direct, comprehensive answer to the core question.
  - `65.0 - 84.9`: Answers the question with slight tangential or indirect commentary.
  - `40.0 - 64.9`: Weak topical overlap; partial responsiveness.
  - `< 40.0`: Unresponsive or completely off-topic.

### 2.2 Accuracy (Weight: 35%)
- **Definition**: Evaluates the factual consistency of the AI response compared to the verified ground truth reference answer and retrieved knowledge base evidence.
- **Evaluation Mechanism**:
  - Polarity and negation conflict analysis (detecting if reference refutes what AI affirms).
  - Entity contradiction checks (e.g. naming Sydney instead of Canberra).
  - Numerical and date verification (identifying conflicting years, counts, or measurements).
- **Penalties**:
  - Contradictions incur heavy penalties (-35.0 per verified contradiction).
- **Scale**:
  - `85.0 - 100.0`: High factual accuracy; completely consistent with reference.
  - `65.0 - 84.9`: Generally accurate with minor imprecise phrasing.
  - `50.0 - 64.9`: Notable factual discrepancies or unverified assertions.
  - `< 50.0`: Severe factual errors or direct contradictions.

### 2.3 Hallucination Detection (Weight: 25%)
- **Definition**: Evaluates the presence of unsupported, fabricated, or contradictory statements.
- **Two Metric Representation**:
  1. **Hallucination Risk Percentage (`percentage`)**:
     - `0.0%`: Completely supported and grounded in evidence.
     - `100.0%`: Entirely fabricated or contradictory.
  2. **Hallucination-Free Score (`score`)**:
     $$\text{Hallucination-Free Score} = 100.0 - \text{Hallucination Risk Percentage}$$
- **Risk Tiers**:
  | Risk Tier | Risk Percentage | Hallucination-Free Score | Description |
  |---|---|---|---|
  | **Low** | $0.0\% - 20.0\%$ | $80.0 - 100.0$ | Claims are thoroughly grounded in reference evidence. |
  | **Medium** | $20.1\% - 50.0\%$ | $50.0 - 79.9$ | Contains partially unverified statements or weak grounding. |
  | **High** | $> 50.0\%$ | $< 50.0$ | Significant unsupported or directly contradictory claims present. |

### 2.4 Completeness (Weight: 15%)
- **Definition**: Quantifies informational coverage and recall against the essential points established in the reference ground truth.
- **Evaluation Mechanism**:
  - Sentence-level semantic coverage.
  - Critical entity and keyword recall from the reference.
  - Specific identification of omitted context.
- **Scale**:
  - `85.0 - 100.0`: Full coverage of essential reference information.
  - `60.0 - 84.9`: Covers primary points but omits secondary context.
  - `< 60.0`: Omits critical factual elements necessary to answer the question.

### 2.5 Semantic Similarity (Informational Dimension)
- **Definition**: Cosine similarity between sentence embeddings of AI response and reference answer:
  $$\text{Similarity Percentage} = \frac{\mathbf{u} \cdot \mathbf{v}}{\|\mathbf{u}\| \|\mathbf{v}\|} \times 100$$
- **Distinction from Accuracy**:
  > [!IMPORTANT]
  > Semantic similarity measures lexical, syntactical, and topical alignment. A fabricated answer like *"Neil Armstrong walked on Mars in 1985"* achieves high semantic similarity to *"Neil Armstrong walked on the Moon in 1969"*, but possesses high hallucination and low accuracy.

---

## 3. Overall Verdict Calculation

The composite score synthesizes all dimensions according to their respective weights:

$$\text{Overall Score} = (0.25 \times \text{Relevance}) + (0.35 \times \text{Accuracy}) + (0.25 \times \text{Hallucination-Free Score}) + (0.15 \times \text{Completeness})$$

### Verdict Labels & Thresholds

| Overall Score | Verdict Label | System Recommendation |
|---|---|---|
| **$\ge 85.0$** | **Excellent** | Response meets high standards of factuality and completeness. Direct use recommended. |
| **$70.0 - 84.9$** | **Good** | Response is largely sound with minor gaps. Review suggested improvements. |
| **$50.0 - 69.9$** | **Needs Improvement** | Noticeable deficiencies or weak grounding. Adopting "Better Answer" recommended. |
| **$< 50.0$** | **Poor** | Severe factual contradictions or hallucinations. Substitute with grounded "Better Answer". |

---

## 4. Better Answer Comparison Data

When an AI response exhibits deficiencies (Accuracy < 85, Hallucination > 15%, or Completeness < 80), the system generates a **Better Answer** grounded strictly in the reference answer and retrieved evidence.

The API delivers structured comparison metrics designed for frontend visualization:
```json
{
  "reference_answer_score": 100.0,
  "better_answer_score": 93.8,
  "similarity_percentage": 92.4
}
```
This structured payload allows client-side dashboards to render comparison bar charts or radar graphs.
