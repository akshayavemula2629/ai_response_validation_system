/**
 * Answer Quality Comparison Chart Component
 * Renders an interactive, animated bar chart comparing Reference Answer (100),
 * Better Answer score, and Semantic Similarity percentage.
 */

export class ComparisonChart {
  constructor(canvasId) {
    this.canvasId = canvasId;
    this.chartInstance = null;
  }

  /**
   * Updates or creates the interactive bar chart.
   * @param {Object} comparisonData
   * @param {number} comparisonData.reference_answer_score
   * @param {number} comparisonData.better_answer_score
   * @param {number} comparisonData.similarity_percentage
   */
  render(comparisonData) {
    const refScore = Number(comparisonData?.reference_answer_score) || 100.0;
    const betterScore = Number(comparisonData?.better_answer_score) || 0.0;
    const similarityPct = Number(comparisonData?.similarity_percentage) || 0.0;

    const canvas = document.getElementById(this.canvasId);
    if (!canvas) return;

    // Check if Chart.js global is available
    if (window.Chart) {
      this.renderChartJs(canvas, refScore, betterScore, similarityPct);
    } else {
      this.renderSvgFallback(canvas, refScore, betterScore, similarityPct);
    }
  }

  /**
   * Renders polished Chart.js bar chart.
   */
  renderChartJs(canvas, refScore, betterScore, similarityPct) {
    const ctx = canvas.getContext('2d');

    if (this.chartInstance) {
      this.chartInstance.destroy();
    }

    // Create subtle gradient bars
    const gradientRef = ctx.createLinearGradient(0, 0, 0, 220);
    gradientRef.addColorStop(0, '#6366F1'); // Indigo
    gradientRef.addColorStop(1, '#818CF8');

    const gradientBetter = ctx.createLinearGradient(0, 0, 0, 220);
    gradientBetter.addColorStop(0, '#10B981'); // Emerald
    gradientBetter.addColorStop(1, '#34D399');

    const gradientSim = ctx.createLinearGradient(0, 0, 0, 220);
    gradientSim.addColorStop(0, '#3B82F6'); // Blue
    gradientSim.addColorStop(1, '#60A5FA');

    this.chartInstance = new window.Chart(ctx, {
      type: 'bar',
      data: {
        labels: ['Reference Ground Truth (Baseline: 100%)', 'Better Answer Alignment (Ref-Grounded)', 'Semantic Similarity to Reference'],
        datasets: [{
          label: 'Score / Percentage',
          data: [refScore, betterScore, similarityPct],
          backgroundColor: [gradientRef, gradientBetter, gradientSim],
          borderColor: ['#4F46E5', '#059669', '#2563EB'],
          borderWidth: 1.5,
          borderRadius: 14,
          borderSkipped: false,
          barThickness: 44,
          maxBarThickness: 56
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: {
          duration: 1100,
          easing: 'easeOutQuart'
        },
        plugins: {
          legend: {
            display: false
          },
          tooltip: {
            backgroundColor: '#0F172A',
            titleFont: { family: 'Space Grotesk', size: 14, weight: 'bold' },
            bodyFont: { family: 'DM Sans', size: 13 },
            padding: 12,
            cornerRadius: 10,
            displayColors: true,
            callbacks: {
              label: function(context) {
                return ` ${context.parsed.y.toFixed(1)} / 100 (${context.label.includes('Similarity') ? 'Overlap' : 'Quality'})`;
              }
            }
          }
        },
        scales: {
          y: {
            min: 0,
            max: 100,
            ticks: {
              stepSize: 20,
              font: { family: 'DM Sans', size: 12 },
              color: '#64748B',
              callback: (value) => `${value}%`
            },
            grid: {
              color: 'rgba(226, 232, 240, 0.6)',
              drawBorder: false
            }
          },
          x: {
            ticks: {
              font: { family: 'Space Grotesk', size: 12, weight: '500' },
              color: '#334155'
            },
            grid: {
              display: false
            }
          }
        }
      }
    });
  }

  /**
   * Fallback SVG renderer if Chart.js is unavailable offline.
   */
  renderSvgFallback(canvas, refScore, betterScore, similarityPct) {
    const parent = canvas.parentElement;
    if (!parent) return;

    parent.innerHTML = `
      <div class="svg-fallback-chart" style="padding: 1rem 0; width: 100%;">
        <div style="display: flex; flex-direction: column; gap: 1rem;">
          ${this.renderFallbackBar('Reference Ground Truth (Baseline: 100%)', refScore, '#6366F1')}
          ${this.renderFallbackBar('Better Answer Alignment (Ref-Grounded)', betterScore, '#10B981')}
          ${this.renderFallbackBar('Semantic Similarity to Reference', similarityPct, '#3B82F6')}
        </div>
      </div>
    `;
  }

  renderFallbackBar(label, value, color) {
    return `
      <div>
        <div style="display: flex; justify-content: space-between; font-family: 'Space Grotesk'; font-size: 0.85rem; margin-bottom: 0.35rem;">
          <span style="font-weight: 600; color: #334155;">${label}</span>
          <span style="font-weight: 700; color: ${color};">${value.toFixed(1)}%</span>
        </div>
        <div style="width: 100%; height: 16px; background: #EEF2F6; border-radius: 9999px; overflow: hidden;">
          <div style="width: ${value}%; height: 100%; background: ${color}; border-radius: 9999px; transition: width 1s cubic-bezier(0.16, 1, 0.3, 1);"></div>
        </div>
      </div>
    `;
  }
}

/**
 * Milestone 3: Multi-Dimensional Evaluation Metrics Line Chart
 * Renders actual backend-generated evaluation scores:
 * Relevance, Accuracy, Hallucination-Free Quality, Completeness, Overall Score, and Semantic Similarity.
 */
export class MetricsLineChart {
  constructor(canvasId) {
    this.canvasId = canvasId;
    this.chartInstance = null;
  }

  /**
   * Renders or updates the multi-metric line chart.
   * @param {Object} metrics - Data from backend evaluation.
   */
  render(metrics) {
    const canvas = document.getElementById(this.canvasId);
    if (!canvas) return;

    const rel = Number(metrics?.relevance?.score) || 0.0;
    const acc = Number(metrics?.accuracy?.score) || 0.0;
    const halQual = Number(metrics?.hallucination?.score) || (100.0 - Number(metrics?.hallucination?.percentage || 0));
    const comp = Number(metrics?.completeness?.score) || 0.0;
    const overall = Number(metrics?.overall_score) || 0.0;
    const sim = Number(metrics?.similarity?.percentage) || 0.0;

    const labels = [
      'Relevance (25%)',
      'Accuracy (30%)',
      'Hallucination-Free Score (20%)',
      'Completeness (25%)',
      'Overall Verdict Score',
      'Semantic Similarity'
    ];
    const dataPoints = [rel, acc, halQual, comp, overall, sim];

    if (window.Chart) {
      this.renderChartJs(canvas, labels, dataPoints);
    } else {
      this.renderSvgFallback(canvas, labels, dataPoints);
    }
  }

  renderChartJs(canvas, labels, dataPoints) {
    const ctx = canvas.getContext('2d');
    if (this.chartInstance) {
      this.chartInstance.destroy();
    }

    const gradient = ctx.createLinearGradient(0, 0, 0, 260);
    gradient.addColorStop(0, 'rgba(79, 70, 229, 0.28)');
    gradient.addColorStop(1, 'rgba(79, 70, 229, 0.02)');

    this.chartInstance = new window.Chart(ctx, {
      type: 'line',
      data: {
        labels: labels,
        datasets: [{
          label: 'Score (0–100)',
          data: dataPoints,
          borderColor: '#4F46E5',
          borderWidth: 3,
          backgroundColor: gradient,
          fill: true,
          tension: 0.35,
          pointBackgroundColor: '#FFFFFF',
          pointBorderColor: '#4F46E5',
          pointBorderWidth: 2.5,
          pointRadius: 6,
          pointHoverRadius: 8,
          pointHoverBackgroundColor: '#4F46E5',
          pointHoverBorderColor: '#FFFFFF'
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: {
          duration: 1000,
          easing: 'easeOutQuart'
        },
        plugins: {
          legend: {
            display: false
          },
          tooltip: {
            backgroundColor: '#0F172A',
            titleFont: { family: 'Space Grotesk', size: 13, weight: 'bold' },
            bodyFont: { family: 'DM Sans', size: 13 },
            padding: 12,
            cornerRadius: 10,
            callbacks: {
              label: function(context) {
                return ` Score: ${context.parsed.y.toFixed(1)} / 100`;
              }
            }
          }
        },
        scales: {
          y: {
            min: 0,
            max: 100,
            ticks: {
              stepSize: 20,
              font: { family: 'DM Sans', size: 12 },
              color: '#64748B',
              callback: (value) => `${value}`
            },
            grid: {
              color: 'rgba(226, 232, 240, 0.7)',
              drawBorder: false
            }
          },
          x: {
            ticks: {
              font: { family: 'Space Grotesk', size: 11, weight: '500' },
              color: '#334155'
            },
            grid: {
              display: false
            }
          }
        }
      }
    });
  }

  renderSvgFallback(canvas, labels, dataPoints) {
    const parent = canvas.parentElement;
    if (!parent) return;

    let itemsHtml = '';
    labels.forEach((label, idx) => {
      const val = dataPoints[idx] || 0.0;
      itemsHtml += `
        <div style="margin-bottom: 0.6rem;">
          <div style="display: flex; justify-content: space-between; font-size: 0.85rem; margin-bottom: 0.2rem;">
            <span style="font-weight: 600; color: #334155;">${label}</span>
            <span style="font-weight: 700; color: #4F46E5;">${val.toFixed(1)}/100</span>
          </div>
          <div style="width: 100%; height: 12px; background: #EEF2F6; border-radius: 9999px; overflow: hidden;">
            <div style="width: ${val}%; height: 100%; background: #4F46E5; border-radius: 9999px;"></div>
          </div>
        </div>
      `;
    });

    parent.innerHTML = `<div style="padding: 1rem 0; width: 100%;">${itemsHtml}</div>`;
  }
}

/**
 * Milestone 3: Dynamic Per-Dimension Pie / Doughnut Chart
 * Displays the contribution and balance across evaluation dimensions:
 * Relevance, Accuracy, Completeness, Hallucination-Free Quality, and Semantic Similarity.
 */
export class PerDimensionPieChart {
  constructor(canvasId) {
    this.canvasId = canvasId;
    this.chartInstance = null;
  }

  /**
   * Renders the dynamic pie chart from dimension values.
   * Four canonical evaluation dimensions per prompt specification:
   * 1. Relevance
   * 2. Accuracy
   * 3. Completeness
   * 4. Hallucination Detection (Grounding Safety)
   */
  render(dimensions) {
    const canvas = document.getElementById(this.canvasId);
    if (!canvas) return;

    const rel = Math.max(0, Math.min(100, Number(dimensions?.relevance) || 0));
    const acc = Math.max(0, Math.min(100, Number(dimensions?.accuracy) || 0));
    const comp = Math.max(0, Math.min(100, Number(dimensions?.completeness) || 0));
    let halVal = 100;
    if (dimensions?.hallucination_detection !== undefined) {
      halVal = Number(dimensions.hallucination_detection);
    } else if (dimensions?.hallucination_safety !== undefined) {
      halVal = Number(dimensions.hallucination_safety);
    } else if (dimensions?.hallucination_percentage !== undefined) {
      halVal = 100 - Number(dimensions.hallucination_percentage);
    }
    const hal = Math.max(0, Math.min(100, halVal || 0));

    const labels = [
      'Relevance',
      'Accuracy',
      'Completeness',
      'Hallucination Detection'
    ];
    const dataValues = [rel, acc, comp, hal];
    const colors = ['#6366F1', '#10B981', '#0EA5E9', '#8B5CF6'];
    const hoverColors = ['#4F46E5', '#059669', '#0284C7', '#7C3AED'];

    if (window.Chart) {
      this.renderChartJs(canvas, labels, dataValues, colors, hoverColors);
    } else {
      this.renderSvgFallback(canvas, labels, dataValues, colors);
    }
  }

  renderChartJs(canvas, labels, dataValues, colors, hoverColors) {
    const ctx = canvas.getContext('2d');
    if (this.chartInstance) {
      this.chartInstance.destroy();
    }

    this.chartInstance = new window.Chart(ctx, {
      type: 'doughnut',
      data: {
        labels: labels,
        datasets: [{
          data: dataValues,
          backgroundColor: colors,
          hoverBackgroundColor: hoverColors,
          borderColor: '#FFFFFF',
          borderWidth: 3,
          hoverOffset: 6
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: '58%',
        animation: {
          animateRotate: true,
          duration: 900,
          easing: 'easeOutQuart'
        },
        plugins: {
          legend: {
            position: 'bottom',
            labels: {
              boxWidth: 12,
              boxHeight: 12,
              padding: 14,
              font: { family: 'Space Grotesk', size: 12, weight: '600' },
              color: '#334155'
            }
          },
          tooltip: {
            backgroundColor: '#0F172A',
            titleFont: { family: 'Space Grotesk', size: 13, weight: 'bold' },
            bodyFont: { family: 'DM Sans', size: 12 },
            padding: 10,
            cornerRadius: 8,
            callbacks: {
              label: function(context) {
                const label = context.label || '';
                const val = context.parsed || 0;
                return ` ${label}: ${val.toFixed(1)} / 100`;
              }
            }
          }
        }
      }
    });
  }

  renderSvgFallback(canvas, labels, dataValues, colors) {
    const parent = canvas.parentElement;
    if (!parent) return;

    let itemsHtml = '';
    labels.forEach((label, idx) => {
      const val = dataValues[idx] || 0.0;
      const color = colors[idx] || '#6366F1';
      itemsHtml += `
        <div style="display: flex; justify-content: space-between; align-items: center; padding: 0.4rem 0.6rem; border-radius: 6px; background: #F8FAFC; margin-bottom: 0.35rem;">
          <div style="display: flex; align-items: center; gap: 0.5rem;">
            <span style="display: inline-block; width: 10px; height: 10px; border-radius: 50%; background: ${color};"></span>
            <span style="font-weight: 600; font-size: 0.85rem; color: #334155;">${label}</span>
          </div>
          <span style="font-weight: 700; font-size: 0.85rem; color: ${color};">${val.toFixed(1)} / 100</span>
        </div>
      `;
    });

    parent.innerHTML = `<div style="padding: 0.5rem 0; width: 100%;">${itemsHtml}</div>`;
  }
}

/**
 * Milestone 3: Individual Small Pie / Donut Chart for Batch Record Cards
 * Renders an isolated chart on a per-card basis using that specific record's scores.
 * Fully supports interactive hover displaying Dimension and Score / 100.
 */
export function renderBatchMiniPieChart(canvasId, dimensions, chartRegistry = {}) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return null;

  const rel = Math.max(0, Math.min(100, Number(dimensions?.relevance) || 0));
  const acc = Math.max(0, Math.min(100, Number(dimensions?.accuracy) || 0));
  const comp = Math.max(0, Math.min(100, Number(dimensions?.completeness) || 0));
  let halVal = 100;
  if (dimensions?.hallucination_detection !== undefined) {
    halVal = Number(dimensions.hallucination_detection);
  } else if (dimensions?.hallucination_safety !== undefined) {
    halVal = Number(dimensions.hallucination_safety);
  } else if (dimensions?.hallucination_percentage !== undefined) {
    halVal = 100 - Number(dimensions.hallucination_percentage);
  }
  const hal = Math.max(0, Math.min(100, halVal || 0));

  const labels = ['Relevance', 'Accuracy', 'Completeness', 'Hallucination'];
  const dataValues = [rel, acc, comp, hal];
  const colors = ['#6366F1', '#10B981', '#0EA5E9', '#8B5CF6'];
  const hoverColors = ['#4F46E5', '#059669', '#0284C7', '#7C3AED'];

  // Cleanup prior instance for this canvas if already exists in registry
  if (chartRegistry[canvasId]) {
    chartRegistry[canvasId].destroy();
    delete chartRegistry[canvasId];
  }

  if (window.Chart) {
    const ctx = canvas.getContext('2d');
    const chart = new window.Chart(ctx, {
      type: 'doughnut',
      data: {
        labels: labels,
        datasets: [{
          data: dataValues,
          backgroundColor: colors,
          hoverBackgroundColor: hoverColors,
          borderColor: '#FFFFFF',
          borderWidth: 2,
          hoverOffset: 4
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: '50%',
        animation: {
          duration: 600
        },
        plugins: {
          legend: {
            display: false // Kept compact for small card layout; labels shown in card table
          },
          tooltip: {
            backgroundColor: '#0F172A',
            titleFont: { family: 'Space Grotesk', size: 11, weight: 'bold' },
            bodyFont: { family: 'DM Sans', size: 10 },
            padding: 7,
            cornerRadius: 6,
            callbacks: {
              label: function(context) {
                const label = context.label || '';
                const val = context.parsed || 0;
                return ` ${label}: ${val.toFixed(1)} / 100`;
              }
            }
          }
        }
      }
    });
    chartRegistry[canvasId] = chart;
    return chart;
  } else {
    // Fallback simple mini representation
    const parent = canvas.parentElement;
    if (parent) {
      parent.innerHTML = `
        <div style="font-size:0.75rem; text-align:center; padding:0.25rem;">
          <div>Rel: ${rel.toFixed(0)} | Acc: ${acc.toFixed(0)}</div>
          <div>Comp: ${comp.toFixed(0)} | Hal: ${hal.toFixed(0)}</div>
        </div>
      `;
    }
    return null;
  }
}

/**
 * =========================================================================
 * Milestone 4 Dashboard Analytical Chart Components
 * =========================================================================
 */

export class DashboardVerdictChart {
  constructor(canvasId) {
    this.canvasId = canvasId;
    this.chartInstance = null;
  }

  render(verdictCounts = {}) {
    const canvas = document.getElementById(this.canvasId);
    if (!canvas) return;

    const pass = Number(verdictCounts.PASS || verdictCounts.Pass || 0);
    const needs = Number(verdictCounts['NEEDS IMPROVEMENT'] || verdictCounts['Needs Improvement'] || 0);
    const fail = Number(verdictCounts.FAIL || verdictCounts.Fail || 0);
    const total = pass + needs + fail;

    if (this.chartInstance) {
      this.chartInstance.destroy();
      this.chartInstance = null;
    }

    if (!window.Chart) return;
    const ctx = canvas.getContext('2d');

    this.chartInstance = new window.Chart(ctx, {
      type: 'doughnut',
      data: {
        labels: ['Pass Verdict', 'Needs Improvement', 'Fail Verdict'],
        datasets: [{
          data: total === 0 ? [1, 0, 0] : [pass, needs, fail],
          backgroundColor: total === 0 ? ['#E2E8F0', '#E2E8F0', '#E2E8F0'] : ['#10B981', '#F59E0B', '#EF4444'],
          hoverBackgroundColor: total === 0 ? ['#CBD5E1', '#CBD5E1', '#CBD5E1'] : ['#059669', '#D97706', '#DC2626'],
          borderColor: '#FFFFFF',
          borderWidth: 2,
          hoverOffset: 6
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: '62%',
        animation: { duration: 800 },
        plugins: {
          legend: {
            position: 'bottom',
            labels: {
              font: { family: 'DM Sans', size: 12, weight: '500' },
              padding: 14,
              boxWidth: 12,
              usePointStyle: true
            }
          },
          tooltip: {
            backgroundColor: '#0F172A',
            titleFont: { family: 'Space Grotesk', size: 13, weight: 'bold' },
            bodyFont: { family: 'DM Sans', size: 12 },
            padding: 10,
            cornerRadius: 8,
            callbacks: {
              label: (ctx) => {
                if (total === 0) return ' No evaluations recorded yet';
                const val = ctx.raw || 0;
                const pct = ((val / total) * 100).toFixed(1);
                return ` ${ctx.label}: ${val} (${pct}%)`;
              }
            }
          }
        }
      }
    });
  }
}

export class DashboardDimensionsChart {
  constructor(canvasId) {
    this.canvasId = canvasId;
    this.chartInstance = null;
  }

  render(dimensionAverages = {}) {
    const canvas = document.getElementById(this.canvasId);
    if (!canvas) return;

    const rel = Number(dimensionAverages.relevance || 0);
    const acc = Number(dimensionAverages.accuracy || 0);
    const comp = Number(dimensionAverages.completeness || 0);
    const hal = Number(dimensionAverages.hallucination_safety !== undefined ? dimensionAverages.hallucination_safety : (100 - (dimensionAverages.hallucination || 0)));

    if (this.chartInstance) {
      this.chartInstance.destroy();
      this.chartInstance = null;
    }

    if (!window.Chart) return;
    const ctx = canvas.getContext('2d');

    this.chartInstance = new window.Chart(ctx, {
      type: 'bar',
      data: {
        labels: ['Relevance (25%)', 'Accuracy (30%)', 'Completeness (25%)', 'Hal Safety (20%)'],
        datasets: [{
          label: 'Average Score',
          data: [rel, acc, comp, hal],
          backgroundColor: ['#6366F1', '#10B981', '#F59E0B', '#8B5CF6'],
          borderRadius: 8,
          borderSkipped: false,
          barThickness: 36
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 800 },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: '#0F172A',
            padding: 10,
            cornerRadius: 8,
            callbacks: {
              label: (ctx) => ` ${ctx.label}: ${Number(ctx.raw || 0).toFixed(1)} / 100.0`
            }
          }
        },
        scales: {
          y: {
            min: 0,
            max: 100,
            ticks: {
              stepSize: 20,
              font: { family: 'DM Sans', size: 11 },
              callback: (v) => `${v}%`
            },
            grid: { color: 'rgba(226, 232, 240, 0.6)' }
          },
          x: {
            ticks: { font: { family: 'DM Sans', size: 11, weight: '600' } },
            grid: { display: false }
          }
        }
      }
    });
  }
}

export class DashboardHistogramChart {
  constructor(canvasId) {
    this.canvasId = canvasId;
    this.chartInstance = null;
  }

  render(scoreDistributions = {}) {
    const canvas = document.getElementById(this.canvasId);
    if (!canvas) return;

    const b0_40 = Number(scoreDistributions['0-40'] || 0);
    const b41_70 = Number(scoreDistributions['41-70'] || 0);
    const b71_85 = Number(scoreDistributions['71-85'] || 0);
    const b86_100 = Number(scoreDistributions['86-100'] || 0);

    if (this.chartInstance) {
      this.chartInstance.destroy();
      this.chartInstance = null;
    }

    if (!window.Chart) return;
    const ctx = canvas.getContext('2d');

    this.chartInstance = new window.Chart(ctx, {
      type: 'bar',
      data: {
        labels: ['0–40 (Fail)', '41–70 (Borderline)', '71–85 (Moderate)', '86–100 (High)'],
        datasets: [{
          label: 'Responses Count',
          data: [b0_40, b41_70, b71_85, b86_100],
          backgroundColor: ['#EF4444', '#F59E0B', '#3B82F6', '#10B981'],
          borderRadius: 8,
          borderSkipped: false,
          barThickness: 36
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 800 },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: '#0F172A',
            padding: 10,
            cornerRadius: 8,
            callbacks: {
              label: (ctx) => ` Count: ${ctx.raw} responses`
            }
          }
        },
        scales: {
          y: {
            beginAtZero: true,
            ticks: { precision: 0, font: { family: 'DM Sans', size: 11 } },
            grid: { color: 'rgba(226, 232, 240, 0.6)' }
          },
          x: {
            ticks: { font: { family: 'DM Sans', size: 11, weight: '600' } },
            grid: { display: false }
          }
        }
      }
    });
  }
}

export class DashboardTrendsChart {
  constructor(canvasId) {
    this.canvasId = canvasId;
    this.chartInstance = null;
  }

  render(data = []) {
    const canvas = document.getElementById(this.canvasId);
    if (!canvas) return;

    if (this.chartInstance) {
      this.chartInstance.destroy();
      this.chartInstance = null;
    }

    let emptyEl = document.getElementById('trends-empty-state');

    // Normalize input data into an array of run objects
    let runs = [];
    if (Array.isArray(data)) {
      runs = data;
    } else if (data && typeof data === 'object') {
      if (Array.isArray(data.run_items) && data.run_items.length > 0) {
        runs = data.run_items;
      } else if (Array.isArray(data.runs) && data.runs.length > 0) {
        const scoreTrend = Array.isArray(data.score_trend) ? data.score_trend : [];
        const passTrend = Array.isArray(data.pass_rate_trend) ? data.pass_rate_trend : [];
        runs = data.runs.map((r, i) => ({
          run_label: `Run ${i + 1}`,
          dataset_name: typeof r === 'string' ? r : `Run ${i + 1}`,
          average_score: scoreTrend[i] !== undefined ? scoreTrend[i] : 0,
          pass_rate: passTrend[i] !== undefined ? passTrend[i] : 0
        }));
      }
    }

    // Filter out invalid/null items
    runs = runs.filter(r => r && typeof r === 'object');

    if (runs.length === 0) {
      // Clean honest empty state - NO fake or zero-filled graph
      canvas.style.display = 'none';
      if (!emptyEl && canvas.parentElement) {
        emptyEl = document.createElement('div');
        emptyEl.id = 'trends-empty-state';
        emptyEl.style.cssText = 'display:flex;height:100%;min-height:220px;align-items:center;justify-content:center;flex-direction:column;color:var(--text-muted);font-size:0.95rem;text-align:center;';
        emptyEl.innerHTML = '<span style="font-size:2rem;margin-bottom:0.4rem;">📊</span><span style="font-weight:500;">No historical evaluation runs available yet.</span>';
        canvas.parentElement.appendChild(emptyEl);
      }
      if (emptyEl) {
        emptyEl.style.display = 'flex';
      }
      return;
    }

    // Historical runs exist: show canvas, hide empty state
    canvas.style.display = 'block';
    if (emptyEl) {
      emptyEl.style.display = 'none';
    }

    if (!window.Chart) return;
    const ctx = canvas.getContext('2d');

    const labels = runs.map((r, idx) => r.run_label || `Run ${idx + 1}`);
    const avgScores = runs.map(r => {
      const val = r.average_score !== undefined ? r.average_score : (r.overall_score !== undefined ? r.overall_score : 0);
      return Number(val);
    });
    const passRates = runs.map(r => {
      const val = r.pass_rate !== undefined ? r.pass_rate : 0;
      return Number(val);
    });

    const isSingle = runs.length === 1;

    this.chartInstance = new window.Chart(ctx, {
      type: 'line',
      data: {
        labels: labels,
        datasets: [
          {
            label: 'Quality Score',
            data: avgScores,
            borderColor: '#6366F1',
            backgroundColor: 'rgba(99, 102, 241, 0.1)',
            tension: isSingle ? 0 : 0.35,
            pointBackgroundColor: '#6366F1',
            pointRadius: isSingle ? 6 : 5,
            pointHoverRadius: isSingle ? 8 : 7,
            borderWidth: 2.5
          },
          {
            label: 'Pass Rate (%)',
            data: passRates,
            borderColor: '#10B981',
            backgroundColor: 'rgba(16, 185, 129, 0.1)',
            tension: isSingle ? 0 : 0.35,
            pointBackgroundColor: '#10B981',
            pointRadius: isSingle ? 6 : 5,
            pointHoverRadius: isSingle ? 8 : 7,
            borderWidth: 2.5
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 900 },
        plugins: {
          legend: {
            position: 'top',
            align: 'end',
            labels: {
              font: { family: 'DM Sans', size: 12, weight: '600' },
              boxWidth: 14,
              usePointStyle: true
            }
          },
          tooltip: {
            backgroundColor: '#0F172A',
            titleFont: { family: 'Space Grotesk', size: 13, weight: 'bold' },
            bodyFont: { family: 'DM Sans', size: 12 },
            padding: 10,
            cornerRadius: 8,
            callbacks: {
              title: (items) => {
                const idx = items[0].dataIndex;
                const r = runs[idx] || {};
                const name = r.dataset_name || r.batch_id || `Run ${idx + 1}`;
                return `Evaluation Run: Run ${idx + 1} (${name})`;
              },
              label: (ctx) => {
                const label = ctx.dataset.label || '';
                const val = ctx.parsed.y;
                if (label.includes('Pass Rate')) {
                  return `Pass Rate: ${val}%`;
                }
                return `Quality Score: ${val}`;
              },
              afterLabel: (ctx) => {
                const item = runs[ctx.dataIndex];
                const dt = item?.evaluation_time || item?.timestamp;
                if (dt) {
                  return `Date: ${dt.substring(0, 19)}`;
                }
                return '';
              }
            }
          }
        },
        scales: {
          y: {
            min: 0,
            max: 100,
            ticks: {
              stepSize: 20,
              font: { family: 'DM Sans', size: 11 },
              callback: (v) => `${v}%`
            },
            grid: { color: 'rgba(226, 232, 240, 0.6)' }
          },
          x: {
            ticks: { font: { family: 'DM Sans', size: 11, weight: '500' } },
            grid: { display: false }
          }
        }
      }
    });
  }
}


