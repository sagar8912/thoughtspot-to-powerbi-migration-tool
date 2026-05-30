import apiClient from './api.js';
import { validateAndLog } from '../utils/apiResponseValidator.js';

export const jobsApi = {
  // POST /api/v1/jobs/ - Upload ThoughtSpot files and create job
  createJob: async (files, onUploadProgress) => {
    const formData = new FormData();

    files.forEach((file) => {
      formData.append('files', file);
    });

    const response = await apiClient.post('/jobs/', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      onUploadProgress: (progressEvent) => {
        if (progressEvent.total && onUploadProgress) {
          const percentCompleted = Math.round(
            (progressEvent.loaded * 100) / progressEvent.total
          );
          onUploadProgress(percentCompleted);
        }
      },
    });

    return response.data;
  },

  // GET /api/v1/jobs/ - List jobs
  listJobs: async (limit = 20, offset = 0) => {
    const response = await apiClient.get('/jobs/', {
      params: {
        limit,
        offset,
      },
    });

    return response.data;
  },

  // GET /api/v1/jobs/{job_id} - Get ThoughtSpot migration job status
  getJobStatus: async (jobId) => {
    const response = await apiClient.get(`/jobs/${jobId}`);
    return response.data;
  },

  // GET /api/v1/jobs/{job_id}/result - Get ThoughtSpot to Power BI migration result
  getJobResult: async (jobId) => {
    const response = await apiClient.get(`/jobs/${jobId}/result`);

    if (import.meta.env.DEV) {
      console.group(`📋 API Response Validation for Job: ${jobId}`);
      validateAndLog(response.data);
      console.groupEnd();
    }

    return response.data;
  },

  // DELETE /api/v1/jobs/{job_id} - Delete job
  deleteJob: async (jobId) => {
    const response = await apiClient.delete(`/jobs/${jobId}`);
    return response.data;
  },

  // ==================== Preview Endpoints ====================

  // POST /api/v1/jobs/preview - Upload ThoughtSpot files for preview
  createPreview: async (files, onUploadProgress) => {
    const formData = new FormData();

    files.forEach((file) => {
      formData.append('files', file);
    });

    const response = await apiClient.post('/jobs/preview', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      onUploadProgress: (progressEvent) => {
        if (progressEvent.total && onUploadProgress) {
          const percentCompleted = Math.round(
            (progressEvent.loaded * 100) / progressEvent.total
          );
          onUploadProgress(percentCompleted);
        }
      },
    });

    return response.data;
  },

  // POST /api/v1/jobs/preview/{preview_id}/confirm - Confirm preview and start migration job
  confirmPreview: async (previewId, fileSelections = []) => {
    const response = await apiClient.post(
      `/jobs/preview/${previewId}/confirm`,
      {
        file_selections: fileSelections,
      }
    );

    return response.data;
  },

  // DELETE /api/v1/jobs/preview/{preview_id} - Cancel preview
  cancelPreview: async (previewId) => {
    const response = await apiClient.delete(`/jobs/preview/${previewId}`);
    return response.data;
  },

  // PATCH /api/v1/jobs/{job_id}/relationships/{relationship_id}/inclusion
  // Optional endpoint. Used only if backend supports relationship inclusion updates.
  updateRelationshipInclusion: async (jobId, relationshipId, included) => {
    const response = await apiClient.patch(
      `/jobs/${jobId}/relationships/${relationshipId}/inclusion`,
      {
        included,
      }
    );

    return response.data;
  },
};