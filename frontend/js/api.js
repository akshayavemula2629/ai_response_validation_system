/**
 * API Service
 * Handles communication with the FastAPI backend with comprehensive error handling.
 */
import { CONFIG } from './config.js';

class ApiService {
  constructor() {
    this.baseUrl = CONFIG.API_BASE_URL;
  }

  /**
   * Sets custom API base URL if needed.
   * @param {string} url 
   */
  setBaseUrl(url) {
    this.baseUrl = url.replace(/\/$/, '');
  }

  /**
   * Performs health check against backend.
   * @returns {Promise<boolean>}
   */
  async checkHealth() {
    try {
      const response = await fetch(`${this.baseUrl}${CONFIG.ENDPOINTS.HEALTH}`, {
        method: 'GET',
        headers: { 'Accept': 'application/json' }
      });
      return response.ok;
    } catch {
      return false;
    }
  }

  /**
   * Sends an evaluation request to POST /api/evaluate.
   * @param {Object} payload 
   * @param {string} payload.question
   * @param {string} payload.ai_response
   * @param {string} payload.reference_answer
   * @param {string|null} payload.source_document
   * @returns {Promise<Object>}
   */
  async evaluateResponse(payload) {
    const url = `${this.baseUrl}${CONFIG.ENDPOINTS.EVALUATE}`;
    
    let response;
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 60000); // 60s timeout

      response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        },
        body: JSON.stringify(payload),
        signal: controller.signal
      });

      clearTimeout(timeoutId);
    } catch (err) {
      if (err.name === 'AbortError') {
        throw new Error('Evaluation request timed out. The server took too long to analyze the response.');
      }
      // Connection failure / network offline
      throw new Error('Unable to connect to the evaluation service. Please make sure the backend is running.');
    }

    // Process response
    let data;
    try {
      data = await response.json();
    } catch {
      throw new Error('Received an unreadable or malformed response from the evaluation server.');
    }

    if (!response.ok) {
      // Format structured error message
      const errorTitle = data.error || 'Evaluation Failed';
      const errorMsg = data.message || 'The server could not process the evaluation.';
      const detailed = `${errorTitle}: ${errorMsg}`;
      const customErr = new Error(detailed);
      customErr.status = response.status;
      customErr.data = data;
      throw customErr;
    }

    return data;
  }
}

export const apiService = new ApiService();
