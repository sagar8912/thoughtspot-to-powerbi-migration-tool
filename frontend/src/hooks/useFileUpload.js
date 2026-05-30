import { useState, useCallback } from 'react';
import { jobsApi } from '../services/jobsApi.js';
import { useJobStore } from '../stores/jobStore.js';
import { validateFiles } from '../utils/validation.js';
import toast from 'react-hot-toast';

/**
 * Custom hook for file upload functionality
 * Handles file validation, upload progress, and job creation
 *
 * @returns {Object} - Upload state and handlers
 */
const useFileUpload = () => {
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState({});
  const [selectedFiles, setSelectedFiles] = useState([]);

  const setCurrentJob = useJobStore(state => state.actions.setCurrentJob);
  const setUploadedFiles = useJobStore(state => state.actions.setUploadedFiles);

  /**
   * Validates and adds files to the selected files list
   */
  const addFiles = useCallback((files) => {
    const validation = validateFiles(files);

    if (!validation.valid) {
      validation.errors.forEach(error => {
        toast.error(error);
      });
      return { success: false, errors: validation.errors };
    }

    // Add valid files to the list
    const newFiles = validation.validFiles.map(file => ({
      id: `${file.name}-${file.size}-${Date.now()}`,
      file,
      name: file.name,
      size: file.size,
      status: 'ready' // 'ready', 'uploading', 'uploaded', 'error'
    }));

    setSelectedFiles(prev => [...prev, ...newFiles]);
    setUploadedFiles(validation.validFiles);

    return { success: true, files: newFiles };
  }, [setUploadedFiles]);

  /**
   * Removes a file from the selected files list
   */
  const removeFile = useCallback((fileId) => {
    setSelectedFiles(prev => prev.filter(f => f.id !== fileId));
  }, []);

  /**
   * Clears all selected files
   */
  const clearFiles = useCallback(() => {
    setSelectedFiles([]);
    setUploadProgress({});
  }, []);

  /**
   * Uploads files to the server
   */
  const uploadFiles = useCallback(async () => {
    if (selectedFiles.length === 0) {
      toast.error('Please select at least one file');
      return { success: false, error: 'No files selected' };
    }

    setIsUploading(true);

    try {
      // Extract File objects from selected files
      const files = selectedFiles.map(sf => sf.file);

      // Track overall progress
      let totalProgress = 0;

      const onUploadProgress = (progressEvent) => {
        totalProgress = progressEvent;
        setUploadProgress({ overall: totalProgress });
      };

      // Create job with files
      const jobData = await jobsApi.createJob(files, onUploadProgress);

      // Update job store
      setCurrentJob(jobData);

      toast.success('Files uploaded successfully!');

      return {
        success: true,
        jobId: jobData.job_id,
        job: jobData
      };
    } catch (error) {
      console.error('Upload error:', error);
      const errorMessage = error.response?.data?.error?.message || 'Upload failed';
      toast.error(errorMessage);

      return {
        success: false,
        error: errorMessage
      };
    } finally {
      setIsUploading(false);
    }
  }, [selectedFiles, setCurrentJob]);

  /**
   * Handles file input change event
   */
  const handleFileInputChange = useCallback((event) => {
    const files = event.target.files;
    if (files && files.length > 0) {
      addFiles(files);
    }
  }, [addFiles]);

  /**
   * Handles file drop event
   */
  const handleFileDrop = useCallback((event) => {
    event.preventDefault();
    const files = event.dataTransfer.files;
    if (files && files.length > 0) {
      addFiles(files);
    }
  }, [addFiles]);

  return {
    // State
    selectedFiles,
    isUploading,
    uploadProgress,

    // Actions
    addFiles,
    removeFile,
    clearFiles,
    uploadFiles,
    handleFileInputChange,
    handleFileDrop
  };
};

export default useFileUpload;
