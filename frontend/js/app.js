/**
 * Main Application Controller — Milestone 3
 * Coordinates single evaluation, batch CSV processing, real multi-agent progress,
 * metrics line charts, verdict arbitration, completeness breakdown, and interactive inspections.
 */
import { CONFIG } from './config.js';
import { apiService } from './api.js';
import { ScoreGauge } from './components/gauge.js';
import { ComparisonChart, MetricsLineChart } from './components/chart.js';

class App {
  constructor() {
    this.gauge = new ScoreGauge('overall-score-gauge');
    this.comparisonChart = new ComparisonChart('comparison-chart-canvas');
    this.lineChart = new MetricsLineChart('metrics-line-chart-canvas');
    
    this.lastEvaluation = null;
    this.batchResults = [];
    this.selectedBatchFile = null;

    this.initElements();
    this.bindEvents();
    this.checkBackendReadiness();
  }

  initElements() {
    // Mode Switcher Tabs
    this.tabSingle = document.getElementById('tab-single-mode');
    this.tabBatch = document.getElementById('tab-batch-mode');
    this.evalFormCard = document.getElementById('evaluation-form-card');
    this.batchSection = document.getElementById('batch-evaluation-section');

    // Single Evaluation Form Elements
    this.form = document.getElementById('evaluation-form');
    this.questionInput = document.getElementById('input-question');
    this.aiResponseInput = document.getElementById('input-ai-response');
    this.referenceAnswerInput = document.getElementById('input-reference-answer');
    this.sourceDocInput = document.getElementById('input-source-doc');
    this.submitBtn = document.getElementById('btn-evaluate');
    this.btnText = document.getElementById('btn-text');
    this.btnSpinner = document.getElementById('btn-spinner');
    this.errorAlert = document.getElementById('form-error-alert');
    this.errorAlertText = document.getElementById('form-error-text');

    // Progress Tracker Elements
    this.progressCard = document.getElementById('evaluation-progress-card');
    this.progressBar = document.getElementById('progress-bar');
    this.progressPct = document.getElementById('progress-pct');
    this.progressCurrentStage = document.getElementById('progress-current-stage');
    this.stageSteps = [1, 2, 3, 4, 5].map(i => document.getElementById(`stage-step-${i}`));

    // Single Results Dashboard Elements
    this.resultsSection = document.getElementById('results-dashboard');
    this.verdictSummaryText = document.getElementById('verdict-summary-text');
    this.originalResponseText = document.getElementById('original-response-text');
    this.comparisonRefText = document.getElementById('comparison-ref-text');
    this.comparisonBetterText = document.getElementById('comparison-better-text');
    this.betterReasonText = document.getElementById('better-answer-reason-text');

    // M3 Verdict Agent Elements
    this.verdictBadge = document.getElementById('verdict-decision-badge');
    this.verdictWeightedScore = document.getElementById('verdict-weighted-score');
    this.verdictOverrideAlert = document.getElementById('verdict-override-alert');
    this.verdictReasoningText = document.getElementById('verdict-reasoning-text');
    this.verdictMajorIssuesBox = document.getElementById('verdict-major-issues-box');
    this.verdictMajorIssuesList = document.getElementById('verdict-major-issues-list');

    // M3 Completeness Judge Elements
    this.completenessBadge = document.getElementById('completeness-score-badge');
    this.compAddressedCount = document.getElementById('completeness-addressed-count');
    this.compPartialCount = document.getElementById('completeness-partial-count');
    this.compMissingCount = document.getElementById('completeness-missing-count');
    this.compAspectsList = document.getElementById('completeness-aspects-list');
    this.compReasoningText = document.getElementById('completeness-reasoning-text');

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

    // Evidence and Header
    this.evidenceListContainer = document.getElementById('retrieved-evidence-container');
    this.evidenceCountBadge = document.getElementById('evidence-count-badge');
    this.backendStatusPill = document.getElementById('backend-status-pill');

    // Batch Evaluation Elements
    this.batchDropzone = document.getElementById('batch-dropzone');
    this.batchFileInput = document.getElementById('batch-file-input');
    this.batchSelectedFile = document.getElementById('batch-selected-file');
    this.batchFilename = document.getElementById('batch-filename');
    this.batchFilesize = document.getElementById('batch-filesize');
    this.btnCancelFile = document.getElementById('btn-cancel-file');
    this.btnProcessBatch = document.getElementById('btn-process-batch');
    this.batchSpinner = document.getElementById('batch-spinner');
    this.batchBtnText = document.getElementById('batch-btn-text');
    this.batchProgressContainer = document.getElementById('batch-progress-container');
    this.batchProgressBar = document.getElementById('batch-progress-bar');
    this.batchProgressPct = document.getElementById('batch-progress-pct');
    this.batchProgressStatus = document.getElementById('batch-progress-status');
    this.batchErrorAlert = document.getElementById('batch-error-alert');
    this.batchErrorText = document.getElementById('batch-error-text');

    // Batch Results Dashboard Elements
    this.batchResultsDashboard = document.getElementById('batch-results-dashboard');
    this.batchStatTotal = document.getElementById('batch-stat-total');
    this.batchStatValid = document.getElementById('batch-stat-valid');
    this.batchStatAvgScore = document.getElementById('batch-stat-avg-score');
    this.batchStatPass = document.getElementById('batch-stat-pass');
    this.batchStatNi = document.getElementById('batch-stat-ni');
    this.batchStatFail = document.getElementById('batch-stat-fail');
    this.batchStatAvgHal = document.getElementById('batch-stat-avg-hallucination');
    this.batchStatHighRisk = document.getElementById('batch-stat-high-risk-count');
    this.batchTableBody = document.getElementById('batch-table-body');

    // Modal Drawer Elements
    this.batchDetailModal = document.getElementById('batch-detail-modal');
    this.modalContentArea = document.getElementById('modal-content-area');
    this.btnCloseModal = document.getElementById('btn-close-modal');
  }

  bindEvents() {
    // Mode Switcher Tabs
    if (this.tabSingle && this.tabBatch) {
      this.tabSingle.addEventListener('click', () => this.switchMode('single'));
      this.tabBatch.addEventListener('click', () => this.switchMode('batch'));
    }

    // Form submission
    if (this.form) {
      this.form.addEventListener('submit', (e) => this.handleSubmit(e));
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

    // Batch Upload Events
    if (this.batchDropzone) {
      this.batchDropzone.addEventListener('click', () => this.batchFileInput?.click());
      this.batchDropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        this.batchDropzone.classList.add('dragover');
      });
      this.batchDropzone.addEventListener('dragleave', () => {
        this.batchDropzone.classList.remove('dragover');
      });
      this.batchDropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        this.batchDropzone.classList.remove('dragover');
        if (e.dataTransfer?.files?.length) {
          this.handleFileSelect(e.dataTransfer.files[0]);
        }
      });
    }

    if (this.batchFileInput) {
      this.batchFileInput.addEventListener('change', (e) => {
        if (e.target?.files?.length) {
          this.handleFileSelect(e.target.files[0]);
        }
      });
    }

    if (this.btnCancelFile) {
      this.btnCancelFile.addEventListener('click', () => this.clearBatchFile());
    }

    if (this.btnProcessBatch) {
      this.btnProcessBatch.addEventListener('click', () => this.handleBatchSubmit());
    }

    // Modal Drawer Events
    if (this.btnCloseModal) {
      this.btnCloseModal.addEventListener('click', () => this.closeModal());
    }
    if (this.batchDetailModal) {
      this.batchDetailModal.addEventListener('click', (e) => {
        if (e.target === this.batchDetailModal) {
          this.closeModal();
        }
      });
    }

    // Escape key closes modal
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && this.batchDetailModal && !this.batchDetailModal.classList.contains('hidden')) {
        this.closeModal();
      }
    });
  }

  /**
   * Switch between Single Evaluation and Batch Evaluation modes.
   */
  switchMode(mode) {
    if (mode === 'single') {
      this.tabSingle?.classList.add('active');
      this.tabSingle?.setAttribute('aria-selected', 'true');
      this.tabBatch?.classList.remove('active');
      this.tabBatch?.setAttribute('aria-selected', 'false');

      this.evalFormCard?.classList.remove('hidden');
      this.batchSection?.classList.add('hidden');

      if (this.lastEvaluation) {
        this.resultsSection?.classList.remove('hidden');
      }
    } else {
      this.tabBatch?.classList.add('active');
      this.tabBatch?.setAttribute('aria-selected', 'true');
      this.tabSingle?.classList.remove('active');
      this.tabSingle?.setAttribute('aria-selected', 'false');

      this.evalFormCard?.classList.add('hidden');
      this.progressCard?.classList.add('hidden');
      this.resultsSection?.classList.add('hidden');
      this.batchSection?.classList.remove('hidden');
    }
  }

  /**
   * Loads sample data for quick demonstrations.
   */
  loadSampleData(presetKey) {
    const sample = CONFIG.SAMPLE_DATA[presetKey];
    if (!sample) return;

    if (this.questionInput) this.questionInput.value = sample.question || '';
    if (this.aiResponseInput) this.aiResponseInput.value = sample.ai_response || '';
    if (this.referenceAnswerInput) this.referenceAnswerInput.value = sample.reference_answer || '';
    if (this.sourceDocInput) this.sourceDocInput.value = sample.source_document || '';

    this.hideError();
    this.switchMode('single');
    this.form?.scrollIntoView({ behavior: 'smooth', block: 'center' });
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
   * Validates form inputs. Reference Answer is strictly mandatory in Milestone 3.
   */
  validateInputs() {
    const question = this.questionInput?.value?.trim() || '';
    const aiResponse = this.aiResponseInput?.value?.trim() || '';
    const referenceAnswer = this.referenceAnswerInput?.value?.trim() || '';

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

    if (!referenceAnswer) {
      this.showError('Reference Answer is required for evaluation.');
      this.referenceAnswerInput?.focus();
      return null;
    }

    return {
      question,
      ai_response: aiResponse,
      reference_answer: referenceAnswer,
      source_document: this.sourceDocInput?.value?.trim() || null
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
      this.btnText.textContent = 'Evaluating Response...';
      this.btnSpinner.classList.remove('hidden');
      this.submitBtn.classList.add('btn-loading');
    } else {
      this.btnText.textContent = 'Evaluate Response';
      this.btnSpinner.classList.add('hidden');
      this.submitBtn.classList.remove('btn-loading');
    }
  }

  /**
   * Updates visual progress stages truthfully.
   */
  setProgressStage(activeStageIndex, label, pct = null) {
    if (!this.progressCard) return;
    this.progressCard.classList.remove('hidden');

    if (this.progressCurrentStage) {
      this.progressCurrentStage.textContent = label;
    }

    if (pct !== null && this.progressPct && this.progressBar) {
      const rounded = Math.round(pct);
      this.progressPct.textContent = `${rounded}%`;
      this.progressBar.style.width = `${rounded}%`;
    }

    const stageNames = [
      '1. Relevance',
      '2. Accuracy',
      '3. Hallucination Detection',
      '4. Completeness',
      '5. Verdict'
    ];

    this.stageSteps.forEach((stepEl, idx) => {
      if (!stepEl) return;
      const icon = stepEl.querySelector('.stage-icon');
      const textSpan = stepEl.querySelector('span:last-child');
      const stageNum = stageNames[idx] || `Stage ${idx + 1}`;

      if (idx < activeStageIndex) {
        stepEl.className = 'stage-item stage-completed';
        if (icon) icon.textContent = '✓';
        if (textSpan) textSpan.textContent = stageNum;
      } else if (idx === activeStageIndex && activeStageIndex < 5) {
        stepEl.className = 'stage-item stage-active';
        if (icon) icon.textContent = '⟳';
        if (textSpan) textSpan.textContent = stageNum;
      } else if (activeStageIndex >= 5) {
        stepEl.className = 'stage-item stage-completed';
        if (icon) icon.textContent = '✓';
        if (textSpan) textSpan.textContent = stageNum;
      } else {
        stepEl.className = 'stage-item stage-pending';
        if (icon) icon.textContent = '○';
        if (textSpan) textSpan.textContent = stageNum;
      }
    });
  }

  handleStageProgress(event) {
    if (!event) return;

    if (event.event === 'STAGE_STARTED') {
      const stageIdx = (event.stage_index || 1) - 1;
      const pct = event.percentage !== undefined ? event.percentage : stageIdx * 20;
      this.setProgressStage(stageIdx, `Stage ${event.stage_index} of 5: Running ${event.stage_name || ''}...`, pct);
    } else if (event.event === 'STAGE_COMPLETED') {
      const stageIdx = (event.stage_index || 1) - 1;
      const pct = event.percentage !== undefined ? event.percentage : (stageIdx + 1) * 20;
      this.setProgressStage(stageIdx + 1, `Completed ${event.stage_name || ''}`, pct);
    } else if (event.event === 'EVALUATION_COMPLETED') {
      this.setProgressStage(5, '✓ Evaluation Complete', 100);
    }
  }

  async handleSubmit(e) {
    e.preventDefault();
    this.hideError();

    const payload = this.validateInputs();
    if (!payload) return;

    this.setLoading(true);
    this.resultsSection?.classList.add('hidden');

    // Stage 1: Validation passed, now running pipeline
    this.setProgressStage(0, 'Stage 1 of 5: Running Relevance...', 0);
    this.progressCard?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

    try {
      const result = await apiService.evaluateResponseStream(payload, (stageEvent) => {
        this.handleStageProgress(stageEvent);
      });
      this.lastEvaluation = result;

      // Mark all stages complete truthfully when backend completes
      this.setProgressStage(5, '✓ Evaluation Complete', 100);

      setTimeout(() => {
        this.renderResults(result);
      }, 400);

    } catch (err) {
      this.progressCard?.classList.add('hidden');
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

    this.resultsSection.classList.remove('hidden');
    const evalData = data.evaluation;

    // 1. Render Overall Score & Circular Gauge with Authoritative Milestone 3 Verdict
    const authoritativeVerdict = data.verdict_judge?.final_verdict || evalData.verdict;
    const authoritativeScore = data.verdict_judge?.weighted_score !== undefined ? data.verdict_judge.weighted_score : evalData.overall_score;
    this.gauge.render(authoritativeScore, authoritativeVerdict);
    if (this.verdictSummaryText) {
      this.verdictSummaryText.textContent = data.verdict_judge?.consolidated_reasoning || data.verdict_judge?.verdict_reasoning || evalData.summary || '';
    }

    // 2. Render M3 Verdict Agent Decision Card
    this.renderVerdictCard(data.verdict_judge, evalData.overall_score);

    // 3. Render 5 Metric Cards
    this.renderRelevanceCard(evalData.relevance, data.relevance_judge);
    this.renderAccuracyCard(evalData.accuracy, data.accuracy_judge);
    this.renderMetricCard('completeness', evalData.completeness);
    this.renderSimilarityMetric(evalData.similarity);
    this.renderHallucinationMetricCard(evalData.hallucination);

    // 4. Render M3 Completeness Judge Breakdown Card
    this.renderCompletenessCard(data.completeness_judge, evalData.completeness);

    // 5. Render M3 Evaluation Metrics Profile (Line Chart) with genuine calculated backend metrics
    this.lineChart.render({
      relevance: evalData.relevance,
      accuracy: evalData.accuracy,
      hallucination: evalData.hallucination,
      completeness: data.completeness_judge || evalData.completeness,
      overall_score: data.verdict_judge ? data.verdict_judge.weighted_score : evalData.overall_score,
      similarity: evalData.similarity
    });

    // 6. Render M1 Answer Quality Comparison Bar Chart
    this.comparisonChart.render(data.comparison);

    // 7. Render Side-by-Side Answer Comparisons
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

    // 8. Render Dedicated Hallucination Analysis Card (with M2 atomic claims breakdown)
    this.renderHallucinationAnalysis(evalData.hallucination, data.hallucination_judge);

    // 9. Render Retrieved Evidence
    this.renderRetrievedEvidence(data.retrieved_evidence);

    // Smooth scroll to results
    setTimeout(() => {
      this.resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 100);
  }

  /**
   * Renders Verdict Agent arbitration results.
   */
  renderVerdictCard(verdictJudge, fallbackScore) {
    if (!verdictJudge) return;

    const verdict = verdictJudge.final_verdict || 'PASS';
    const score = Number(verdictJudge.weighted_score !== undefined ? verdictJudge.weighted_score : fallbackScore) || 0.0;

    if (this.verdictBadge) {
      this.verdictBadge.textContent = verdict;
      if (verdict === 'PASS') {
        this.verdictBadge.className = 'verdict-badge-large badge-pass';
      } else if (verdict === 'NEEDS IMPROVEMENT') {
        this.verdictBadge.className = 'verdict-badge-large badge-needs-improvement';
      } else {
        this.verdictBadge.className = 'verdict-badge-large badge-fail';
      }
    }

    if (this.verdictWeightedScore) {
      this.verdictWeightedScore.textContent = score.toFixed(1);
    }

    if (this.verdictOverrideAlert) {
      if (verdictJudge.severe_hallucination_override) {
        this.verdictOverrideAlert.classList.remove('hidden');
      } else {
        this.verdictOverrideAlert.classList.add('hidden');
      }
    }

    if (this.verdictReasoningText) {
      this.verdictReasoningText.textContent = verdictJudge.consolidated_reasoning || '';
    }

    if (this.verdictMajorIssuesBox && this.verdictMajorIssuesList) {
      const issues = verdictJudge.major_issues || [];
      if (issues.length > 0) {
        this.verdictMajorIssuesBox.classList.remove('hidden');
        this.verdictMajorIssuesList.innerHTML = issues.map(iss => `
          <div class="issue-item">
            <span>⚠️</span>
            <span>${this.escapeHtml(iss)}</span>
          </div>
        `).join('');
      } else {
        this.verdictMajorIssuesBox.classList.add('hidden');
        this.verdictMajorIssuesList.innerHTML = '';
      }
    }
  }

  /**
   * Renders Completeness Judge granular 3-tier aspect classification.
   */
  renderCompletenessCard(compJudge, fallbackComp) {
    if (!compJudge) return;

    const score = Number(compJudge.score !== undefined ? compJudge.score : fallbackComp?.score) || 0.0;
    if (this.completenessBadge) {
      this.completenessBadge.textContent = `${score.toFixed(1)}%`;
    }

    const addressed = compJudge.addressed_aspects || [];
    const partial = compJudge.partially_addressed_aspects || [];
    const missing = compJudge.missing_aspects || [];

    if (this.compAddressedCount) this.compAddressedCount.textContent = addressed.length;
    if (this.compPartialCount) this.compPartialCount.textContent = partial.length;
    if (this.compMissingCount) this.compMissingCount.textContent = missing.length;

    if (this.compAspectsList) {
      let html = '';

      if (addressed.length > 0) {
        html += `
          <div>
            <div class="aspect-group-title" style="color: #065F46;">Addressed Aspects (${addressed.length})</div>
            <div class="aspect-chips-wrap">
              ${addressed.map(a => `<span class="aspect-chip chip-addressed">✓ ${this.escapeHtml(a)}</span>`).join('')}
            </div>
          </div>
        `;
      }

      if (partial.length > 0) {
        html += `
          <div style="margin-top: 0.5rem;">
            <div class="aspect-group-title" style="color: #92400E;">Partially Addressed Aspects (${partial.length})</div>
            <div class="aspect-chips-wrap">
              ${partial.map(a => `<span class="aspect-chip chip-partial">⏳ ${this.escapeHtml(a)}</span>`).join('')}
            </div>
          </div>
        `;
      }

      if (missing.length > 0) {
        html += `
          <div style="margin-top: 0.5rem;">
            <div class="aspect-group-title" style="color: #991B1B;">Missing / Omitted Aspects (${missing.length})</div>
            <div class="aspect-chips-wrap">
              ${missing.map(a => `<span class="aspect-chip chip-missing">✕ ${this.escapeHtml(a)}</span>`).join('')}
            </div>
          </div>
        `;
      }

      if (addressed.length === 0 && partial.length === 0 && missing.length === 0) {
        html = `<p style="color: var(--text-muted); font-size: 0.85rem;">No requirements evaluated.</p>`;
      }

      this.compAspectsList.innerHTML = html;
    }

    if (this.compReasoningText) {
      this.compReasoningText.textContent = compJudge.reasoning || fallbackComp?.explanation || '';
    }
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
      this.accuracySource.className = 'badge-pill badge-source';
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
      const isExpanded = index === 0;
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

  // =========================================================================
  // BATCH EVALUATION MODULE (Milestone 3)
  // =========================================================================

  handleFileSelect(file) {
    if (!file) return;

    if (!file.name.toLowerCase().endsWith('.csv')) {
      this.showBatchError('Only CSV (.csv) files are supported for batch evaluation.');
      return;
    }

    this.hideBatchError();
    this.selectedBatchFile = file;

    if (this.batchFilename) this.batchFilename.textContent = file.name;
    if (this.batchFilesize) this.batchFilesize.textContent = `${(file.size / 1024).toFixed(1)} KB`;

    this.batchSelectedFile?.classList.remove('hidden');
    if (this.btnProcessBatch) {
      this.btnProcessBatch.disabled = false;
      this.btnProcessBatch.style.opacity = '1';
      this.btnProcessBatch.style.cursor = 'pointer';
    }
  }

  clearBatchFile() {
    this.selectedBatchFile = null;
    if (this.batchFileInput) this.batchFileInput.value = '';
    this.batchSelectedFile?.classList.add('hidden');

    if (this.btnProcessBatch) {
      this.btnProcessBatch.disabled = true;
      this.btnProcessBatch.style.opacity = '0.6';
      this.btnProcessBatch.style.cursor = 'not-allowed';
    }
    this.hideBatchError();
  }

  showBatchError(msg) {
    if (this.batchErrorAlert && this.batchErrorText) {
      this.batchErrorText.textContent = msg;
      this.batchErrorAlert.classList.remove('hidden');
    }
  }

  hideBatchError() {
    if (this.batchErrorAlert) {
      this.batchErrorAlert.classList.add('hidden');
    }
  }

  handleBatchProgress(event) {
    if (!event) return;

    if (event.event === 'BATCH_STARTED') {
      if (this.batchProgressBar) this.batchProgressBar.style.width = '0%';
      if (this.batchProgressPct) this.batchProgressPct.textContent = '0%';
      if (this.batchProgressStatus) {
        this.batchProgressStatus.textContent = `Processed: 0 / ${event.total_rows} (0.0%)`;
      }
    } else if (event.event === 'ROW_PROCESSED') {
      const pct = typeof event.percentage === 'number' ? event.percentage.toFixed(1) : ((event.processed / event.total_rows) * 100).toFixed(1);
      if (this.batchProgressBar) this.batchProgressBar.style.width = `${pct}%`;
      if (this.batchProgressPct) this.batchProgressPct.textContent = `${pct}%`;
      if (this.batchProgressStatus) {
        this.batchProgressStatus.textContent = `Processed: ${event.processed} / ${event.total_rows} (${pct}%) — Row ${event.row_id} [${event.status}]`;
      }
    } else if (event.event === 'BATCH_COMPLETED') {
      if (this.batchProgressBar) this.batchProgressBar.style.width = '100%';
      if (this.batchProgressPct) this.batchProgressPct.textContent = '100%';
      if (this.batchProgressStatus) {
        this.batchProgressStatus.textContent = `Processed: ${event.total_rows} / ${event.total_rows} (100.0%) — ✓ Batch Evaluation Complete!`;
      }
    }
  }

  async handleBatchSubmit() {
    if (!this.selectedBatchFile) {
      this.showBatchError('Please select a valid CSV file first.');
      return;
    }

    this.hideBatchError();
    this.btnProcessBatch.disabled = true;
    this.batchSpinner?.classList.remove('hidden');
    if (this.batchBtnText) this.batchBtnText.textContent = 'Processing Batch...';

    // Show Batch Progress
    if (this.batchProgressContainer) {
      this.batchProgressContainer.classList.remove('hidden');
      if (this.batchProgressBar) this.batchProgressBar.style.width = '0%';
      if (this.batchProgressPct) this.batchProgressPct.textContent = '0%';
      if (this.batchProgressStatus) this.batchProgressStatus.textContent = 'Initializing batch evaluation pipeline...';
    }
    this.batchResultsDashboard?.classList.add('hidden');

    const formData = new FormData();
    formData.append('file', this.selectedBatchFile);

    try {
      const response = await apiService.evaluateBatchStream(formData, (rowEvent) => {
        this.handleBatchProgress(rowEvent);
      });
      
      if (this.batchProgressBar) this.batchProgressBar.style.width = '100%';
      if (this.batchProgressPct) this.batchProgressPct.textContent = '100%';
      if (this.batchProgressStatus) this.batchProgressStatus.textContent = '✓ Batch Evaluation Complete!';

      setTimeout(() => {
        this.batchProgressContainer?.classList.add('hidden');
        this.renderBatchResults(response);
      }, 500);

    } catch (err) {
      this.batchProgressContainer?.classList.add('hidden');
      this.showBatchError(err.message || 'Batch evaluation failed.');
    } finally {
      this.btnProcessBatch.disabled = false;
      this.batchSpinner?.classList.add('hidden');
      if (this.batchBtnText) this.batchBtnText.textContent = 'Run Batch Evaluation';
    }
  }

  renderBatchResults(batchData) {
    if (!batchData || !batchData.summary) return;

    this.batchResults = batchData.results || [];
    const summary = batchData.summary;

    // 1. Aggregated Metrics
    const totalCount = summary.total_records !== undefined ? summary.total_records : (summary.total_rows || 0);
    const validCount = summary.successful !== undefined ? summary.successful : (summary.valid_rows || 0);
    const invalidCount = summary.invalid !== undefined ? summary.invalid : (summary.invalid_rows || 0);
    const avgScore = summary.average_overall !== undefined ? summary.average_overall : (summary.average_score || 0);
    const verdicts = summary.verdict_counts || summary.verdict_distribution || {};
    const avgHal = summary.average_hallucination !== undefined ? summary.average_hallucination : (summary.average_hallucination_percentage || 0);
    const highRisk = summary.hallucination_frequency !== undefined ? `${summary.hallucination_frequency}% High Risk` : (summary.high_hallucination_risk_count ? `${summary.high_hallucination_risk_count} High Risk` : '0 High Risk');

    if (this.batchStatTotal) this.batchStatTotal.textContent = totalCount;
    if (this.batchStatValid) this.batchStatValid.textContent = `${validCount} Valid / ${invalidCount} Invalid`;
    if (this.batchStatAvgScore) this.batchStatAvgScore.textContent = `${Number(avgScore).toFixed(1)}%`;

    const passCount = verdicts.PASS !== undefined ? verdicts.PASS : 0;
    const niCount = verdicts['NEEDS IMPROVEMENT'] !== undefined ? verdicts['NEEDS IMPROVEMENT'] : 0;
    const failCount = verdicts.FAIL !== undefined ? verdicts.FAIL : 0;
    if (this.batchStatPass) this.batchStatPass.textContent = `${passCount} PASS`;
    if (this.batchStatNi) this.batchStatNi.textContent = `${niCount} NI`;
    if (this.batchStatFail) this.batchStatFail.textContent = `${failCount} FAIL`;

    if (this.batchStatAvgHal) this.batchStatAvgHal.textContent = `${Number(avgHal).toFixed(1)}%`;
    if (this.batchStatHighRisk) this.batchStatHighRisk.textContent = highRisk;

    // 2. Results Table
    if (this.batchTableBody) {
      this.batchTableBody.innerHTML = this.batchResults.map((item, idx) => {
        const isInvalid = item.status !== 'VALID' && item.status !== 'SUCCESS';
        const verdict = item.verdict || item.final_verdict || (isInvalid ? 'INVALID' : 'FAIL');
        const rowNum = item.row_id !== undefined ? item.row_id : (item.row_index || (idx + 1));
        
        let verdictBadgeClass = 'badge-pass';
        if (verdict === 'NEEDS IMPROVEMENT') verdictBadgeClass = 'badge-needs-improvement';
        else if (verdict === 'FAIL' || verdict === 'INVALID') verdictBadgeClass = 'badge-fail';

        const scoreStr = isInvalid ? '—' : `${Number(item.overall_score || 0).toFixed(1)}%`;
        const relStr = item.relevance_score !== null && item.relevance_score !== undefined ? `${Number(item.relevance_score).toFixed(1)}%` : '—';
        const accStr = item.accuracy_score !== null && item.accuracy_score !== undefined ? `${Number(item.accuracy_score).toFixed(1)}%` : '—';
        const compStr = item.completeness_score !== null && item.completeness_score !== undefined ? `${Number(item.completeness_score).toFixed(1)}%` : '—';
        
        let halPct = null;
        if (item.hallucination_percentage !== null && item.hallucination_percentage !== undefined) {
          halPct = item.hallucination_percentage;
        } else if (item.evaluation_detail?.evaluation?.hallucination?.percentage !== undefined) {
          halPct = item.evaluation_detail.evaluation.hallucination.percentage;
        } else if (item.hallucination_score !== null && item.hallucination_score !== undefined) {
          halPct = 100 - item.hallucination_score;
        }
        const halStr = halPct !== null ? `${Number(halPct).toFixed(1)}%` : '—';

        const statusPill = isInvalid 
          ? `<span class="badge-pill" style="background:#FEF2F2; color:#991B1B;">INVALID</span>`
          : `<span class="badge-pill" style="background:#ECFDF5; color:#065F46;">VALID</span>`;

        return `
          <tr>
            <td><strong>#${rowNum}</strong></td>
            <td style="max-width: 220px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="${this.escapeHtml(item.question)}">
              ${this.escapeHtml(item.question)}
            </td>
            <td><strong>${scoreStr}</strong></td>
            <td><span class="badge-pill ${verdictBadgeClass}">${verdict}</span></td>
            <td>${relStr}</td>
            <td>${accStr}</td>
            <td>${compStr}</td>
            <td>${halStr}</td>
            <td>${statusPill}</td>
            <td>
              <button type="button" class="batch-row-btn" data-batch-idx="${idx}">Inspect</button>
            </td>
          </tr>
        `;
      }).join('');

      // Bind inspection click events
      const inspectButtons = this.batchTableBody.querySelectorAll('[data-batch-idx]');
      inspectButtons.forEach(btn => {
        btn.addEventListener('click', (e) => {
          const idx = parseInt(e.currentTarget.getAttribute('data-batch-idx'), 10);
          this.openBatchItemModal(this.batchResults[idx]);
        });
      });
    }

    this.batchResultsDashboard?.classList.remove('hidden');
    setTimeout(() => {
      this.batchResultsDashboard?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 100);
  }

  /**
   * Modal drawer inspecting individual batch record.
   */
  openBatchItemModal(item) {
    if (!item || !this.batchDetailModal || !this.modalContentArea) return;

    const isInvalid = item.status !== 'VALID' && item.status !== 'SUCCESS';
    const verdict = item.verdict || item.final_verdict || (isInvalid ? 'INVALID' : 'FAIL');
    const rowNum = item.row_id !== undefined ? item.row_id : (item.row_index || 'N/A');
    let verdictBadgeClass = 'badge-pass';
    if (verdict === 'NEEDS IMPROVEMENT') verdictBadgeClass = 'badge-needs-improvement';
    else if (verdict === 'FAIL' || verdict === 'INVALID') verdictBadgeClass = 'badge-fail';

    let contentHtml = `
      <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #E2E8F0; padding-bottom: 1rem; margin-bottom: 1.25rem;">
        <div>
          <h3 style="font-family: var(--font-heading); font-size: 1.3rem; font-weight: 700; color: #0F172A;">
            Record Detail: Row #${rowNum}
          </h3>
          <span style="font-size: 0.85rem; color: var(--text-muted);">Batch record inspection &amp; multi-agent telemetry</span>
        </div>
        <div style="display: flex; gap: 0.5rem; align-items: center;">
          <span class="badge-pill ${verdictBadgeClass}" style="font-size: 0.85rem; font-weight: 700;">${verdict}</span>
          ${!isInvalid ? `<span style="font-family: var(--font-heading); font-weight: 700; color: #4338CA;">${Number(item.overall_score || 0).toFixed(1)}%</span>` : ''}
        </div>
      </div>
    `;

    if (isInvalid) {
      contentHtml += `
        <div class="alert-error" style="margin-bottom: 1.5rem;">
          <strong>Row Validation Failed:</strong> ${this.escapeHtml(item.error_message || 'Missing required fields or invalid row structure.')}
        </div>
      `;
    }

    contentHtml += `
      <div style="display: flex; flex-direction: column; gap: 1rem;">
        <div>
          <strong style="font-size: 0.82rem; text-transform: uppercase; color: var(--text-muted); letter-spacing: 0.04em;">Question:</strong>
          <div style="background: #F8FAFC; padding: 0.75rem 1rem; border-radius: 8px; border: 1px solid #E2E8F0; font-size: 0.95rem; margin-top: 0.3rem;">
            ${this.escapeHtml(item.question)}
          </div>
        </div>

        <div>
          <strong style="font-size: 0.82rem; text-transform: uppercase; color: var(--text-muted); letter-spacing: 0.04em;">AI Generated Response:</strong>
          <div style="background: #F8FAFC; padding: 0.75rem 1rem; border-radius: 8px; border: 1px solid #E2E8F0; font-size: 0.92rem; margin-top: 0.3rem;">
            ${this.escapeHtml(item.ai_response || '(Empty)')}
          </div>
        </div>

        <div>
          <strong style="font-size: 0.82rem; text-transform: uppercase; color: #4338CA; letter-spacing: 0.04em;">Reference Answer (Ground Truth):</strong>
          <div style="background: #EEF2FF; padding: 0.75rem 1rem; border-radius: 8px; border: 1px solid #C7D2FE; font-size: 0.92rem; margin-top: 0.3rem;">
            ${this.escapeHtml(item.reference_answer || '(Empty)')}
          </div>
        </div>
      </div>
    `;

    const evalResp = item.evaluation_detail || item.evaluation_response;
    if (!isInvalid && evalResp) {
      const vJudge = evalResp.verdict_judge;
      const cJudge = evalResp.completeness_judge;
      const hJudge = evalResp.hallucination_judge;

      contentHtml += `
        <div style="margin-top: 1.5rem; border-top: 1px solid #E2E8F0; padding-top: 1rem;">
          <h4 style="font-family: var(--font-heading); font-size: 1.05rem; font-weight: 700; margin-bottom: 0.75rem;">Multi-Agent Scores</h4>
          <div class="batch-stats-grid" style="margin: 0 0 1rem 0;">
            <div class="batch-stat-card"><div class="batch-stat-val">${(evalResp.evaluation.relevance.score || 0).toFixed(1)}%</div><div class="batch-stat-label">Relevance</div></div>
            <div class="batch-stat-card"><div class="batch-stat-val">${(evalResp.evaluation.accuracy.score || 0).toFixed(1)}%</div><div class="batch-stat-label">Accuracy</div></div>
            <div class="batch-stat-card"><div class="batch-stat-val">${(cJudge ? cJudge.score : evalResp.evaluation.completeness.score || 0).toFixed(1)}%</div><div class="batch-stat-label">Completeness</div></div>
            <div class="batch-stat-card"><div class="batch-stat-val">${(evalResp.evaluation.hallucination.percentage || 0).toFixed(1)}%</div><div class="batch-stat-label">Hallucination</div></div>
          </div>
        </div>
      `;

      if (cJudge) {
        contentHtml += `
          <div style="margin-top: 1rem; background: #F8FAFC; padding: 1rem; border-radius: 10px; border: 1px solid #E2E8F0;">
            <strong style="font-size: 0.85rem; color: #1E293B;">Completeness Breakdown:</strong>
            <div style="display: flex; gap: 0.4rem; flex-wrap: wrap; margin-top: 0.5rem;">
              ${(cJudge.addressed_aspects || []).map(a => `<span class="aspect-chip chip-addressed">✓ ${this.escapeHtml(a)}</span>`).join('')}
              ${(cJudge.partially_addressed_aspects || []).map(a => `<span class="aspect-chip chip-partial">⏳ ${this.escapeHtml(a)}</span>`).join('')}
              ${(cJudge.missing_aspects || []).map(a => `<span class="aspect-chip chip-missing">✕ ${this.escapeHtml(a)}</span>`).join('')}
            </div>
            <p style="font-size: 0.88rem; color: #475569; margin-top: 0.5rem;">${this.escapeHtml(cJudge.reasoning)}</p>
          </div>
        `;
      }

      if (vJudge && vJudge.major_issues && vJudge.major_issues.length > 0) {
        contentHtml += `
          <div class="major-issues-box" style="margin-top: 1rem;">
            <strong style="font-size: 0.88rem; color: #991B1B;">Identified Issues:</strong>
            ${vJudge.major_issues.map(iss => `<div class="issue-item"><span>⚠️</span><span>${this.escapeHtml(iss)}</span></div>`).join('')}
          </div>
        `;
      }

      if (vJudge && vJudge.consolidated_reasoning) {
        contentHtml += `
          <div style="margin-top: 1rem; padding: 0.85rem; background: #FFFFFF; border: 1px solid #CBD5E1; border-radius: 8px;">
            <strong style="font-size: 0.82rem; color: #334155; text-transform: uppercase;">Arbitration Reasoning:</strong>
            <p style="font-size: 0.9rem; color: #1E293B; margin-top: 0.25rem;">${this.escapeHtml(vJudge.consolidated_reasoning)}</p>
          </div>
        `;
      }
    }

    this.modalContentArea.innerHTML = contentHtml;
    this.batchDetailModal.classList.remove('hidden');
  }

  closeModal() {
    if (this.batchDetailModal) {
      this.batchDetailModal.classList.add('hidden');
    }
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
