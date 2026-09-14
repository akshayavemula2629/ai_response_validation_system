/**
 * Overall Score Gauge Component
 * Renders an animated circular SVG gauge and verdict badge with smooth spring interpolation.
 */

export class ScoreGauge {
  constructor(containerId) {
    this.container = document.getElementById(containerId);
  }

  /**
   * Updates the circular gauge and score counter.
   * @param {number} score - Overall score between 0 and 100
   * @param {string} verdict - Verdict label ('Excellent', 'Good', 'Needs Improvement', 'Poor')
   */
  render(score, verdict) {
    if (!this.container) return;

    const normalizedScore = Math.max(0, Math.min(100, Number(score) || 0));
    const radius = 68;
    const circumference = 2 * Math.PI * radius;
    const targetOffset = circumference - (normalizedScore / 100) * circumference;

    // Determine verdict color theme
    const theme = this.getVerdictTheme(verdict);

    this.container.innerHTML = `
      <div class="score-gauge-wrapper">
        <svg class="score-gauge-svg" width="170" height="170" viewBox="0 0 170 170">
          <circle
            class="gauge-bg-circle"
            cx="85"
            cy="85"
            r="${radius}"
            fill="none"
            stroke-width="12"
          />
          <circle
            id="gauge-progress-circle"
            class="gauge-progress-circle"
            cx="85"
            cy="85"
            r="${radius}"
            fill="none"
            stroke="${theme.color}"
            stroke-width="12"
            stroke-linecap="round"
            stroke-dasharray="${circumference}"
            stroke-dashoffset="${circumference}"
          />
        </svg>
        <div class="gauge-center-content">
          <div class="gauge-score-value">
            <span id="gauge-counter">0</span><span class="gauge-max">/100</span>
          </div>
          <div class="gauge-verdict-badge" style="background-color: ${theme.badgeBg}; color: ${theme.badgeColor}; border: 1px solid ${theme.badgeBorder};">
            ${verdict}
          </div>
        </div>
      </div>
    `;

    // Trigger stroke dashoffset animation
    requestAnimationFrame(() => {
      const circle = document.getElementById('gauge-progress-circle');
      if (circle) {
        circle.style.transition = 'stroke-dashoffset 1.4s cubic-bezier(0.16, 1, 0.3, 1)';
        circle.style.strokeDashoffset = `${targetOffset}`;
      }
      this.animateCounter('gauge-counter', normalizedScore, 1200);
    });
  }

  /**
   * Smoothly animates numeric score counter from 0 to target value.
   */
  animateCounter(elementId, targetValue, durationMs) {
    const el = document.getElementById(elementId);
    if (!el) return;

    const startTime = performance.now();
    const update = (currentTime) => {
      const elapsed = currentTime - startTime;
      const progress = Math.min(elapsed / durationMs, 1);
      // Ease out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      const current = (eased * targetValue).toFixed(1);
      el.textContent = current;

      if (progress < 1) {
        requestAnimationFrame(update);
      } else {
        el.textContent = targetValue.toFixed(1);
      }
    };
    requestAnimationFrame(update);
  }

  /**
   * Returns theme styling matching verdict quality.
   */
  getVerdictTheme(verdict) {
    const v = String(verdict || '').toLowerCase();
    if (v === 'excellent') {
      return {
        color: '#10B981', // Emerald
        badgeBg: '#ECFDF5',
        badgeColor: '#065F46',
        badgeBorder: '#A7F3D0'
      };
    } else if (v === 'good') {
      return {
        color: '#6366F1', // Indigo / Violet
        badgeBg: '#EEF2FF',
        badgeColor: '#3730A3',
        badgeBorder: '#C7D2FE'
      };
    } else if (v === 'needs improvement') {
      return {
        color: '#F59E0B', // Amber
        badgeBg: '#FFFBEB',
        badgeColor: '#92400E',
        badgeBorder: '#FDE68A'
      };
    } else { // Poor
      return {
        color: '#EF4444', // Red / Rose
        badgeBg: '#FEF2F2',
        badgeColor: '#991B1B',
        badgeBorder: '#FECACA'
      };
    }
  }
}
