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
        labels: ['Reference Answer (Ground Truth)', 'Better / Grounded Answer', 'Semantic Similarity'],
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
          ${this.renderFallbackBar('Reference Ground Truth', refScore, '#6366F1')}
          ${this.renderFallbackBar('Better Grounded Answer', betterScore, '#10B981')}
          ${this.renderFallbackBar('Semantic Similarity', similarityPct, '#3B82F6')}
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
      'Hallucination-Free (20%)',
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
