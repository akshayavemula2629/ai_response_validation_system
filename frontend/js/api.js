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

  /**
   * Sends a batch evaluation CSV to POST /api/batch/evaluate.
   * @param {FormData} formData 
   * @returns {Promise<Object>}
   */
  async evaluateBatch(formData) {
    const url = `${this.baseUrl}${CONFIG.ENDPOINTS.BATCH || '/api/batch/evaluate'}`;
    
    let response;
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 180000); // 180s timeout for batch

      response = await fetch(url, {
        method: 'POST',
        headers: {
          'Accept': 'application/json'
        },
        body: formData,
        signal: controller.signal
      });

      clearTimeout(timeoutId);
    } catch (err) {
      if (err.name === 'AbortError') {
        throw new Error('Batch evaluation timed out. The server took too long to process the dataset.');
      }
      throw new Error('Unable to connect to the evaluation service for batch processing. Please check backend connection.');
    }

    let data;
    try {
      data = await response.json();
    } catch {
      throw new Error('Received an unreadable or malformed response from the batch evaluation server.');
    }

    if (!response.ok) {
      const errorTitle = data.error || 'Batch Evaluation Failed';
      const errorMsg = data.message || 'The server could not process the batch file.';
      const customErr = new Error(`${errorTitle}: ${errorMsg}`);
      customErr.status = response.status;
      customErr.data = data;
      throw customErr;
    }

    return data;
  }

  /**
   * Sends an evaluation request with real-time SSE stage progression.
   * @param {Object} payload 
   * @param {Function} onStageUpdate - callback for each stage event
   * @returns {Promise<Object>} final EvaluationResponse
   */
  async evaluateResponseStream(payload, onStageUpdate) {
    const url = `${this.baseUrl}/api/evaluate/stream`;
    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'text/event-stream'
        },
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        return await this.evaluateResponse(payload);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';
      let finalResult = null;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop();

        for (const line of lines) {
          const trimmed = line.trim();
          if (trimmed.startsWith('data:')) {
            try {
              const eventData = JSON.parse(trimmed.slice(5).trim());
              if (onStageUpdate) {
                onStageUpdate(eventData);
              }
              if (eventData.event === 'EVALUATION_COMPLETED' && eventData.result) {
                finalResult = eventData.result;
              } else if (eventData.event === 'ERROR') {
                throw new Error(eventData.error || 'Evaluation failed on server');
              }
            } catch (err) {
              console.warn('Error parsing SSE event chunk:', err);
            }
          }
        }
      }

      if (finalResult) {
        return finalResult;
      }
      return await this.evaluateResponse(payload);
    } catch (err) {
      console.warn('Streaming evaluation fallback to standard endpoint:', err.message);
      return await this.evaluateResponse(payload);
    }
  }

  /**
   * Sends a batch evaluation CSV with real-time SSE row-by-row progress.
   * @param {FormData} formData
   * @param {Function} onRowUpdate - callback for each row processed
   * @returns {Promise<Object>} final BatchEvaluationResponse
   */
  async evaluateBatchStream(formData, onRowUpdate) {
    const url = `${this.baseUrl}/api/batch/evaluate/stream`;
    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Accept': 'text/event-stream'
        },
        body: formData
      });

      if (!response.ok) {
        return await this.evaluateBatch(formData);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';
      let finalResult = null;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop();

        for (const line of lines) {
          const trimmed = line.trim();
          if (trimmed.startsWith('data:')) {
            try {
              const eventData = JSON.parse(trimmed.slice(5).trim());
              if (onRowUpdate) {
                onRowUpdate(eventData);
              }
              if (eventData.event === 'BATCH_COMPLETED' && eventData.summary) {
                finalResult = {
                  summary: eventData.summary,
                  results: eventData.results
                };
              }
            } catch (err) {
              console.warn('Error parsing batch SSE event chunk:', err);
            }
          }
        }
      }

      if (finalResult) {
        return finalResult;
      }
      return await this.evaluateBatch(formData);
    } catch (err) {
      console.warn('Batch streaming fallback to standard batch endpoint:', err.message);
      return await this.evaluateBatch(formData);
    }
  }
}

export const apiService = new ApiService();
