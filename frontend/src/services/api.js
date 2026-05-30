import axios from 'axios';
import { config } from '../config.js';

const apiClient = axios.create({
  baseURL: `${config.apiBaseUrl}/api/v1`,
  timeout: 120000, // 2 minutes for large uploads
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor
apiClient.interceptors.request.use(
  (requestConfig) => {
    /**
     * Important:
     * When sending FormData, do not manually force JSON content type.
     * Axios/browser will automatically set multipart/form-data with boundary.
     */
    if (requestConfig.data instanceof FormData) {
      delete requestConfig.headers['Content-Type'];
    }

    return requestConfig;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const errorMessage =
      error.response?.data?.error?.message ||
      error.response?.data?.detail?.error?.message ||
      error.response?.data?.detail ||
      error.response?.data?.message ||
      error.message ||
      'An error occurred';

    console.error('API Error:', errorMessage, error);

    return Promise.reject(error);
  }
);

export default apiClient;