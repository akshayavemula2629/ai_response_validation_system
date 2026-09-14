/**
 * Main Application Controller
 * Coordinates form input, validation, API dispatch, results dashboard rendering,
 * and interactive component interactions.
 */
import { CONFIG } from './config.js';
import { apiService } from './api.js';
import { ScoreGauge } from './components/gauge.js';
import { ComparisonChart } from './components/chart.js';

class App {
  constructor() {
    this.gauge = new ScoreGauge('overall-score-gauge');
    this.chart = new ComparisonChart('comparison-chart-canvas');
    this.lastEvaluation = null;

    this.initElements();
    this.bindEvents();
    this.checkBackendReadiness();
  }

  initElements() {
    // Form elements
    this.form = document.getElementById('evaluation-form');
    this.questionInput = document.getElementById('input-question');
    this.aiResponseInput = document.getElementById('input-ai-response');
    this.referenceAnswerInput = document.getElementById('input-reference-answer');
    this.sourceDocInput = document.getElementById('input-source-doc');
    this.case2Toggle = document.getElementById('toggle-case2-kb');
    this.refAnswerRequiredStar = document.getElementById('ref-required-star');
    this.refModeBadge = document.getElementById('ref-mode-badge');
    this.submitBtn = document.getElementById('btn-evaluate');
    this.btnText = document.getElementById('btn-text');
    this.btnSpinner = document.getElementById('btn-spinner');
    this.errorAlert = document.getElementById('form-error-alert');
    this.errorAlertText = document.getElementById('form-error-text');

    // Dashboard sections
    this.resultsSection = document.getElementById('results-dashboard');
    this.verdictSummaryText = document.getElementById('verdict-summary-text');
    this.originalResponseText = document.getElementById('original-response-text');
    this.comparisonRefText = document.getElementById('comparison-ref-text');
    this.comparisonBetterText = document.getElementById('comparison-better-text');
    this.betterReasonText = document.getElementById('better-answer-reason-text');

    // M2 Judge Badges & Categories
    this.relevanceRating = document.getElementById('metric-relevance-rating');
    this.relevanceCategory = document.getElementById('metric-relevance-category');
    this.accuracyRating = document.getElementById('metric-accuracy-rating');
    this.accuracyCategory = document.getElementById('metric-accuracy-category');
    this.accuracySource = document.getElementById('metric-accuracy-source');

    // Hallucination Dashboard & Claim Breakdown Elements
    this.hallucinationRiskBadge = document.getElementById('hallucination-risk-badge');
    this.hallucinationPctText = document.getElementById('hallucination-pct-text');
    this.hallucinationExplanation = document.getElementById('hallucination-explanation');
    this.hallucinationIssuesList = document.getElementById('hallucination-issues-list');
    this.halTotalClaims = document.getElementById('hallucination-total-claims');
    this.halSupportedClaims = document.getElementById('hallucination-supported-claims');
    this.halUnsupportedClaims = document.getElementById('hallucination-unsupported-claims');
    this.halContradictedClaims = document.getElementById('hallucination-contradicted-claims');
    this.halClaimsList = document.getElementById('hallucination-claims-list');

    this.evidenceListContainer = document.getElementById('retrieved-evidence-container');
    this.evidenceCountBadge = document.getElementById('evidence-count-badge');
    this.backendStatusPill = document.getElementById('backend-status-pill');
  }

  bindEvents() {
    // Form submission
    if (this.form) {
      this.form.addEventListener('submit', (e) => this.handleSubmit(e));
    }

    // Case 2 Toggle
    if (this.case2Toggle) {
      this.case2Toggle.addEventListener('change', () => this.handleCase2Toggle());
    }

    // Quick demo preset buttons
    const presetButtons = document.querySelectorAll('[data-sample-preset]');
    presetButtons.forEach(btn => {
      btn.addEventListener('click', (e) => {
        const presetKey = e.currentTarget.getAttribute('data-sample-preset');
        this.loadSampleData(presetKey);
      });
    });

    // Clear form error on typing
    [this.questionInput, this.aiResponseInput, this.referenceAnswerInput].forEach(input => {
      if (input) {
        input.addEventListener('input', () => this.hideError());
      }
    });
  }

  /**
   * Toggles required attribute and visual helper when Case 2 mode is active.
   */
  handleCase2Toggle() {
    const isCase2 = Boolean(this.case2Toggle && this.case2Toggle.checked);
    if (isCase2) {
      this.referenceAnswerInput?.removeAttribute('required');
      if (this.referenceAnswerInput) {
        this.referenceAnswerInput.placeholder = 'Optional in Case 2: Knowledge Base chunks will be used as primary ground truth.';
      }
      this.refAnswerRequiredStar?.classList.add('hidden');
      this.refModeBadge?.classList.remove('hidden');
    } else {
      this.referenceAnswerInput?.setAttribute('required', 'true');
      if (this.referenceAnswerInput) {
        this.referenceAnswerInput.placeholder = 'Enter the trusted/reference answer...';
      }
      this.refAnswerRequiredStar?.classList.remove('hidden');
      this.refModeBadge?.classList.add('hidden');
    }
    this.hideError();
  }

  /**
   * Loads sample data for quick live demonstrations.
   */
  loadSampleData(presetKey) {
    const sample = CONFIG.SAMPLE_DATA[presetKey];
    if (!sample) return;

    this.questionInput.value = sample.question;
    this.aiResponseInput.value = sample.ai_response;
    this.referenceAnswerInput.value = sample.reference_answer || '';
    this.sourceDocInput.value = sample.source_document || '';

    if (sample.use_knowledge_base_only) {
      if (this.case2Toggle) this.case2Toggle.checked = true;
    } else {
      if (this.case2Toggle) this.case2Toggle.checked = false;
    }
    this.handleCase2Toggle();

    this.hideError();
    // Smooth scroll to form
    this.form.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }

  /**
   * Periodically checks if backend is active.
   */
  async checkBackendReadiness() {
    const isHealthy = await apiService.checkHealth();
    if (this.backendStatusPill) {
      if (isHealthy) {
        this.backendStatusPill.className = 'status-pill status-online';
        this.backendStatusPill.innerHTML = '<span class="status-dot"></span> Backend Ready';
      } else {
        this.backendStatusPill.className = 'status-pill status-offline';
        this.backendStatusPill.innerHTML = '<span class="status-dot"></span> Backend Offline';
      }
    }
  }

  /**
   * Validates form inputs according to requirements.
   */
  validateInputs() {
    const question = this.questionInput?.value?.trim() || '';
    const aiResponse = this.aiResponseInput?.value?.trim() || '';
    const referenceAnswer = this.referenceAnswerInput?.value?.trim() || '';
    const isCase2 = Boolean(this.case2Toggle && this.case2Toggle.checked);

    if (!question) {
      this.showError('Please enter the question');
      this.questionInput?.focus();
      return null;
    }

    if (!aiResponse) {
      this.showError('Please enter the AI-generated response');
      this.aiResponseInput?.focus();
      return null;
    }

    if (!isCase2 && !referenceAnswer) {
      this.showError('Please enter the reference answer');
      this.referenceAnswerInput?.focus();
      return null;
    }

    return {
      question,
      ai_response: aiResponse,
      reference_answer: referenceAnswer,
      source_document: this.sourceDocInput?.value?.trim() || null,
      use_knowledge_base_only: isCase2
    };
  }

  showError(message) {
    if (this.errorAlert && this.errorAlertText) {
      this.errorAlertText.textContent = message;
      this.errorAlert.classList.remove('hidden');
      this.errorAlert.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }

  hideError() {
    if (this.errorAlert) {
      this.errorAlert.classList.add('hidden');
    }
  }

  setLoading(isLoading) {
    if (!this.submitBtn) return;
    this.submitBtn.disabled = isLoading;
    if (isLoading) {
      this.btnText.textContent = 'Analyzing Response...';
      this.btnSpinner.classList.remove('hidden');
      this.submitBtn.classList.add('btn-loading');
    } else {
      this.btnText.textContent = 'Evaluate Response';
      this.btnSpinner.classList.add('hidden');
      this.submitBtn.classList.remove('btn-loading');
    }
  }

  async handleSubmit(e) {
    e.preventDefault();
    this.hideError();

    const payload = this.validateInputs();
    if (!payload) return;

    this.setLoading(true);

    try {
      const result = await apiService.evaluateResponse(payload);
      this.lastEvaluation = result;
      this.renderResults(result);
    } catch (err) {
      this.showError(err.message || 'An error occurred while evaluating the response.');
    } finally {
      this.setLoading(false);
    }
  }

  /**
   * Dynamically renders the complete results dashboard.
   */
  renderResults(data) {
    if (!data || !data.evaluation) return;

    // Show results section
    this.resultsSection.classList.remove('hidden');

    const evalData = data.evaluation;

    // 1. Render Overall Score & Circular Gauge
    this.gauge.render(evalData.overall_score, evalData.verdict);
    if (this.verdictSummaryText) {
      this.verdictSummaryText.textContent = evalData.summary || '';
    }

    // 2. Render Metric Cards
    this.renderRelevanceCard(evalData.relevance, data.relevance_judge);
    this.renderAccuracyCard(evalData.accuracy, data.accuracy_judge);
    this.renderMetricCard('completeness', evalData.completeness);
    this.renderSimilarityMetric(evalData.similarity);
    this.renderHallucinationMetricCard(evalData.hallucination);

    // 3. Render Answer Quality Comparison Chart
    this.chart.render(data.comparison);

    // 4. Render Answer Comparisons
    if (this.originalResponseText) {
      this.originalResponseText.textContent = data.original_response || '';
    }
    if (this.comparisonRefText) {
      this.comparisonRefText.textContent = data.reference_answer || '';
    }
    if (this.comparisonBetterText) {
      this.comparisonBetterText.textContent = data.better_answer || data.reference_answer || '';
    }
    if (this.betterReasonText) {
      this.betterReasonText.textContent = data.better_answer_reason || 'The answer is grounded strictly in reference truth.';
    }

    // 5. Render Dedicated Hallucination Analysis Card (with M2 atomic claims breakdown)
    this.renderHallucinationAnalysis(evalData.hallucination, data.hallucination_judge);

    // 6. Render Retrieved Evidence
    this.renderRetrievedEvidence(data.retrieved_evidence);

    // Smooth scroll to results
    setTimeout(() => {
      this.resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 100);
  }

  renderRelevanceCard(metricData, relJudge) {
    this.renderMetricCard('relevance', metricData);

    if (relJudge && this.relevanceRating) {
      this.relevanceRating.textContent = `${relJudge.score} / 5`;
    }
    if (relJudge && this.relevanceCategory) {
      this.relevanceCategory.textContent = relJudge.category || 'Relevant';
    }
  }

  renderAccuracyCard(metricData, accJudge) {
    this.renderMetricCard('accuracy', metricData);

    if (accJudge && this.accuracyRating) {
      this.accuracyRating.textContent = `${accJudge.score} / 5`;
    }
    if (accJudge && this.accuracyCategory) {
      this.accuracyCategory.textContent = accJudge.category || 'Correct';
    }
    if (accJudge && this.accuracySource) {
      this.accuracySource.textContent = `Source: ${accJudge.evidence_source || 'Reference Answer'}`;
      if (accJudge.evidence_source === 'Knowledge Base Retrieval') {
        this.accuracySource.className = 'badge-pill badge-source tag-source-kb';
      } else {
        this.accuracySource.className = 'badge-pill badge-source';
      }
    }
  }

  renderMetricCard(dimension, metricData) {
    const scoreVal = Number(metricData?.score) || 0;
    const scoreEl = document.getElementById(`metric-${dimension}-score`);
    const barEl = document.getElementById(`metric-${dimension}-bar`);
    const descEl = document.getElementById(`metric-${dimension}-desc`);

    if (scoreEl) scoreEl.textContent = `${scoreVal.toFixed(1)}%`;
    if (barEl) {
      barEl.style.width = '0%';
      requestAnimationFrame(() => {
        barEl.style.transition = 'width 1s cubic-bezier(0.16, 1, 0.3, 1)';
        barEl.style.width = `${scoreVal}%`;
      });
    }
    if (descEl) descEl.textContent = metricData?.explanation || '';
  }

  renderSimilarityMetric(simData) {
    const pct = Number(simData?.percentage) || 0;
    const scoreEl = document.getElementById('metric-similarity-score');
    const barEl = document.getElementById('metric-similarity-bar');
    const descEl = document.getElementById('metric-similarity-desc');

    if (scoreEl) scoreEl.textContent = `${pct.toFixed(1)}%`;
    if (barEl) {
      barEl.style.width = '0%';
      requestAnimationFrame(() => {
        barEl.style.transition = 'width 1s cubic-bezier(0.16, 1, 0.3, 1)';
        barEl.style.width = `${pct}%`;
      });
    }
    if (descEl) descEl.textContent = simData?.explanation || '';
  }

  renderHallucinationMetricCard(hallData) {
    const pct = Number(hallData?.percentage) || 0;
    const scoreEl = document.getElementById('metric-hallucination-score');
    const badgeEl = document.getElementById('metric-hallucination-level');
    const barEl = document.getElementById('metric-hallucination-bar');
    const descEl = document.getElementById('metric-hallucination-desc');

    if (scoreEl) scoreEl.textContent = `${pct.toFixed(1)}%`;
    if (badgeEl) {
      badgeEl.textContent = `${hallData?.risk_level || 'Low'} Risk`;
      badgeEl.className = `badge-pill risk-${String(hallData?.risk_level || 'low').toLowerCase()}`;
    }
    if (barEl) {
      barEl.style.width = '0%';
      requestAnimationFrame(() => {
        barEl.style.transition = 'width 1s cubic-bezier(0.16, 1, 0.3, 1)';
        barEl.style.width = `${pct}%`;
      });
    }
    if (descEl) descEl.textContent = hallData?.explanation || '';
  }

  renderHallucinationAnalysis(hallData, hallJudge) {
    if (!hallData) return;

    const risk = hallData.risk_level || 'Low';
    const pct = Number(hallData.percentage) || 0;

    if (this.hallucinationRiskBadge) {
      this.hallucinationRiskBadge.textContent = `${risk} Risk`;
      this.hallucinationRiskBadge.className = `badge-pill badge-large risk-${risk.toLowerCase()}`;
    }
    if (this.hallucinationPctText) {
      this.hallucinationPctText.textContent = `${pct.toFixed(1)}%`;
    }
    if (this.hallucinationExplanation) {
      this.hallucinationExplanation.textContent = hallData.explanation || '';
    }

    // Render Milestone 2 Claim Summary Counters
    if (hallJudge) {
      if (this.halTotalClaims) this.halTotalClaims.textContent = hallJudge.total_claims || 0;
      if (this.halSupportedClaims) this.halSupportedClaims.textContent = hallJudge.supported_claims || 0;
      if (this.halUnsupportedClaims) this.halUnsupportedClaims.textContent = hallJudge.unsupported_claims || 0;
      if (this.halContradictedClaims) this.halContradictedClaims.textContent = hallJudge.contradicted_claims || 0;

      // Render Atomic Claims Breakdown Cards
      if (this.halClaimsList) {
        const claims = hallJudge.claims_breakdown || [];
        if (claims.length === 0) {
          this.halClaimsList.innerHTML = `<p style="color: var(--text-muted); font-size: 0.85rem;">No discrete claims evaluated.</p>`;
        } else {
          this.halClaimsList.innerHTML = claims.map(c => {
            const statusClass = c.status === 'Supported' ? 'status-sup' : (c.status === 'Contradicted' ? 'status-contra' : 'status-unsup');
            const cardClass = c.status === 'Supported' ? 'claim-card-supported' : (c.status === 'Contradicted' ? 'claim-card-contradicted' : 'claim-card-unsupported');
            const icon = c.status === 'Supported' ? '✓' : (c.status === 'Contradicted' ? '✕' : '⚠');
            const conf = Math.round((c.confidence || 0.9) * 100);

            return `
              <div class="claim-card ${cardClass}">
                <div class="claim-card-top-row">
                  <div class="claim-text">"${this.escapeHtml(c.claim)}"</div>
                  <div class="claim-badge-group">
                    <span class="badge-claim-status ${statusClass}">${icon} ${this.escapeHtml(c.status)}</span>
                    <span class="claim-confidence-tag">${conf}% Conf</span>
                  </div>
                </div>
                <div class="claim-explanation-text">${this.escapeHtml(c.explanation || '')}</div>
                ${c.evidence ? `<div class="claim-evidence-snippet">Evidence: "${this.escapeHtml(c.evidence)}"</div>` : ''}
              </div>
            `;
          }).join('');
        }
      }
    }

    // Render Issue Bullet Points
    if (this.hallucinationIssuesList) {
      const issues = hallData.issues || [];
      if (issues.length === 0) {
        this.hallucinationIssuesList.innerHTML = `
          <div class="clean-issue-banner">
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
              <path d="M10 18C14.4183 18 18 14.4183 18 10C18 5.58172 14.4183 2 10 2C5.58172 2 2 5.58172 2 10C2 14.4183 5.58172 18 10 18Z" stroke="#10B981" stroke-width="2"/>
              <path d="M6.5 10L9 12.5L13.5 7.5" stroke="#10B981" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
            <span>All evaluated claims are grounded in verified evidence. No hallucinations detected.</span>
          </div>
        `;
      } else {
        this.hallucinationIssuesList.innerHTML = `
          <div class="issues-container">
            <div class="issues-title">Detected Problematic Claims (${issues.length}):</div>
            <ul class="issues-bullet-list">
              ${issues.map(iss => `
                <li class="issue-item">
                  <span class="issue-icon">⚠️</span>
                  <span class="issue-text">${this.escapeHtml(iss)}</span>
                </li>
              `).join('')}
            </ul>
          </div>
        `;
      }
    }
  }

  renderRetrievedEvidence(evidenceList) {
    if (!this.evidenceListContainer) return;

    const list = evidenceList || [];
    if (this.evidenceCountBadge) {
      this.evidenceCountBadge.textContent = `${list.length} item${list.length === 1 ? '' : 's'}`;
    }

    if (list.length === 0) {
      this.evidenceListContainer.innerHTML = `
        <div class="empty-evidence-box">
          No external knowledge-base chunks retrieved for this evaluation.
        </div>
      `;
      return;
    }

    this.evidenceListContainer.innerHTML = list.map((item, index) => {
      const sim = (Number(item.similarity_score) * 100).toFixed(1);
      const isExpanded = index === 0; // First item expanded by default
      return `
        <div class="evidence-card ${isExpanded ? 'is-open' : ''}" data-evidence-index="${index}">
          <div class="evidence-header" onclick="this.parentElement.classList.toggle('is-open')">
            <div class="evidence-header-left">
              <span class="evidence-source-tag">${this.escapeHtml(item.source || 'Knowledge Base')}</span>
              <span class="evidence-sim-tag">Relevance: ${sim}%</span>
            </div>
            <div class="evidence-toggle-btn">
              <svg class="chevron-icon" width="16" height="16" viewBox="0 0 16 16" fill="none">
                <path d="M4 6L8 10L12 6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
            </div>
          </div>
          <div class="evidence-body">
            <div class="evidence-content-box">${this.escapeHtml(item.content || '')}</div>
            <div class="evidence-meta-row">
              <span class="evidence-chunk-id">Chunk ID: ${this.escapeHtml(item.chunk_id || 'N/A')}</span>
            </div>
          </div>
        </div>
      `;
    }).join('');
  }

  escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }
}

// Instantiate on DOM ready
document.addEventListener('DOMContentLoaded', () => {
  window.app = new App();
});
