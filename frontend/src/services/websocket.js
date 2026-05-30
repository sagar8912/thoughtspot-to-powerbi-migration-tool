import { config } from '../config.js';

export class JobWebSocket {
  constructor(jobId, onMessage, onError) {
    const wsUrl = `${config.wsBaseUrl}/api/v1/jobs/${jobId}/ws`;
    this.ws = new WebSocket(wsUrl);
    this.jobId = jobId;
    this.onMessage = onMessage;
    this.onError = onError;

    this.ws.onopen = () => {
      console.log(`WebSocket connected for job ${jobId}`);
    };

    this.ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        this.onMessage(message);
      } catch (error) {
        console.error('Failed to parse WebSocket message:', error);
      }
    };

    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      this.onError(error);
    };

    this.ws.onclose = () => {
      console.log('WebSocket closed');
    };
  }

  send(message) {
    if (this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    }
  }

  close() {
    if (this.ws) {
      this.ws.close();
    }
  }
}
