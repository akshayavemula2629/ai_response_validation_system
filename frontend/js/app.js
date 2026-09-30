/**
 * Main Application Controller — Milestone 3
 * Coordinates single evaluation, batch CSV processing, real multi-agent progress,
 * metrics line charts, verdict arbitration, completeness breakdown, and interactive inspections.
 */
import { CONFIG } from './config.js';
import { apiService } from './api.js';
import { ScoreGauge } from './components/gauge.js';
import { ComparisonChart, MetricsLineChart, PerDimensionPieChart, renderBatchMiniPieChart } from './components/chart.js';

class App {
  constructor() {
    this.gauge = new ScoreGauge('overall-score-gauge');
    this.comparisonChart = new ComparisonChart('comparison-chart-canvas');
    this.lineChart = new MetricsLineChart('metrics-line-chart-canvas');
    this.pieChart = new PerDimensionPieChart('per-dimension-pie-chart');
    this.batchPieChart = new PerDimensionPieChart('batch-dimension-pie-chart');
    
    this.lastEvaluation = null;
    this.batchResults = [];
    this.selectedBatchFile = null;
    this.batchValidationData = null;
    this.batchCardCharts = {};
    this.activeBatchFilter = 'ALL';

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

    // Modern Batch Evaluation Elements
    this.batchDropzone = document.getElementById('batch-dropzone');
    this.batchFileInput = document.getElementById('batch-file-input');
    this.batchFileSummaryCard = document.getElementById('batch-file-summary-card');
    this.batchFileName = document.getElementById('batch-file-name');
    this.batchFileSize = document.getElementById('batch-file-size');
    this.btnViewFile = document.getElementById('btn-view-file');
    this.btnReplaceFile = document.getElementById('btn-replace-file');
    this.batchFileTotal = document.getElementById('batch-file-total');
    this.batchFileValid = document.getElementById('batch-file-valid');
    this.batchFileInvalid = document.getElementById('batch-file-invalid');

    this.batchEvaluationControls = document.getElementById('batch-evaluation-controls');
    this.batchFilterSelect = document.getElementById('batch-filter-select');
    this.batchAvailableCount = document.getElementById('batch-available-count');
    this.batchRowCountInput = document.getElementById('batch-row-count-input');
    this.batchRowDenominator = document.getElementById('batch-row-denominator');
    this.batchRowCountError = document.getElementById('batch-row-count-error');
    this.batchRowCountErrorText = document.getElementById('batch-row-count-error-text');
    this.btnProcessBatch = document.getElementById('btn-process-batch') || document.getElementById('btn-evaluate-selected');
    this.btnEvaluateSelected = this.btnProcessBatch;
    this.btnEvaluateAllAvailable = document.getElementById('btn-evaluate-all-available');
    this.batchEvalSpinner = document.getElementById('batch-eval-spinner');
    this.batchEvalBtnText = document.getElementById('batch-eval-btn-text') || document.getElementById('batch-btn-text');

    this.batchProgressContainer = document.getElementById('batch-progress-container');
    this.batchProgressBar = document.getElementById('batch-progress-bar');
    this.batchProgressPct = document.getElementById('batch-progress-pct');
    this.batchProgressStatus = document.getElementById('batch-progress-status');
    this.batchErrorAlert = document.getElementById('batch-error-alert');
    this.batchErrorText = document.getElementById('batch-error-text');

    this.batchResultsDashboard = document.getElementById('batch-results-dashboard');
    this.sumFileTotal = document.getElementById('sum-file-total');
    this.sumValidTotal = document.getElementById('sum-valid-total');
    this.sumInvalidTotal = document.getElementById('sum-invalid-total');
    this.sumFilter = document.getElementById('sum-filter');
    this.sumAvailable = document.getElementById('sum-available');
    this.sumRequested = document.getElementById('sum-requested');
    this.sumEvaluated = document.getElementById('sum-evaluated');

    this.batchResultsTable = document.getElementById('batch-results-table');
    this.batchTableBody = document.getElementById('batch-table-body');
    this.btnBatchExpandAll = document.getElementById('btn-batch-expand-all');
    this.btnBatchCollapseAll = document.getElementById('btn-batch-collapse-all');

    // File View Modal Elements
    this.batchFileViewModal = document.getElementById('batch-file-view-modal');
    this.fileModalTitle = document.getElementById('file-modal-title');
    this.fileModalSubtitle = document.getElementById('file-modal-subtitle');
    this.fileModalContentArea = document.getElementById('file-modal-content-area');
    this.fileModalFooterInfo = document.getElementById('file-modal-footer-info');
    this.btnCloseFileModal = document.getElementById('btn-close-file-modal');
    this.btnCloseFileModalFooter = document.getElementById('btn-close-file-modal-footer');

    // Modal Drawer Elements
    this.batchDetailModal = document.getElementById('batch-detail-modal');
    this.modalContentArea = document.getElementById('modal-content-area');
    this.btnCloseModal = document.getElementById('btn-close-modal');

    // Result Dropdown Boxes & Dynamic Pie Chart Elements
    this.dropdownCompleteness = document.getElementById('dropdown-completeness');
    this.dropdownCompletenessBadge = document.getElementById('dropdown-completeness-badge');
    this.dropdownCompletenessVal = document.getElementById('dropdown-completeness-val');
    this.dropdownCompletenessReason = document.getElementById('dropdown-completeness-reason');
    this.dropdownCompletenessAspects = document.getElementById('dropdown-completeness-aspects');

    this.dropdownVerdict = document.getElementById('dropdown-verdict');
    this.dropdownVerdictBadge = document.getElementById('dropdown-verdict-badge');
    this.dropdownVerdictVal = document.getElementById('dropdown-verdict-val');
    this.dropdownVerdictReason = document.getElementById('dropdown-verdict-reason');

    this.dropdownDimensions = document.getElementById('dropdown-dimensions');
    this.dropdownScoreRel = document.getElementById('dropdown-score-rel');
    this.dropdownScoreAcc = document.getElementById('dropdown-score-acc');
    this.dropdownScoreComp = document.getElementById('dropdown-score-comp');
    this.dropdownScoreHal = document.getElementById('dropdown-score-hal');
    this.dropdownScoreSim = document.getElementById('dropdown-score-sim');
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

    // Modern Batch Evaluation Action Events
    if (this.btnViewFile) {
      this.btnViewFile.addEventListener('click', () => this.openFileViewModal());
    }
    if (this.btnReplaceFile) {
      this.btnReplaceFile.addEventListener('click', () => this.handleReplaceFile());
    }
    if (this.batchFilterSelect) {
      this.batchFilterSelect.addEventListener('change', () => this.handleBatchFilterChange());
    }
    if (this.batchRowCountInput) {
      this.batchRowCountInput.addEventListener('input', () => this.validateBatchRowCount());
    }
    if (this.btnEvaluateSelected) {
      this.btnEvaluateSelected.addEventListener('click', () => this.handleEvaluateBatch(false));
    }
    if (this.btnEvaluateAllAvailable) {
      this.btnEvaluateAllAvailable.addEventListener('click', () => this.handleEvaluateBatch(true));
    }
    if (this.btnBatchExpandAll) {
      this.btnBatchExpandAll.addEventListener('click', () => this.expandAllBatchRows());
    }
    if (this.btnBatchCollapseAll) {
      this.btnBatchCollapseAll.addEventListener('click', () => this.collapseAllBatchRows());
    }

    // Dropdown Accordion Toggles
    document.querySelectorAll('.dropdown-header').forEach(header => {
      header.addEventListener('click', () => {
        const box = header.closest('.dropdown-box');
        if (box) {
          box.classList.toggle('open');
        }
      });
    });

    // File View Modal Events
    if (this.btnCloseFileModal) {
      this.btnCloseFileModal.addEventListener('click', () => this.closeFileViewModal());
    }
    if (this.btnCloseFileModalFooter) {
      this.btnCloseFileModalFooter.addEventListener('click', () => this.closeFileViewModal());
    }
    if (this.batchFileViewModal) {
      this.batchFileViewModal.addEventListener('click', (e) => {
        if (e.target === this.batchFileViewModal) this.closeFileViewModal();
      });
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

    // Escape key closes modals
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        if (this.batchFileViewModal && !this.batchFileViewModal.classList.contains('hidden')) {
          this.closeFileViewModal();
        }
        if (this.batchDetailModal && !this.batchDetailModal.classList.contains('hidden')) {
          this.closeModal();
        }
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
   * Validates form inputs.
   * In Question Evaluation mode, user-facing Reference Answer input is hidden.
   * If reference answer is empty, automatically retrieves ground truth context from the knowledge base.
   */
  async validateInputs() {
    const question = this.questionInput?.value?.trim() || '';
    const aiResponse = this.aiResponseInput?.value?.trim() || '';
    let referenceAnswer = this.referenceAnswerInput?.value?.trim() || '';

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

    // Auto-retrieve reference context if not provided
    if (!referenceAnswer) {
      try {
        const retrieved = await apiService.getRetrieval(question, 1);
        if (retrieved && retrieved.chunks && retrieved.chunks.length > 0) {
          referenceAnswer = retrieved.chunks[0].content;
        } else {
          referenceAnswer = "The AI response is evaluated based on factual grounding, accuracy to the prompt, and logical reasoning.";
        }
      } catch (err) {
        console.warn('Auto-retrieval for reference answer fallback:', err);
        referenceAnswer = "Standard ground truth evaluation based on domain knowledge and verified facts.";
      }
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

    const payload = await this.validateInputs();
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

    // 10. Render M3 Dropdown Accordions (Completeness, Verdict, Per-Dimension Pie Chart)
    this.renderDropdownAccordions(data);

    // Smooth scroll to results
    setTimeout(() => {
      this.resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 100);
  }

  /**
   * Renders the 3 M3 interactive dropdown accordions with simple explanations,
   * aspect breakdowns, and the dynamic Per-Dimension Pie Chart.
   */
  renderDropdownAccordions(data) {
    if (!data || !data.evaluation) return;
    const evalData = data.evaluation;
    const cJudge = data.completeness_judge;
    const vJudge = data.verdict_judge;

    // 1. Completeness Dropdown
    const compScore = Number(cJudge?.score !== undefined ? cJudge.score : evalData.completeness?.score || 0).toFixed(1);
    if (this.dropdownCompletenessBadge) this.dropdownCompletenessBadge.textContent = `${compScore}%`;
    if (this.dropdownCompletenessVal) this.dropdownCompletenessVal.textContent = `${compScore}%`;
    if (this.dropdownCompletenessReason) {
      this.dropdownCompletenessReason.textContent = cJudge?.reasoning || evalData.completeness?.explanation || 'Evaluation completed based on prompt requirements.';
    }
    if (this.dropdownCompletenessAspects) {
      const addressed = cJudge?.addressed_aspects || [];
      const partial = cJudge?.partially_addressed_aspects || [];
      const missing = cJudge?.missing_aspects || [];
      let chipsHtml = '';
      if (addressed.length > 0) {
        chipsHtml += `<div style="margin-bottom:0.35rem;"><strong style="font-size:0.8rem;color:#065F46;">Addressed (${addressed.length}):</strong> ` + 
          addressed.map(a => `<span class="aspect-chip chip-addressed">✓ ${this.escapeHtml(a)}</span>`).join(' ') + `</div>`;
      }
      if (partial.length > 0) {
        chipsHtml += `<div style="margin-bottom:0.35rem;"><strong style="font-size:0.8rem;color:#92400E;">Partially Addressed (${partial.length}):</strong> ` + 
          partial.map(a => `<span class="aspect-chip chip-partial">⏳ ${this.escapeHtml(a)}</span>`).join(' ') + `</div>`;
      }
      if (missing.length > 0) {
        chipsHtml += `<div><strong style="font-size:0.8rem;color:#991B1B;">Missing (${missing.length}):</strong> ` + 
          missing.map(a => `<span class="aspect-chip chip-missing">✕ ${this.escapeHtml(a)}</span>`).join(' ') + `</div>`;
      }
      this.dropdownCompletenessAspects.innerHTML = chipsHtml;
    }

    // 2. Verdict Dropdown
    const verdict = vJudge?.final_verdict || evalData.verdict || 'PASS';
    if (this.dropdownVerdictBadge) {
      this.dropdownVerdictBadge.textContent = verdict;
      this.dropdownVerdictBadge.className = `dropdown-badge ${verdict === 'PASS' ? 'badge-pass' : (verdict === 'NEEDS IMPROVEMENT' ? 'badge-needs-improvement' : 'badge-fail')}`;
    }
    if (this.dropdownVerdictVal) {
      this.dropdownVerdictVal.textContent = verdict;
      this.dropdownVerdictVal.style.color = verdict === 'PASS' ? '#10B981' : (verdict === 'NEEDS IMPROVEMENT' ? '#F59E0B' : '#EF4444');
    }
    if (this.dropdownVerdictReason) {
      this.dropdownVerdictReason.textContent = vJudge?.consolidated_reasoning || evalData.summary || 'Arbitration completed across all metrics.';
    }

    // 3. Per-Dimension Scoring Dropdown & Dynamic Pie Chart
    const relScore = Number(evalData.relevance?.score || 0);
    const accScore = Number(evalData.accuracy?.score || 0);
    const compScoreVal = Number(cJudge?.score !== undefined ? cJudge.score : evalData.completeness?.score || 0);
    const halPct = Number(evalData.hallucination?.percentage || 0);
    const halSafety = Math.max(0, 100 - halPct); // Safety is 100 - risk
    const simScore = Number(data.similarity?.percentage !== undefined ? data.similarity.percentage : (evalData.similarity?.percentage || 0));

    if (this.dropdownScoreRel) this.dropdownScoreRel.textContent = `${relScore.toFixed(1)}%`;
    if (this.dropdownScoreAcc) this.dropdownScoreAcc.textContent = `${accScore.toFixed(1)}%`;
    if (this.dropdownScoreComp) this.dropdownScoreComp.textContent = `${compScoreVal.toFixed(1)}%`;
    if (this.dropdownScoreHal) this.dropdownScoreHal.textContent = `${halSafety.toFixed(1)}%`;
    if (this.dropdownScoreSim) this.dropdownScoreSim.textContent = `${simScore.toFixed(1)}%`;

    // Render Dynamic Pie Chart with calculated dimension data
    if (this.pieChart) {
      this.pieChart.render({
        relevance: relScore,
        accuracy: accScore,
        completeness: compScoreVal,
        hallucination_safety: halSafety,
        similarity: simScore
      });
    }
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

  // =========================================================================
  // MODERN BATCH EVALUATION MODULE
  // =========================================================================

  async handleFileSelect(file) {
    if (!file) return;

    const lowerName = file.name.toLowerCase();
    const isSupported = lowerName.endsWith('.csv') || lowerName.endsWith('.txt') || lowerName.endsWith('.pdf') || lowerName.endsWith('.doc') || lowerName.endsWith('.docx');
    if (!isSupported) {
      this.showBatchError('Supported batch dataset formats are: CSV (.csv), TXT (.txt), PDF (.pdf), and DOCX (.docx).');
      return;
    }

    this.hideBatchError();
    await this.validateBatchFile(file);
  }

  async validateBatchFile(file) {
    this.hideBatchError();
    this.hideBatchRowError();

    // Show temporary validating indicator in File Summary Card
    if (this.batchFileSummaryCard) {
      this.batchFileSummaryCard.classList.remove('hidden');
    }
    if (this.batchFileName) this.batchFileName.textContent = file.name;
    if (this.batchFileSize) this.batchFileSize.textContent = `${(file.size / 1024).toFixed(1)} KB`;
    if (this.batchFileTotal) this.batchFileTotal.textContent = '...';
    if (this.batchFileValid) this.batchFileValid.textContent = '...';
    if (this.batchFileInvalid) this.batchFileInvalid.textContent = '...';

    try {
      const summary = await apiService.validateBatchInput(file);
      this.selectedBatchFile = file;
      this.batchValidationData = summary;

      const total = summary.total_records || summary.valid_records + summary.invalid_records || 0;
      const valid = summary.valid_count !== undefined ? summary.valid_count : (summary.valid_records || 0);
      const invalid = summary.invalid_count !== undefined ? summary.invalid_count : (summary.invalid_records || 0);

      if (this.batchFileTotal) this.batchFileTotal.textContent = total;
      if (this.batchFileValid) this.batchFileValid.textContent = valid;
      if (this.batchFileInvalid) this.batchFileInvalid.textContent = invalid;

      // Show Controls Box
      if (this.batchEvaluationControls) {
        this.batchEvaluationControls.classList.remove('hidden');
      }

      // Hide results from previous run and reset state
      this.batchResults = [];
      if (this.batchTableBody) this.batchTableBody.innerHTML = '';
      if (this.batchCardCharts) {
        Object.keys(this.batchCardCharts).forEach(k => {
          try { this.batchCardCharts[k].destroy(); } catch (e) {}
        });
        this.batchCardCharts = {};
      }
      if (this.batchProgressBar) this.batchProgressBar.style.width = '0%';
      if (this.batchProgressPct) this.batchProgressPct.textContent = '0%';
      if (this.batchResultsDashboard) {
        this.batchResultsDashboard.classList.add('hidden');
      }

      // Update Filter and Denominators
      this.handleBatchFilterChange();

    } catch (err) {
      console.error('Batch validation error:', err);
      if (this.batchFileSummaryCard) this.batchFileSummaryCard.classList.add('hidden');
      if (this.batchEvaluationControls) this.batchEvaluationControls.classList.add('hidden');
      this.showBatchError(err.message || 'Failed to validate batch file.');
    }
  }

  getAvailableCount(filterVal) {
    if (!this.batchValidationData) return 0;
    const filter = (filterVal || 'all').toLowerCase();
    if (filter === 'valid') {
      return this.batchValidationData.valid_count !== undefined 
        ? this.batchValidationData.valid_count 
        : (this.batchValidationData.valid_records || 0);
    }
    if (filter === 'invalid') {
      return this.batchValidationData.invalid_count !== undefined 
        ? this.batchValidationData.invalid_count 
        : (this.batchValidationData.invalid_records || 0);
    }
    return this.batchValidationData.total_records || 0;
  }

  handleBatchFilterChange() {
    const filterVal = this.batchFilterSelect ? this.batchFilterSelect.value : 'all';
    const available = this.getAvailableCount(filterVal);

    if (this.batchAvailableCount) {
      this.batchAvailableCount.textContent = available;
    }
    if (this.batchRowDenominator) {
      this.batchRowDenominator.textContent = available;
    }

    this.validateBatchRowCount();
  }

  validateBatchRowCount() {
    const filterVal = this.batchFilterSelect ? this.batchFilterSelect.value : 'all';
    const available = this.getAvailableCount(filterVal);
    const rawVal = this.batchRowCountInput ? this.batchRowCountInput.value.trim() : '';

    if (!rawVal) {
      this.showBatchRowError(`❌ Invalid number of rows. Please enter a positive integer between 1 and ${available}.`);
      if (this.btnEvaluateSelected) this.btnEvaluateSelected.disabled = true;
      return false;
    }

    const num = Number(rawVal);
    if (isNaN(num) || !Number.isInteger(num) || num <= 0) {
      this.showBatchRowError(`❌ Invalid number of rows. Please enter a positive integer between 1 and ${available}.`);
      if (this.btnEvaluateSelected) this.btnEvaluateSelected.disabled = true;
      return false;
    }

    if (num > available) {
      this.showBatchRowError(`❌ Requested rows cannot exceed the available records. Only ${available} records are available for the selected filter.`);
      if (this.btnEvaluateSelected) this.btnEvaluateSelected.disabled = true;
      return false;
    }

    this.hideBatchRowError();
    if (this.btnEvaluateSelected) this.btnEvaluateSelected.disabled = false;
    return true;
  }

  showBatchRowError(msg) {
    if (this.batchRowCountError && this.batchRowCountErrorText) {
      this.batchRowCountErrorText.textContent = msg;
      this.batchRowCountError.classList.remove('hidden');
    }
  }

  hideBatchRowError() {
    if (this.batchRowCountError) {
      this.batchRowCountError.classList.add('hidden');
    }
  }

  handleReplaceFile() {
    this.selectedBatchFile = null;
    this.batchValidationData = null;
    if (this.batchFileInput) this.batchFileInput.value = '';
    
    this.batchFileSummaryCard?.classList.add('hidden');
    this.batchEvaluationControls?.classList.add('hidden');
    this.batchProgressContainer?.classList.add('hidden');
    this.batchResultsDashboard?.classList.add('hidden');
    this.hideBatchError();
    this.hideBatchRowError();

    // Trigger file browser directly
    this.batchFileInput?.click();
  }

  openFileViewModal() {
    if (!this.batchFileViewModal || !this.batchValidationData) return;

    const records = this.batchValidationData.records || [];
    const total = this.batchValidationData.total_records || records.length;
    const valid = this.batchValidationData.valid_count || 0;
    const invalid = this.batchValidationData.invalid_count || 0;

    if (this.fileModalTitle) {
      this.fileModalTitle.textContent = `Uploaded Dataset: ${this.selectedBatchFile?.name || 'File'} (${total} Records)`;
    }
    if (this.fileModalSubtitle) {
      this.fileModalSubtitle.textContent = `Pre-evaluation dataset inspection • ${valid} Valid Records • ${invalid} Invalid Records`;
    }
    if (this.fileModalFooterInfo) {
      this.fileModalFooterInfo.textContent = `Showing all ${records.length} records. Validation checks: Question, AI Response, and Ground Truth status.`;
    }

    if (this.fileModalContentArea) {
      if (records.length === 0) {
        this.fileModalContentArea.innerHTML = `<div style="padding: 2rem; text-align: center; color: var(--text-muted);">No records found in uploaded file.</div>`;
      } else {
        this.fileModalContentArea.innerHTML = `
          <table style="width: 100%; border-collapse: collapse; font-size: 0.85rem;">
            <thead>
              <tr style="background: #F1F5F9; border-bottom: 2px solid #CBD5E1; text-align: left;">
                <th style="padding: 0.6rem 0.75rem; width: 60px; text-align: center;">Row #</th>
                <th style="padding: 0.6rem 0.75rem; width: 90px; text-align: center;">Status</th>
                <th style="padding: 0.6rem 0.75rem;">Question</th>
                <th style="padding: 0.6rem 0.75rem;">AI Response</th>
                <th style="padding: 0.6rem 0.75rem;">Reference Answer</th>
              </tr>
            </thead>
            <tbody>
              ${records.map(r => {
                const isValid = r.status === 'VALID';
                const statusBadge = isValid 
                  ? `<span class="badge-pill" style="background:#ECFDF5; color:#065F46; font-weight:700;">VALID</span>`
                  : `<span class="badge-pill" style="background:#FEF2F2; color:#991B1B; font-weight:700;">INVALID</span>`;
                const reasonNotice = !isValid && r.reason ? `<div style="font-size:0.75rem; color:#DC2626; margin-top:0.2rem;">${this.escapeHtml(r.reason)}</div>` : '';

                return `
                  <tr style="border-bottom: 1px solid #E2E8F0; vertical-align: top;">
                    <td style="padding: 0.6rem 0.75rem; text-align: center; font-weight: 700; color: #64748B;">#${r.row_id}</td>
                    <td style="padding: 0.6rem 0.75rem; text-align: center;">
                      ${statusBadge}
                      ${reasonNotice}
                    </td>
                    <td style="padding: 0.6rem 0.75rem; font-weight: 600; color: #1E293B; max-width: 250px;">
                      ${this.escapeHtml(r.question || '(Empty Question)')}
                    </td>
                    <td style="padding: 0.6rem 0.75rem; color: #334155; max-width: 280px;">
                      ${this.escapeHtml(r.ai_response || '(Empty AI Response)')}
                    </td>
                    <td style="padding: 0.6rem 0.75rem; color: #4338CA; max-width: 240px;">
                      ${this.escapeHtml(r.reference_answer || '(Auto-Retrieved from KB)')}
                    </td>
                  </tr>
                `;
              }).join('')}
            </tbody>
          </table>
        `;
      }
    }

    this.batchFileViewModal.classList.remove('hidden');
  }

  closeFileViewModal() {
    if (this.batchFileViewModal) {
      this.batchFileViewModal.classList.add('hidden');
    }
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

  async handleEvaluateBatch(evaluateAll = false) {
    if (!this.selectedBatchFile) {
      this.showBatchError('Please select a batch dataset file first.');
      return;
    }

    const filterVal = this.batchFilterSelect ? this.batchFilterSelect.value : 'all';
    const available = this.getAvailableCount(filterVal);

    if (evaluateAll) {
      if (this.batchRowCountInput) this.batchRowCountInput.value = available;
      this.hideBatchRowError();
    }

    if (!this.validateBatchRowCount()) {
      return;
    }

    const rowLimit = parseInt(this.batchRowCountInput.value, 10);

    this.hideBatchError();
    if (this.btnEvaluateSelected) this.btnEvaluateSelected.disabled = true;
    if (this.btnEvaluateAllAvailable) this.btnEvaluateAllAvailable.disabled = true;
    if (this.batchEvalSpinner) this.batchEvalSpinner.classList.remove('hidden');
    if (this.batchEvalBtnText) this.batchEvalBtnText.textContent = 'EVALUATING RESPONSES...';

    // Show Progress Container
    if (this.batchProgressContainer) {
      this.batchProgressContainer.classList.remove('hidden');
      if (this.batchProgressBar) this.batchProgressBar.style.width = '0%';
      if (this.batchProgressPct) this.batchProgressPct.textContent = '0%';
      if (this.batchProgressStatus) {
        this.batchProgressStatus.textContent = `Evaluating selected records... (0 / ${rowLimit})`;
      }
    }
    this.batchResultsDashboard?.classList.add('hidden');

    const formData = new FormData();
    formData.append('file', this.selectedBatchFile);
    formData.append('filter_status', filterVal);
    formData.append('row_limit', rowLimit);

    try {
      const response = await apiService.evaluateBatchStream(formData, (event) => {
        if (!event) return;
        if (event.event === 'BATCH_STARTED') {
          if (this.batchProgressBar) this.batchProgressBar.style.width = '0%';
          if (this.batchProgressPct) this.batchProgressPct.textContent = '0%';
          if (this.batchProgressStatus) {
            this.batchProgressStatus.textContent = `Evaluating selected records... (0 / ${event.total_rows || rowLimit})`;
          }
        } else if (event.event === 'ROW_PROCESSED') {
          const pct = typeof event.percentage === 'number' ? event.percentage.toFixed(1) : ((event.processed / (event.total_rows || rowLimit)) * 100).toFixed(1);
          if (this.batchProgressBar) this.batchProgressBar.style.width = `${pct}%`;
          if (this.batchProgressPct) this.batchProgressPct.textContent = `${pct}%`;
          if (this.batchProgressStatus) {
            this.batchProgressStatus.textContent = `Evaluating ${event.processed} / ${event.total_rows || rowLimit} (${pct}%) — Row #${event.row_id} [${event.status}]`;
          }
        } else if (event.event === 'BATCH_COMPLETED') {
          if (this.batchProgressBar) this.batchProgressBar.style.width = '100%';
          if (this.batchProgressPct) this.batchProgressPct.textContent = '100%';
          if (this.batchProgressStatus) {
            this.batchProgressStatus.textContent = `Evaluating ${event.total_rows || rowLimit} / ${event.total_rows || rowLimit} (100.0%) — ✓ Evaluation Complete!`;
          }
        }
      });

      if (this.batchProgressBar) this.batchProgressBar.style.width = '100%';
      if (this.batchProgressPct) this.batchProgressPct.textContent = '100%';
      if (this.batchProgressStatus) this.batchProgressStatus.textContent = '✓ Evaluation Complete!';

      setTimeout(() => {
        this.batchProgressContainer?.classList.add('hidden');
        this.renderBatchResults(response);
      }, 400);

    } catch (err) {
      this.batchProgressContainer?.classList.add('hidden');
      this.showBatchError(err.message || 'Batch evaluation failed.');
    } finally {
      if (this.btnEvaluateSelected) this.btnEvaluateSelected.disabled = false;
      if (this.btnEvaluateAllAvailable) this.btnEvaluateAllAvailable.disabled = false;
      if (this.batchEvalSpinner) this.batchEvalSpinner.classList.add('hidden');
      if (this.batchEvalBtnText) this.batchEvalBtnText.textContent = 'EVALUATE RESPONSES';
    }
  }

  renderBatchResults(batchData) {
    if (!batchData) return;

    this.batchResults = batchData.results || [];
    const summary = batchData.summary || {};

    // 1. Update Batch Evaluation Summary Banner
    const fileTotal = summary.file_total !== undefined ? summary.file_total : (this.batchValidationData?.total_records || this.batchResults.length);
    const validTotal = summary.valid_total !== undefined ? summary.valid_total : (this.batchValidationData?.valid_count !== undefined ? this.batchValidationData.valid_count : (this.batchValidationData?.valid_records || 0));
    const invalidTotal = summary.invalid_total !== undefined ? summary.invalid_total : (this.batchValidationData?.invalid_count !== undefined ? this.batchValidationData.invalid_count : (this.batchValidationData?.invalid_records || 0));
    const selFilter = summary.selected_filter || (this.batchFilterSelect ? this.batchFilterSelect.value : 'All');
    const available = summary.available_records !== undefined ? summary.available_records : this.getAvailableCount(selFilter);
    const requested = summary.requested_records !== undefined ? summary.requested_records : this.batchResults.length;
    const evaluated = summary.actually_evaluated !== undefined ? summary.actually_evaluated : this.batchResults.length;

    if (this.sumFileTotal) this.sumFileTotal.textContent = fileTotal;
    if (this.sumValidTotal) this.sumValidTotal.textContent = validTotal;
    if (this.sumInvalidTotal) this.sumInvalidTotal.textContent = invalidTotal;
    if (this.sumFilter) this.sumFilter.textContent = selFilter.charAt(0).toUpperCase() + selFilter.slice(1);
    if (this.sumAvailable) this.sumAvailable.textContent = available;
    if (this.sumRequested) this.sumRequested.textContent = requested;
    if (this.sumEvaluated) this.sumEvaluated.textContent = evaluated;

    // 2. Clean up previous charts
    if (this.batchCardCharts) {
      Object.keys(this.batchCardCharts).forEach(k => {
        try { this.batchCardCharts[k].destroy(); } catch (e) {}
      });
      this.batchCardCharts = {};
    }

    // 3. Render Batch Results Table
    if (this.batchTableBody) {
      if (this.batchResults.length === 0) {
        this.batchTableBody.innerHTML = `
          <tr>
            <td colspan="9" style="text-align: center; padding: 2rem; color: var(--text-muted);">
              No records evaluated.
            </td>
          </tr>
        `;
      } else {
        this.batchTableBody.innerHTML = this.batchResults.map((item, idx) => {
          const isInvalid = item.status === 'INVALID' || item.status === 'FAILED' || item.record_status === 'INVALID';
          const rowNum = item.row_id !== undefined ? item.row_id : (idx + 1);
          const verdict = item.final_verdict || item.verdict || (isInvalid ? 'FAIL' : 'PASS');
          const recStatus = item.record_status || (isInvalid ? 'INVALID' : 'VALID');

          let verdictBadgeClass = 'badge-pass';
          if (verdict === 'NEEDS IMPROVEMENT') verdictBadgeClass = 'badge-needs-improvement';
          else if (verdict === 'FAIL') verdictBadgeClass = 'badge-fail';

          const statusBadge = recStatus === 'VALID'
            ? `<span class="badge-pill" style="background:#ECFDF5; color:#065F46; font-weight:700;">VALID</span>`
            : `<span class="badge-pill" style="background:#FEF2F2; color:#991B1B; font-weight:700;">INVALID</span>`;

          const scoreVal = Number(item.overall_score || 0);
          const scoreStr = isInvalid && scoreVal === 0 ? '0.0%' : `${scoreVal.toFixed(1)}%`;
          const relStr = item.relevance_score !== null && item.relevance_score !== undefined ? `${Number(item.relevance_score).toFixed(1)}%` : '—';
          const accStr = item.accuracy_score !== null && item.accuracy_score !== undefined ? `${Number(item.accuracy_score).toFixed(1)}%` : '—';
          const compStr = item.completeness_score !== null && item.completeness_score !== undefined ? `${Number(item.completeness_score).toFixed(1)}%` : '—';

          let halPct = 0;
          if (item.hallucination_percentage !== null && item.hallucination_percentage !== undefined) {
            halPct = Number(item.hallucination_percentage);
          } else if (item.evaluation_detail?.evaluation?.hallucination?.percentage !== undefined) {
            halPct = Number(item.evaluation_detail.evaluation.hallucination.percentage);
          } else if (item.hallucination_score !== null && item.hallucination_score !== undefined) {
            halPct = 100 - Number(item.hallucination_score);
          }
          const halStr = `${halPct.toFixed(1)}%`;
          const riskLevel = halPct > 35 ? 'High' : (halPct > 15 ? 'Medium' : 'Low');

          const simVal = item.similarity_score !== null && item.similarity_score !== undefined 
            ? item.similarity_score 
            : (item.evaluation_detail?.evaluation?.similarity?.percentage !== undefined ? item.evaluation_detail.evaluation.similarity.percentage : null);
          const simStr = simVal !== null ? `${Number(simVal).toFixed(1)}%` : '—';

          const evalResp = item.evaluation_detail || {};
          const vJudge = evalResp.verdict_judge;
          const relJudge = evalResp.relevance_judge;
          const accJudge = evalResp.accuracy_judge;
          const compJudge = evalResp.completeness_judge;
          const halJudge = evalResp.hallucination_judge;

          const canvasId = `batch-row-pie-${idx}`;

          return `
            <!-- Main Record Row -->
            <tr class="batch-main-row" data-row-idx="${idx}" style="cursor: pointer;">
              <td style="text-align: center;">
                <button type="button" class="btn-row-toggle" data-row-toggle="${idx}" aria-label="Toggle details">▶</button>
              </td>
              <td style="max-width: 280px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="${this.escapeHtml(item.question || '')}">
                <span style="font-weight: 700; color: #64748B; margin-right: 0.35rem;">#${rowNum}</span>
                <strong>${this.escapeHtml(item.question || '(No Question)')}</strong>
              </td>
              <td style="text-align: center;">${statusBadge}</td>
              <td style="text-align: center;">
                <span class="badge-pill ${verdictBadgeClass}" style="margin-right: 0.3rem;">${verdict}</span>
                <strong style="color: #4338CA;">${scoreStr}</strong>
              </td>
              <td style="text-align: center;">${relStr}</td>
              <td style="text-align: center;">${accStr}</td>
              <td style="text-align: center;">${compStr}</td>
              <td style="text-align: center;">
                <span class="badge-pill risk-${riskLevel.toLowerCase()}" style="font-size: 0.76rem; padding: 0.2rem 0.5rem;">${riskLevel} Risk</span>
                <span style="font-size: 0.8rem; color: #64748B; margin-left: 0.25rem;">${halStr}</span>
              </td>
              <td style="text-align: center; color: #2563EB; font-weight: 600;">${simStr}</td>
            </tr>

            <!-- Expandable Single-Evaluation Breakdown Row -->
            <tr class="batch-detail-row hidden" id="batch-row-detail-${idx}">
              <td colspan="9" class="batch-detail-cell">
                <div style="padding: 1.25rem 1rem;">
                  
                  <!-- 1. Question, AI Response & Reference Answer -->
                  <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1rem; margin-bottom: 1.25rem;">
                    <div class="batch-detail-q-box" style="margin: 0;">
                      <strong>Question (Row #${rowNum})</strong>
                      <div style="margin-top: 0.3rem;">${this.escapeHtml(item.question || '(No Question)')}</div>
                    </div>
                    <div class="batch-detail-a-box" style="margin: 0;">
                      <strong>AI Generated Response</strong>
                      <div style="margin-top: 0.3rem;">${this.escapeHtml(item.ai_response || '(Empty Response)')}</div>
                    </div>
                    <div style="background: #EEF2FF; border: 1px solid #C7D2FE; border-radius: 8px; padding: 0.85rem 1rem;">
                      <strong style="font-size: 0.82rem; color: #4338CA; text-transform: uppercase;">Reference Answer (Ground Truth)</strong>
                      <div style="font-size: 0.9rem; color: #1E293B; margin-top: 0.3rem;">
                        ${this.escapeHtml(item.reference_answer || 'Knowledge Base Verified Facts')}
                      </div>
                    </div>
                  </div>

                  <!-- 2. Verdict & Multi-Agent Arbitration Banner -->
                  <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 12px; padding: 1.1rem 1.25rem; margin-bottom: 1.25rem;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem; flex-wrap: wrap; gap: 0.5rem;">
                      <div style="display: flex; align-items: center; gap: 0.6rem;">
                        <span class="badge-pill ${verdictBadgeClass}" style="font-weight: 700; font-size: 0.95rem;">${verdict}</span>
                        <span style="font-weight: 700; font-size: 0.95rem; color: #1E293B;">Arbitration Verdict &amp; Synthesis</span>
                      </div>
                      <span style="font-family: var(--font-heading); font-weight: 700; color: #4338CA; font-size: 1.1rem;">
                        Overall Score: ${scoreStr}
                      </span>
                    </div>
                    <p style="font-size: 0.9rem; color: #334155; line-height: 1.55; margin: 0;">
                      ${this.escapeHtml(vJudge?.consolidated_reasoning || evalResp.evaluation?.summary || item.error_message || 'Multi-agent evaluation completed.')}
                    </p>
                    ${(vJudge?.major_issues && vJudge.major_issues.length > 0) ? `
                      <div class="major-issues-box" style="margin-top: 0.75rem;">
                        <strong style="font-size: 0.82rem; color: #991B1B;">Identified Issues:</strong>
                        ${vJudge.major_issues.map(iss => `<div class="issue-item"><span>⚠️</span><span>${this.escapeHtml(iss)}</span></div>`).join('')}
                      </div>
                    ` : ''}
                  </div>

                  <!-- 3. Four Evaluation Dimensions Grid -->
                  <div class="batch-detail-dims-grid">
                    <!-- Relevance -->
                    <div class="batch-detail-dim-card">
                      <div class="batch-detail-dim-header">
                        <span class="batch-detail-dim-name">🎯 Relevance</span>
                        <span class="batch-detail-dim-score" style="color: #6366F1;">${relStr}</span>
                      </div>
                      <div style="display: flex; gap: 0.35rem; margin-bottom: 0.45rem; flex-wrap: wrap;">
                        <span class="badge-pill" style="background: #EEF2FF; color: #4338CA; font-size: 0.75rem;">${relJudge?.category || 'Relevant'}</span>
                        <span class="badge-pill badge-rating" style="font-size: 0.75rem;">${relJudge?.score || '—'} / 5</span>
                      </div>
                      <div class="batch-detail-dim-reason">
                        ${this.escapeHtml(relJudge?.reasoning || evalResp.evaluation?.relevance?.explanation || 'Direct semantic and topical query alignment.')}
                      </div>
                    </div>

                    <!-- Accuracy -->
                    <div class="batch-detail-dim-card">
                      <div class="batch-detail-dim-header">
                        <span class="batch-detail-dim-name">🛡️ Accuracy</span>
                        <span class="batch-detail-dim-score" style="color: #10B981;">${accStr}</span>
                      </div>
                      <div style="display: flex; gap: 0.35rem; margin-bottom: 0.45rem; flex-wrap: wrap;">
                        <span class="badge-pill" style="background: #ECFDF5; color: #065F46; font-size: 0.75rem;">${accJudge?.category || 'Correct'}</span>
                        <span class="badge-pill badge-source" style="font-size: 0.75rem;">Source: ${accJudge?.evidence_source || 'Knowledge Base'}</span>
                      </div>
                      <div class="batch-detail-dim-reason">
                        ${this.escapeHtml(accJudge?.reasoning || evalResp.evaluation?.accuracy?.explanation || 'Factual consistency against ground truth.')}
                      </div>
                      ${(accJudge?.issues && accJudge.issues.length > 0) ? `
                        <div style="margin-top: 0.5rem; font-size: 0.78rem; color: #991B1B;">
                          <strong>Inaccuracies:</strong>
                          ${accJudge.issues.map(iss => `<div style="margin-top: 0.15rem;">• ${this.escapeHtml(iss)}</div>`).join('')}
                        </div>
                      ` : ''}
                    </div>

                    <!-- Completeness -->
                    <div class="batch-detail-dim-card">
                      <div class="batch-detail-dim-header">
                        <span class="batch-detail-dim-name">📚 Completeness</span>
                        <span class="batch-detail-dim-score" style="color: #0EA5E9;">${compStr}</span>
                      </div>
                      <div class="aspect-chips-wrap" style="margin-bottom: 0.45rem; gap: 0.3rem;">
                        ${(compJudge?.addressed_aspects || []).map(a => `<span class="aspect-chip chip-addressed" style="font-size:0.75rem; padding:0.2rem 0.5rem;">✓ ${this.escapeHtml(a)}</span>`).join('')}
                        ${(compJudge?.partially_addressed_aspects || []).map(a => `<span class="aspect-chip chip-partial" style="font-size:0.75rem; padding:0.2rem 0.5rem;">⏳ ${this.escapeHtml(a)}</span>`).join('')}
                        ${(compJudge?.missing_aspects || []).map(a => `<span class="aspect-chip chip-missing" style="font-size:0.75rem; padding:0.2rem 0.5rem;">✕ ${this.escapeHtml(a)}</span>`).join('')}
                      </div>
                      <div class="batch-detail-dim-reason">
                        ${this.escapeHtml(compJudge?.reasoning || evalResp.evaluation?.completeness?.explanation || 'Coverage of essential prompt concepts.')}
                      </div>
                    </div>

                    <!-- Hallucination Detection -->
                    <div class="batch-detail-dim-card">
                      <div class="batch-detail-dim-header">
                        <span class="batch-detail-dim-name">⚠️ Hallucination Risk</span>
                        <span class="batch-detail-dim-score" style="color: #8B5CF6;">${halStr}</span>
                      </div>
                      <div style="margin-bottom: 0.45rem;">
                        <span class="badge-pill risk-${riskLevel.toLowerCase()}" style="font-size: 0.75rem;">
                          ${riskLevel} Risk
                        </span>
                      </div>
                      <div class="batch-detail-dim-reason">
                        ${this.escapeHtml(halJudge?.explanation || evalResp.evaluation?.hallucination?.explanation || 'Atomic claim grounding verification.')}
                      </div>
                      ${(halJudge?.claims_breakdown && halJudge.claims_breakdown.length > 0) ? `
                        <div class="batch-claims-chips-wrap" style="margin-top: 0.6rem;">
                          <span style="font-size: 0.78rem; font-weight: 700; color: #475569;">Atomic Claims:</span>
                          ${halJudge.claims_breakdown.map(c => {
                            const statusClass = c.status === 'Supported' ? 'batch-claim-supported' : (c.status === 'Contradicted' ? 'batch-claim-contradicted' : 'batch-claim-unsupported');
                            const icon = c.status === 'Supported' ? '✓' : (c.status === 'Contradicted' ? '✕' : '⚠');
                            return `
                              <div class="batch-claim-chip ${statusClass}">
                                <strong>${icon} ${c.status}:</strong> "${this.escapeHtml(c.claim)}"
                              </div>
                            `;
                          }).join('')}
                        </div>
                      ` : ''}
                    </div>
                  </div>

                  <!-- 4. Retrieved Evidence, Better Answer, and Individual Pie Chart -->
                  <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1rem; margin-top: 1.25rem;">
                    
                    <!-- Evidence Context -->
                    <div style="background: #FFFFFF; padding: 1rem; border-radius: 10px; border: 1px solid #E2E8F0;">
                      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                        <strong style="font-size: 0.82rem; text-transform: uppercase; color: #475569; letter-spacing: 0.04em;">Retrieved Evidence Context</strong>
                        <span class="badge-pill" style="background: #F1F5F9; color: #475569; font-size: 0.75rem;">${(evalResp.retrieved_evidence || []).length} chunks</span>
                      </div>
                      ${(evalResp.retrieved_evidence && evalResp.retrieved_evidence.length > 0) ? `
                        <div style="max-height: 150px; overflow-y: auto; font-size: 0.82rem; color: #334155; line-height: 1.45;">
                          ${evalResp.retrieved_evidence.map(ev => `
                            <div style="margin-bottom: 0.5rem; padding-bottom: 0.5rem; border-bottom: 1px dashed #E2E8F0;">
                              <div style="font-weight: 600; color: #4338CA; font-size: 0.78rem;">${this.escapeHtml(ev.source || 'Knowledge Base')} (Sim: ${(Number(ev.similarity_score || 0) * 100).toFixed(1)}%)</div>
                              <div>${this.escapeHtml(ev.content)}</div>
                            </div>
                          `).join('')}
                        </div>
                      ` : `
                        <div style="font-size: 0.82rem; color: var(--text-muted);">Knowledge base retrieval verified for factual grounding.</div>
                      `}
                    </div>

                    <!-- Recommended / Better Answer -->
                    <div style="background: #FFFFFF; padding: 1rem; border-radius: 10px; border: 1px solid #E2E8F0;">
                      <strong style="font-size: 0.82rem; text-transform: uppercase; color: #10B981; letter-spacing: 0.04em; display: block; margin-bottom: 0.5rem;">Recommended / Better Answer</strong>
                      ${evalResp.better_answer ? `
                        <div style="font-size: 0.85rem; color: #065F46; background: #ECFDF5; padding: 0.75rem; border-radius: 8px; border: 1px solid #A7F3D0; line-height: 1.45;">
                          ${this.escapeHtml(evalResp.better_answer)}
                        </div>
                        ${evalResp.better_answer_reason ? `
                          <div style="font-size: 0.78rem; color: #475569; margin-top: 0.4rem;">
                            <strong>Rationale:</strong> ${this.escapeHtml(evalResp.better_answer_reason)}
                          </div>
                        ` : ''}
                      ` : `
                        <div style="font-size: 0.82rem; color: var(--text-muted);">Current response aligns with reference ground truth.</div>
                      `}
                    </div>

                    <!-- Individual Per-Record Donut Chart -->
                    <div style="background: #FFFFFF; padding: 1rem; border-radius: 10px; border: 1px solid #E2E8F0; display: flex; flex-direction: column; align-items: center; justify-content: center;">
                      <strong style="font-size: 0.82rem; text-transform: uppercase; color: #4338CA; letter-spacing: 0.04em; margin-bottom: 0.5rem;">Dimension Distribution</strong>
                      <div style="width: 150px; height: 150px; position: relative;">
                        <canvas id="${canvasId}" width="150" height="150"></canvas>
                      </div>
                    </div>

                  </div>

                </div>
              </td>
            </tr>
          `;
        }).join('');

        // Bind Row and Toggle Button click events
        document.querySelectorAll('.btn-row-toggle').forEach(btn => {
          btn.addEventListener('click', (e) => {
            e.stopPropagation();
            const idx = parseInt(btn.getAttribute('data-row-toggle'), 10);
            this.toggleBatchRow(idx);
          });
        });

        document.querySelectorAll('.batch-main-row').forEach(row => {
          row.addEventListener('click', (e) => {
            if (e.target.closest('.btn-row-toggle')) return;
            const idx = parseInt(row.getAttribute('data-row-idx'), 10);
            this.toggleBatchRow(idx);
          });
        });
      }
    }

    this.batchResultsDashboard?.classList.remove('hidden');
    setTimeout(() => {
      this.batchResultsDashboard?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 100);
  }

  toggleBatchRow(idx) {
    const detailRow = document.getElementById(`batch-row-detail-${idx}`);
    const toggleBtn = document.querySelector(`[data-row-toggle="${idx}"]`);
    if (!detailRow) return;

    const isHidden = detailRow.classList.contains('hidden');
    if (isHidden) {
      detailRow.classList.remove('hidden');
      if (toggleBtn) toggleBtn.textContent = '▼';
      this.renderBatchRowPieChart(idx, this.batchResults[idx]);
    } else {
      detailRow.classList.add('hidden');
      if (toggleBtn) toggleBtn.textContent = '▶';
    }
  }

  expandAllBatchRows() {
    document.querySelectorAll('.batch-detail-row').forEach(row => {
      row.classList.remove('hidden');
    });
    document.querySelectorAll('.btn-row-toggle').forEach(btn => {
      btn.textContent = '▼';
    });
    if (this.batchResults) {
      this.batchResults.forEach((item, idx) => {
        this.renderBatchRowPieChart(idx, item);
      });
    }
  }

  collapseAllBatchRows() {
    document.querySelectorAll('.batch-detail-row').forEach(row => {
      row.classList.add('hidden');
    });
    document.querySelectorAll('.btn-row-toggle').forEach(btn => {
      btn.textContent = '▶';
    });
  }

  renderBatchRowPieChart(idx, item) {
    if (!item) return;
    const canvasId = `batch-row-pie-${idx}`;
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;

    let halPct = 0;
    if (item.hallucination_percentage !== null && item.hallucination_percentage !== undefined) {
      halPct = Number(item.hallucination_percentage);
    } else if (item.evaluation_detail?.evaluation?.hallucination?.percentage !== undefined) {
      halPct = Number(item.evaluation_detail.evaluation.hallucination.percentage);
    } else if (item.hallucination_score !== null && item.hallucination_score !== undefined) {
      halPct = 100 - Number(item.hallucination_score);
    }
    const halSafety = Math.max(0, 100 - halPct);

    renderBatchMiniPieChart(canvasId, {
      relevance: Number(item.relevance_score || 0),
      accuracy: Number(item.accuracy_score || 0),
      completeness: Number(item.completeness_score || 0),
      hallucination_safety: halSafety
    }, this.batchCardCharts);
  }

  openBatchItemModal(item) {
    if (!item || !this.batchDetailModal || !this.modalContentArea) return;

    const isInvalid = item.status === 'INVALID' || item.status === 'FAILED' || item.record_status === 'INVALID';
    const verdict = item.final_verdict || item.verdict || (isInvalid ? 'FAIL' : 'PASS');
    const rowNum = item.row_id !== undefined ? item.row_id : 'N/A';
    let verdictBadgeClass = 'badge-pass';
    if (verdict === 'NEEDS IMPROVEMENT') verdictBadgeClass = 'badge-needs-improvement';
    else if (verdict === 'FAIL') verdictBadgeClass = 'badge-fail';

    this.modalContentArea.innerHTML = `
      <div style="border-bottom: 1px solid #E2E8F0; padding-bottom: 1rem; margin-bottom: 1.25rem;">
        <h3 style="font-family: var(--font-heading); font-size: 1.3rem; font-weight: 700; color: #0F172A; margin: 0 0 0.35rem 0;">
          Record Detail: Row #${rowNum}
        </h3>
        <span class="badge-pill ${verdictBadgeClass}">${verdict}</span>
      </div>
      <div>
        <p><strong>Question:</strong> ${this.escapeHtml(item.question)}</p>
        <p><strong>AI Response:</strong> ${this.escapeHtml(item.ai_response)}</p>
        <p><strong>Reference:</strong> ${this.escapeHtml(item.reference_answer)}</p>
      </div>
    `;
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

